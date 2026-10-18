"""귀무 보정 실행부 — MC 잔차 배열에서 실험 설정별 임계값 · 귀무 분포표 · 홀드아웃 크기 · 시나리오 검출 (계약 §6–7).

백엔드: GPU(torch float64, ``gpu.py``)가 있으면 이동 CoS 와 Page h 격자를 GPU 로, 없으면 CPU 참조 구현.
임계값과 그것을 비교할 귀무 T 는 같은 백엔드에서 만든다 (D-07).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import zlib

import numpy as np
import pandas as pd

from . import calib as K
from . import core as C
from . import detectors as D

ALPHAS = (0.05, 0.20)
YEARS = (2021, 2022, 2023, 2024, 2025)
H_GRID = np.geomspace(0.2, 400.0, 512)
QTAB = np.linspace(0.0, 1.0, 2001)


@dataclass
class MCSet:
    """한 집합·시나리오의 파이프라인별 e (rep, n) · 메타 · 트리거."""

    E: dict[str, np.ndarray]
    meta: pd.DataFrame
    trig: pd.DataFrame
    resets_cache: dict = field(default_factory=dict)

    @property
    def R(self) -> int:
        return len(self.meta)

    def reset_mask(self, m: C.Market, reset: str, seed: int, salt: str) -> np.ndarray:
        """경로별 초기화 마스크. 달력 일정은 모든 경로 공통, cp: 는 경로 자신의 트리거, placebo_random 은 주 규칙과 같은 횟수."""
        key = (reset, salt)
        if key in self.resets_cache:
            return self.resets_cache[key]
        n = m.n - m.eval_start
        reps = self.meta["rep"].to_numpy()
        if reset in ("none", "NA"):
            M = np.zeros((self.R, n), bool)
        elif reset.startswith("cp:") or reset == "placebo_random":
            rule, q, g = ("V20_two", 0.99, 20) if reset == "placebo_random" else reset.split(":")[1:]
            sub = self.trig[(self.trig["rule"] == rule) & (self.trig["q"] == float(q)) & (self.trig["gap"] == int(g))]
            by = {int(k): v["effect_rel"].to_numpy(int) for k, v in sub.groupby("rep")}
            rows = []
            for rp in reps:
                pos = by.get(int(rp), np.array([], int)).tolist()
                if reset == "placebo_random":
                    rng = np.random.default_rng([seed, int(rp), 7, zlib.crc32(salt.encode()) & 0xFFFF])
                    pos = K.placebo_random(n, len(pos), int(g), rng)
                rows.append(pos)
            M = D.reset_mask(self.R, n, rows)
        else:
            rs = D.reset_positions(m, reset)
            M = np.zeros((self.R, n), bool)
            M[:, [p for p in rs if 0 < p < n]] = True
        self.resets_cache[key] = M
        return M


def load_set(mc_dir: Path, st: str, sc: str) -> MCSet:
    meta = pd.read_csv(mc_dir / "meta.csv")
    meta = meta[(meta["set"] == st) & (meta["scenario"] == sc)].sort_values("rep").reset_index(drop=True)
    E = {}
    for f in sorted(mc_dir.glob(f"e__{st}__{sc}__*.npy")):
        E[f.stem.split("__")[-1]] = np.load(f)
    trig = pd.read_parquet(mc_dir / "triggers.parquet")
    trig = trig[(trig["set"] == st) & (trig["scenario"] == sc)]
    return MCSet(E, meta, trig)


def block_ids(m: C.Market) -> np.ndarray:
    yr = m.eval_dates.year.to_numpy()
    bid = np.full(yr.size, -1, dtype=np.int64)
    for j, y in enumerate(YEARS):
        bid[yr == y] = j
    return bid


class Engine:
    """백엔드 선택 (gpu 모듈이 import 되면 GPU)."""

    def __init__(self, prefer_gpu: bool = True) -> None:
        self.gpu = None
        if prefer_gpu:
            try:
                from . import gpu as G

                if G.torch.cuda.is_available():
                    self.gpu = G
            except Exception:
                self.gpu = None
        self.name = "gpu_torch_float64" if self.gpu else "cpu_numpy_float64"

    def rolling(self, E: np.ndarray, w: int, mask: np.ndarray | None) -> np.ndarray:
        if self.gpu is not None:
            T = self.gpu.rolling_cos_batch(E, w).cpu().numpy()
        else:
            T = np.stack([C.rolling_segmented(E[i], w, []) for i in range(E.shape[0])])
        return T if mask is None or not mask.any() else K.mask_crossing(T, mask, w)

    def page_block_hits(self, E, lam, H, mask, bid) -> np.ndarray:
        """(R, K, B) — 블록 내 ≥1 경보."""
        if self.gpu is not None:
            return self.gpu.page_block_hits(E, lam, H, mask, bid, len(YEARS)).cpu().numpy()
        out = np.zeros((E.shape[0], len(H), len(YEARS)), bool)
        for k, h in enumerate(H):
            al = C.page_alarm_batch(E, lam, h, mask)
            for j in range(len(YEARS)):
                out[:, k, j] = al[:, bid == j].any(axis=1)
        return out

    def page_alarm(self, E, lam, h, mask) -> np.ndarray:
        return C.page_alarm_batch(E, lam, h, mask)


def page_free_batch(E: np.ndarray, lam: float, mask: np.ndarray | None) -> np.ndarray:
    """경로 벡터화 자유 상태 S (경보 후 재설정 없음, 외부 초기화만) — ``core.page_free`` 의 배치판."""
    inc = C.page_increment(E, lam)
    R, n = E.shape
    s = np.zeros(R)
    seen = np.zeros(R, bool)
    S = np.full((R, n), np.nan)
    for t in range(n):
        if mask is not None:
            s = np.where(mask[:, t], 0.0, s)
        x = inc[:, t]
        ok = np.isfinite(x)
        s = np.where(ok, np.maximum(0.0, s + np.where(ok, x, 0.0)), s)
        seen |= ok
        S[seen, t] = s[seen]
    return S


def h_from_rates(rates: np.ndarray, H: np.ndarray, alpha: float) -> float:
    """블록 경보율이 α 이하가 되는 가장 작은 h (격자)."""
    ok = np.flatnonzero(rates <= alpha)
    return float(H[ok[0]]) if ok.size else np.nan


def two_sided_h(hu_hits: np.ndarray, hd_hits: np.ndarray, H: np.ndarray, alpha: float) -> tuple[float, float, float]:
    """단측 경보율을 같게 두고 합집합 경보율 ≤ α 인 최대 단측 수준."""
    ru, rd = hu_hits.mean(axis=(0, 2)), hd_hits.mean(axis=(0, 2))
    best = (np.nan, np.nan, np.nan)
    for a1 in np.linspace(alpha / 2, alpha, 401):
        ku, kd = np.flatnonzero(ru <= a1), np.flatnonzero(rd <= a1)
        if not ku.size or not kd.size:
            continue
        u = (hu_hits[:, ku[0], :] | hd_hits[:, kd[0], :]).mean()
        if u <= alpha:
            best = (float(H[ku[0]]), float(H[kd[0]]), float(u))
    return best


def null_table(T: np.ndarray, bid: np.ndarray) -> dict:
    """귀무 일별 T (2021–2025 블록 위치) 분위표와 블록 최대 표본."""
    v = T[:, bid >= 0]
    v = v[np.isfinite(v)]
    bm = C.block_max(T, [bid == j for j in range(len(YEARS))]).ravel()
    bm = np.sort(bm[np.isfinite(bm)])
    return {"qtab": np.quantile(v, QTAB) if v.size else np.full(QTAB.size, np.nan), "n_daily": int(v.size), "bmax": bm}


def tail_prob(x: np.ndarray, qtab: np.ndarray) -> np.ndarray:
    """분위표 보간으로 P(T_null ≥ x) (서술용 descriptive_raw_p)."""
    out = np.full(np.shape(x), np.nan)
    ok = np.isfinite(x)
    if not np.isfinite(qtab).all():
        return out
    cdf = np.interp(np.asarray(x)[ok], qtab, QTAB, left=0.0, right=1.0)
    out[ok] = 1.0 - cdf
    return out


def bmax_prob(x: np.ndarray, bmax: np.ndarray) -> np.ndarray:
    """P(블록 최대_null ≥ x) — 블록 다중성 보정 p (``cusum_adjusted_pvalue``), (1+#)/(N+1)."""
    out = np.full(np.shape(x), np.nan)
    ok = np.isfinite(x)
    n = bmax.size
    if n == 0:
        return out
    ge = n - np.searchsorted(bmax, np.asarray(x)[ok], side="left")
    out[ok] = (1.0 + ge) / (n + 1.0)
    return out
