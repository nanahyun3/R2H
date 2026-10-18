"""torch 배치 커널 — 이동창 CoS · Page CUSUM 격자 · 블록 최대 (12번 MC 의 GPU 가속 후보).

CPU 참조: ``core.page_alarm_batch`` · ``core.rolling_segmented`` · ``svrgarch_etf.rolling.rolling_cusum``/``_window_stats``.
이 파일은 numpy·torch 만 import 한다 (torch 가 있는 다른 인터프리터에서 파일 경로로 로드해 쓴다 — r2h 다른 모듈 금지).

- 정의는 CPU 와 연산 순서까지 맞춘다: 창 내부 누적합 (전역 prefix 차분 금지), NaN = 건너뜀, 유효 < ceil(0.9w) 또는 τ̂²≤0 → NaN.
- float64 가 기본. float32 는 비교용 (임계 근처 경보가 뒤집힐 수 있다 — 판정 전에 ``t21_gpu_bench.py`` 결과를 볼 것).
- 경로 축을 chunk 로 나눠 VRAM 예산 안에서 돈다. OOM 이면 chunk 를 절반으로 줄여 같은 위치부터 다시 한다.
"""

from __future__ import annotations

import math

import numpy as np
import torch

MIN_VALID_FRAC = 0.9  # rolling.py 와 같은 값 (import 하지 않고 복제 — 단위 시험이 일치를 확인)
GB = 1024**3
LAST_RUN: dict = {}  # 마지막 chunk 실행 정보 (chunk 크기 · OOM 재시도 횟수) — 벤치 기록용


# ── 공통: 장치 · 예산 · chunk 실행 ─────────────────────────────────


