"""12번 핵심 계산 — 069500 수익률 · 일반화 SVR 잔차 경로 · 분할 이동 CoS · Page CUSUM · 사후 CUSUM (계약 12-lock-1).

T12 원 함수(``fit_annual``·``forecast_year``·``standardize``)와 W1 원 함수(``rolling_cusum``)를 수정 없이 호출한다.
재적합 일정이 연간·확장형이면 경로는 08 W3 ``run_pipeline`` 의 069500 정책 A 와 같아야 한다 (게이트 G0·G2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.annual_expanding.fit import fit_annual, forecast_year, standardize
from r2h.paper2020 import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.svrgarch_etf.rolling import rolling_cusum

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "configs" / "t21_k200_cusum_controlled_v1.json"


def load_cfg(path: Path | None = None) -> dict:
    """동결 설정 JSON."""
    return json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))


def sha16(obj: object) -> str:
    """정렬 JSON 직렬화의 sha256 앞 16자 (설정 해시)."""
    body = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def arr_hash(x: np.ndarray) -> str:
    """float 배열 sha256 앞 16자 (NaN 포함, little-endian float64)."""
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, dtype="<f8")).tobytes()).hexdigest()[:16]


# ── 자료 ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Market:
    """069500 2019-01-03..2025-12-30 (W3 와 같은 범위). eval = 2020 이후 위치."""

    dates: pd.DatetimeIndex
    close: np.ndarray  # 수익률 날짜의 종가
    r: np.ndarray  # 100·Δlog 수익률
    eval_start: int  # 첫 평가일 위치 (2020-01-02)
    raw_sha256: str

    @property
    def n(self) -> int:
        return self.r.size

    @property
    def eval_dates(self) -> pd.DatetimeIndex:
        return self.dates[self.eval_start :]


def load_market(cfg: dict, root: Path = REPO_ROOT) -> Market:
    d = cfg["data"]
    path = root / d["raw_csv"]
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != d["expected_raw_sha256"]:
        raise AssertionError(f"원자료 해시 불일치: {sha}")
    f = pd.read_csv(path, dtype={"Date": str})
    px = pd.Series(f["Close"].astype(float).to_numpy(), index=pd.to_datetime(f["Date"])).sort_index()
    if (px <= 0).any():
        raise ValueError("비양수 종가")
    r = 100.0 * np.log(px).diff()
    r = r.loc[d["returns_start"] : d["returns_end"]]
    if r.isna().any():
        raise AssertionError("결측 수익률")
    idx = pd.DatetimeIndex(r.index)
    es = int(np.searchsorted(idx, pd.Timestamp(d["evaluation_start"])))
    return Market(idx, px.reindex(idx).to_numpy(float), r.to_numpy(float), es, sha)


def market_from_returns(r: np.ndarray, dates: pd.DatetimeIndex, eval_start: int, p0: float = 100.0) -> Market:
    """합성 수익률 → 같은 구조 (종가 = p0·exp(누적 r/100))."""
    r = np.asarray(r, float)
    close = p0 * np.exp(np.cumsum(r) / 100.0)
    return Market(dates, close, r, eval_start, "SYNTHETIC")


# ── 일반화 SVR 잔차 경로 ───────────────────────────────────────────


@dataclass(frozen=True)
class SVRPolicy:
    """재적합 일정·학습창. extra_refits 는 평가 구간 상대 위치(효과일), window_at 는 그 위치의 학습창 (적응형)."""

    window: str | int = "expanding"
    schedule: str | int = "annual"
    extra_refits: tuple[int, ...] = ()
    window_at: tuple[tuple[int, int], ...] = ()
    label: str = "B1"

    def key(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "label"}


def scheduled_positions(m: Market, schedule: str | int) -> list[int]:
    """평가 구간 상대 위치의 정기 재적합 시작점 (항상 0 포함)."""
    ed = m.eval_dates
    if schedule == "annual":
        yrs = ed.year.to_numpy()
        return [0] + [int(i) for i in np.flatnonzero(np.diff(yrs) != 0) + 1]
    step = int(schedule)
    return list(range(0, len(ed), step))


@dataclass
class SVRPath:
    """평가 구간(길이 n_eval) 배열과 적합 기록."""

    e: np.ndarray
    vhat: np.ndarray
    fit_id: np.ndarray  # 평가일마다 사용한 적합 번호
    refit_pos: list[int]
    fits: list[dict] = field(default_factory=list)


class FitCache:
    """(이력 끝 위치, 학습창 길이) → 적합 결과. 같은 이력이면 다시 적합하지 않는다."""

    def __init__(self) -> None:
        self.store: dict[tuple[int, int], object] = {}
        self.n_fits = 0

    def get(self, rc: np.ndarray, end: int, win: int | str):
        hist = rc[:end]
        if win != "expanding" and hist.size > int(win):
            hist = hist[-int(win) :]
        key = (end, hist.size)
        if key not in self.store:
            self.store[key] = fit_annual(hist, round(0.7 * hist.size))
            self.n_fits += 1
        return self.store[key], hist.size


def svr_path(m: Market, pol: SVRPolicy, cache: FitCache | None = None) -> SVRPath:
    """구간 [s_k, s_{k+1}) 마다: s_k 이전 유효 수익률(학습창)로 적합, 같은 시점까지의 전체 이력을 문맥으로 정책 A 예측."""
    cache = cache or FitCache()
    rc = m.r
    n_eval = m.n - m.eval_start
    starts = set(scheduled_positions(m, pol.schedule)) | {p for p in pol.extra_refits if 0 <= p < n_eval}
    starts_l = sorted(starts)
    win_at = dict(pol.window_at)
    e = np.full(n_eval, np.nan)
    vh = np.full(n_eval, np.nan)
    fid = np.full(n_eval, -1, dtype=np.int64)
    fits = []
    for k, s in enumerate(starts_l):
        t = starts_l[k + 1] if k + 1 < len(starts_l) else n_eval
        a, b = m.eval_start + s, m.eval_start + t
        win = win_at.get(s, pol.window)
        af, n_hist = cache.get(rc, a, win)
        v = forecast_year(af.fit, rc[:a], rc[a:b], "A")
        vh[s:t] = v
        e[s:t] = standardize(rc[a:b], v)
        fid[s:t] = k
        fits.append(
            {
                "fit_k": k,
                "eval_pos": s,
                "fit_at": str(m.dates[a].date()),
                "train_start": str(m.dates[a - n_hist].date()),
                "train_end": str(m.dates[a - 1].date()),
                "n_history": n_hist,
                "window": win,
                "history_truncated": bool(win != "expanding" and n_hist < int(win)),
                "C": af.params[0],
                "gamma2": af.params[1],
                "eps": af.params[2],
                "val_mae": af.val_mae,
                "model_hash": af.model_hash,
            }
        )
    return SVRPath(e, vh, fid, starts_l, fits)


# ── 이동창 CUSUM-of-squares (분할) ─────────────────────────────────


def segment_starts(n: int, resets: list[int] | np.ndarray) -> list[int]:
    """초기화 위치 (평가 상대) → 정렬된 구간 시작점 (0 포함, 범위 밖 제외)."""
    s = {0} | {int(p) for p in np.asarray(resets, int).tolist() if 0 < p < n}
    return sorted(s)


def rolling_segmented(e: np.ndarray, w: int, resets: list[int] | np.ndarray = ()) -> np.ndarray:
    """초기화 이후 창이 그 이전으로 넘어가지 않는 이동 CoS. 구간마다 ``rolling_cusum`` 원 함수."""
    e = np.asarray(e, float)
    out = np.full(e.size, np.nan)
    st = segment_starts(e.size, resets)
    for k, a in enumerate(st):
        b = st[k + 1] if k + 1 < len(st) else e.size
        out[a:b] = rolling_cusum(e[a:b], w)
    return out


def days_since_reset(n: int, resets: list[int] | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """각 날짜의 마지막 초기화 이후 경과일 · 누적 초기화 횟수 (시작점 0 은 횟수에 넣지 않음)."""
    st = segment_starts(n, resets)
    since = np.zeros(n, dtype=np.int64)
    count = np.zeros(n, dtype=np.int64)
    for k, a in enumerate(st):
        b = st[k + 1] if k + 1 < len(st) else n
        since[a:b] = np.arange(b - a)
        count[a:b] = k
    return since, count


# ── Page CUSUM ─────────────────────────────────────────────────────


def page_increment(e: np.ndarray, lam: float) -> np.ndarray:
    """정규 분산비 λ 의 로그우도비 증분 0.5((1−1/λ)e² − ln λ). NaN 은 NaN."""
    x = np.asarray(e, float) ** 2
    return 0.5 * ((1.0 - 1.0 / lam) * x - np.log(lam))


def page_free(e: np.ndarray, lam: float, resets: list[int] | np.ndarray = ()) -> tuple[np.ndarray, np.ndarray]:
    """경보 후 재설정이 없는 상태 경로 S (외부 초기화만). 반환 (S, 상태코드) — 0 NATURAL_ZERO 아님/1 자연 0/2 외부."""
    inc = page_increment(e, lam)
    n = inc.size
    rs = set(segment_starts(n, resets)) - {0}
    S = np.full(n, np.nan)
    code = np.zeros(n, dtype=np.int8)
    s = 0.0
    seen = False
    for t in range(n):
        if t in rs:
            s = 0.0
            code[t] = 2
        x = inc[t]
        if np.isfinite(x):
            s = max(0.0, s + x)
            seen = True
            if s == 0.0 and code[t] == 0:
                code[t] = 1
        if seen:
            S[t] = s
    return S, code


def page_alarm(
    e: np.ndarray, lam: float, h: float, resets: list[int] | np.ndarray = ()
) -> tuple[np.ndarray, np.ndarray]:
    """경보 다음날 상태 0 (POST_ALARM_RESET). 반환 (S_alarm, alarm bool)."""
    inc = page_increment(e, lam)
    n = inc.size
    rs = set(segment_starts(n, resets)) - {0}
    S = np.full(n, np.nan)
    al = np.zeros(n, dtype=bool)
    s = 0.0
    seen = False
    for t in range(n):
        if t in rs:
            s = 0.0
        x = inc[t]
        if np.isfinite(x):
            s = max(0.0, s + x)
            seen = True
        if seen:
            S[t] = s
            if s >= h:
                al[t] = True
                s = 0.0
    return S, al


def page_alarm_batch(
    E: np.ndarray, lam: float, h: np.ndarray | float, reset_mask: np.ndarray | None = None
) -> np.ndarray:
    """행 = 경로. 시간 루프 + 경로 벡터화 (CPU 참조 구현). reset_mask (경로, 일) True 인 날 시작 전 상태 0. 반환 alarm bool."""
    E = np.asarray(E, float)
    R, n = E.shape
    inc = 0.5 * ((1.0 - 1.0 / lam) * E**2 - np.log(lam))
    hh = np.broadcast_to(np.asarray(h, float), (R,))
    s = np.zeros(R)
    al = np.zeros((R, n), dtype=bool)
    for t in range(n):
        if reset_mask is not None:
            s = np.where(reset_mask[:, t], 0.0, s)
        x = inc[:, t]
        ok = np.isfinite(x)
        s = np.where(ok, np.maximum(0.0, s + np.where(ok, x, 0.0)), s)
        hit = ok & (s >= hh)
        al[:, t] = hit
        s = np.where(hit, 0.0, s)
    return al


# ── 사후 CUSUM ─────────────────────────────────────────────────────


def posthoc_full(e: np.ndarray) -> dict:
    """유효 잔차 전체에 원문 사후 검정. k̂ 는 평가 상대 위치 (POSTHOC_ONLY)."""
    x = np.asarray(e, float)
    keep = np.flatnonzero(np.isfinite(x))
    if keep.size < 30:
        return {"T": np.nan, "khat": None, "n": int(keep.size)}
    res = cusum_squares_test(
        x[keep], tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RETURN_NAN
    )
    k = None if res.change_index_one_based is None else int(keep[res.change_index_one_based - 1])
    return {"T": float(res.statistic), "khat": k, "n": int(keep.size), "path": res.centered_path}


# ── 블록 오경보 · 임계값 ───────────────────────────────────────────


def year_blocks(m: Market, years: list[int]) -> list[np.ndarray]:
    """평가 상대 위치의 연도 블록 마스크 목록."""
    yr = m.eval_dates.year.to_numpy()
    return [yr == y for y in years]


def block_max(T: np.ndarray, blocks: list[np.ndarray]) -> np.ndarray:
    """(경로, 일) → (경로, 블록) 블록 내 유효 최대 (유효 없음 = NaN)."""
    T = np.atleast_2d(T)
    out = np.full((T.shape[0], len(blocks)), np.nan)
    for j, b in enumerate(blocks):
        seg = T[:, b]
        ok = np.isfinite(seg).any(axis=1)
        out[ok, j] = np.nanmax(seg[ok], axis=1)
    return out


def crit_block_alpha(null_T: np.ndarray, blocks: list[np.ndarray], alpha: float) -> float:
    """귀무 경로의 블록 최대 (1−α) 분위 = 블록마다 ≥1 경보 확률 α 인 임계값 (블록 풀링)."""
    bm = block_max(null_T, blocks).ravel()
    bm = bm[np.isfinite(bm)]
    return float(np.quantile(bm, 1.0 - alpha))


def block_alarm_rate(alarm: np.ndarray, blocks: list[np.ndarray]) -> float:
    """(경로, 일) 경보 → 블록마다 ≥1 경보 비율 (풀링)."""
    a = np.atleast_2d(alarm)
    hits = np.stack([a[:, b].any(axis=1) for b in blocks], axis=1)
    return float(hits.mean())


def calibrate_page_h(
    E: np.ndarray, lam: float, blocks: list[np.ndarray], alpha: float, reset_mask: np.ndarray | None = None,
    lo: float = 0.05, hi: float = 60.0, iters: int = 40, batch_fn=page_alarm_batch,
) -> float:
    """블록 경보 확률이 α 가 되도록 h 를 이분 탐색 (경보 확률은 h 에 대해 단조 감소)."""
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        rate = block_alarm_rate(batch_fn(E, lam, mid, reset_mask), blocks)
        if rate > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def calibrate_page_two(
    E: np.ndarray, blocks: list[np.ndarray], alpha: float, reset_mask: np.ndarray | None = None,
    lam_up: float = 2.0, lam_dn: float = 0.5, iters: int = 30, batch_fn=page_alarm_batch,
) -> tuple[float, float]:
    """양방향: 단측 α₁ 을 같게 두고 합집합 블록 경보 확률이 α 가 되도록 α₁ 이분 탐색."""
    lo, hi = alpha / 2.0, alpha
    best = (np.nan, np.nan)
    for _ in range(iters):
        a1 = 0.5 * (lo + hi)
        hu = calibrate_page_h(E, lam_up, blocks, a1, reset_mask, batch_fn=batch_fn)
        hl = calibrate_page_h(E, lam_dn, blocks, a1, reset_mask, batch_fn=batch_fn)
        al = batch_fn(E, lam_up, hu, reset_mask) | batch_fn(E, lam_dn, hl, reset_mask)
        rate = block_alarm_rate(al, blocks)
        best = (hu, hl)
        if rate > alpha:
            hi = a1
        else:
            lo = a1
    return best