def default_device() -> torch.device:
    """CUDA 가 있으면 cuda:0, 없으면 cpu."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def vram_budget(cap_gb: float = 6.0, reserve_gb: float = 2.0, device: torch.device | None = None) -> int:
    """예산 = min(cap, 여유 − reserve) 바이트. 다른 세션이 GPU 를 쓰고 있을 수 있어 매 호출 시점에 다시 조회한다.

    여유에는 이 프로세스의 캐시 (reserved − allocated) 를 더한다 — torch 캐시 할당기가 쥔 메모리는 재사용 가능하다.
    """
    device = device or default_device()
    if device.type != "cuda":
        return int(cap_gb * GB)
    free, _ = torch.cuda.mem_get_info(device)
    free += torch.cuda.memory_reserved(device) - torch.cuda.memory_allocated(device)
    return max(0, int(min(cap_gb * GB, free - reserve_gb * GB)))  # 0 이면 호출 쪽 chunk 하한 1 이 맡는다


def _as_tensor(x, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """numpy/텐서 → 지정 장치·dtype 텐서."""
    if isinstance(x, torch.Tensor):
        return x.to(device=device, dtype=dtype)
    return torch.as_tensor(np.asarray(x), dtype=dtype, device=device)


def _run_chunked(fn, R: int, chunk: int, cat_dim: int = 0) -> torch.Tensor:
    """fn(a, b) 를 경로 [a, b) 조각마다 호출해 이어 붙인다. OOM 이면 chunk 절반으로 같은 a 부터 재시도."""
    chunk = max(1, min(int(chunk), R))
    outs, a, retries = [], 0, 0
    while a < R:
        b = min(R, a + chunk)
        try:
            outs.append(fn(a, b))
        except torch.cuda.OutOfMemoryError:
            if chunk == 1:
                raise
            retries += 1
            chunk = max(1, chunk // 2)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            continue
        a = b
    LAST_RUN.update(chunk=chunk, oom_retries=retries)
    return torch.cat(outs, dim=cat_dim)


# ── (a) 이동창 CUSUM-of-squares ────────────────────────────────────


def _rolling_chunk(X: torch.Tensor, w: int, min_valid: int) -> torch.Tensor:
    """X (Rc, n) → (Rc, n−w+1) 창 통계량. ``_window_stats`` 와 같은 연산 순서."""
    W = X.unfold(1, w, 1)  # (Rc, m, w) 뷰 — 창마다 따로 누적합
    valid = ~torch.isnan(W)
    z = torch.where(valid, W, torch.zeros((), dtype=X.dtype, device=X.device))
    n = valid.sum(dim=-1)  # 유효 개수 (정수)
    k = valid.cumsum(dim=-1)  # 유효 개수 누적
    s = (z * z).cumsum(dim=-1)  # 제곱 누적
    total = s[..., -1:]
    nf = n.to(X.dtype)
    path = s - k.to(X.dtype) / nf[..., None] * total  # (k/n)·total — CPU 와 같은 순서
    del k, s
    m2 = total[..., 0] / nf
    tau2 = torch.pow(z, 4).sum(dim=-1) / nf - m2 * m2
    del z
    peak = path.abs().masked_fill(~valid, -math.inf).amax(dim=-1)  # NaN 위치는 최대값 후보에서 제외
    del path, valid
    stat = peak / (torch.sqrt(nf) * torch.sqrt(tau2))
    bad = (n < min_valid) | ~(tau2 > 0)  # NaN τ̂² 도 여기서 걸린다
    return stat.masked_fill(bad, math.nan)


def rolling_cos_batch(
    E, w: int, *, dtype: torch.dtype = torch.float64, device: torch.device | None = None,
    budget_bytes: int | None = None, chunk: int | None = None,
) -> torch.Tensor:
    """E (R, n) 행마다 ``rolling_cusum`` — 시점 t 에 [t−w+1, t] 창 통계량, 앞 w−1 = NaN. 반환 (R, n) 텐서 (device)."""
    device = device or default_device()
    X = _as_tensor(E, device, dtype)
    if X.ndim == 1:
        X = X[None, :]
    R, n = X.shape
    out = torch.full((R, n), math.nan, dtype=dtype, device=device)
    if n < w or R == 0:
        return out
    m = n - w + 1
    if chunk is None:
        budget = vram_budget(device=device) if budget_bytes is None else budget_bytes
        per_row = m * w * (X.element_size() * 7 + 8 * 2 + 2)  # 임시 텐서 ≈ 실수 7 · 정수 2 · bool 2
        chunk = max(1, budget // per_row)
    mv = int(np.ceil(MIN_VALID_FRAC * w))
    out[:, w - 1 :] = _run_chunked(lambda a, b: _rolling_chunk(X[a:b], w, mv), R, chunk)
    return out


def rolling_segmented_batch(E, w: int, resets=(), **kw) -> torch.Tensor:
    """모든 경로에 공통인 초기화 위치 ``resets`` 로 구간을 나눠 구간마다 ``rolling_cos_batch`` (``core.rolling_segmented`` 의 배치판)."""
    dtype = kw.get("dtype", torch.float64)
    device = kw.get("device") or default_device()
    X = _as_tensor(E, device, dtype)
    if X.ndim == 1:
        X = X[None, :]
    n = X.shape[1]
    st = sorted({0} | {int(p) for p in np.asarray(resets, int).tolist() if 0 < p < n})
    out = torch.full_like(X, math.nan)
    for j, a in enumerate(st):
        b = st[j + 1] if j + 1 < len(st) else n
        out[:, a:b] = rolling_cos_batch(X[:, a:b], w, **kw)
    return out


# ── (b) Page CUSUM — h 후보 K 개 동시 ──────────────────────────────


def page_increment_t(X: torch.Tensor, lam: float) -> torch.Tensor:
    """0.5((1−1/λ)e² − ln λ). 상수는 호스트 float64 로 만들어 CPU 와 같은 값 (연산은 커널 하나씩 — FMA 융합 없음)."""
    a = 1.0 - 1.0 / lam
    b = float(np.log(lam))
    return 0.5 * (a * (X * X) - b)


def _page_chunk(
    inc: torch.Tensor, H: torch.Tensor, reset: torch.Tensor | None, bid: list[int] | None, n_blocks: int
) -> torch.Tensor:
    """inc (Rc, n) · H (K,) → 경보 (Rc, K, n) 또는 (bid 가 있으면) 블록 경보 (Rc, K, n_blocks). 시간 루프, (경로×h) 벡터화."""
    Rc, n = inc.shape
    K = H.numel()
    okT = torch.isfinite(inc).T.contiguous().unsqueeze(-1)  # (n, Rc, 1)
    xT = torch.where(torch.isfinite(inc), inc, torch.zeros((), dtype=inc.dtype, device=inc.device)).T.contiguous().unsqueeze(-1)
    rT = None if reset is None else reset.T.contiguous().unsqueeze(-1)
    h = H.view(1, K)
    s = torch.zeros((Rc, K), dtype=inc.dtype, device=inc.device)
    if bid is None:
        al = torch.zeros((n, Rc, K), dtype=torch.bool, device=inc.device)
    else:
        al = torch.zeros((n_blocks, Rc, K), dtype=torch.bool, device=inc.device)
    for t in range(n):
        if rT is not None:
            s = s.masked_fill(rT[t], 0.0)  # 그날 갱신 전 상태 0
        ok = okT[t]
        s = torch.where(ok, torch.clamp_min(s + xT[t], 0.0), s)  # NaN 이면 상태 유지
        hit = ok & (s >= h)
        if bid is None:
            al[t] = hit
        elif bid[t] >= 0:
            al[bid[t]] |= hit
        s = s.masked_fill(hit, 0.0)  # 경보 → 상태 0
    return al.permute(1, 2, 0).contiguous()


def _page_common(E, lam, H, reset_mask, dtype, device, budget_bytes, chunk, per_row_out):
    device = device or default_device()
    X = _as_tensor(E, device, dtype)
    if X.ndim == 1:
        X = X[None, :]
    R, n = X.shape
    Ht = _as_tensor(np.atleast_1d(np.asarray(H, float)) if not isinstance(H, torch.Tensor) else H, device, dtype).ravel()
    rm = None if reset_mask is None else _as_tensor(reset_mask, device, torch.bool)
    inc = page_increment_t(X, lam)
    if chunk is None:
        budget = vram_budget(device=device) if budget_bytes is None else budget_bytes
        per_row = per_row_out + n * (X.element_size() * 3 + 2) + Ht.numel() * X.element_size() * 4
        chunk = max(1, budget // per_row)
    return inc, Ht, rm, R, n, chunk


def page_alarm_grid(
    E, lam: float, H, reset_mask=None, *, dtype: torch.dtype = torch.float64, device: torch.device | None = None,
    budget_bytes: int | None = None, chunk: int | None = None,
) -> torch.Tensor:
    """``page_alarm_batch`` 를 h 후보 K 개에 동시에. 반환 alarm (R, K, n) bool 텐서."""
    K = int(np.size(H)) if not isinstance(H, torch.Tensor) else H.numel()
    n = np.shape(E)[-1] if not isinstance(E, torch.Tensor) else E.shape[-1]
    inc, Ht, rm, R, n, chunk = _page_common(E, lam, H, reset_mask, dtype, device, budget_bytes, chunk, 2 * K * n)
    return _run_chunked(lambda a, b: _page_chunk(inc[a:b], Ht, None if rm is None else rm[a:b], None, 0), R, chunk)


def page_block_hits(
    E, lam: float, H, reset_mask, block_id, n_blocks: int, *, dtype: torch.dtype = torch.float64,
    device: torch.device | None = None, budget_bytes: int | None = None, chunk: int | None = None,
) -> torch.Tensor:
    """블록 집계판: (R, K, n_blocks) bool — 블록 내 ≥1 경보. block_id (n,) 정수, −1 = 어느 블록에도 안 듦 (임계 보정용)."""
    K = int(np.size(H)) if not isinstance(H, torch.Tensor) else H.numel()
    bid = [int(v) for v in np.asarray(block_id.cpu() if isinstance(block_id, torch.Tensor) else block_id).tolist()]
    inc, Ht, rm, R, n, chunk = _page_common(E, lam, H, reset_mask, dtype, device, budget_bytes, chunk, 2 * K * n_blocks)
    if len(bid) != n:
        raise ValueError("block_id 길이 ≠ n")
    return _run_chunked(lambda a, b: _page_chunk(inc[a:b], Ht, None if rm is None else rm[a:b], bid, n_blocks), R, chunk)


# ── (c) 블록 최대 ─────────────────────────────────────────────────


def block_max(T, block_id, n_blocks: int, *, device: torch.device | None = None) -> torch.Tensor:
    """T (R, n) → (R, n_blocks) 블록 내 유효 최대 (NaN 무시, 유효 없음 = NaN). block_id −1 = 제외."""
    device = device or (T.device if isinstance(T, torch.Tensor) else default_device())
    Tt = T.to(device) if isinstance(T, torch.Tensor) else _as_tensor(T, device, torch.float64)
    if Tt.ndim == 1:
        Tt = Tt[None, :]
    bid = _as_tensor(block_id, device, torch.int64).ravel()
    keep = bid >= 0
    V = Tt[:, keep].nan_to_num(nan=-math.inf)
    idx = bid[keep].unsqueeze(0).expand(Tt.shape[0], -1)
    out = torch.full((Tt.shape[0], n_blocks), -math.inf, dtype=Tt.dtype, device=device)
    out = out.scatter_reduce(1, idx, V, reduce="amax", include_self=False)
    return out.masked_fill(out == -math.inf, math.nan)
