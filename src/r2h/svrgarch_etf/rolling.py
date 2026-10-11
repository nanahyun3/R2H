"""이동창 CUSUM-of-squares — 원문 사후 검정을 길이 w 창에 반복 적용해 시점별 통계량을 만든다.

T_t(w) = max_k |Σ_{s≤k} ε²_s − (k/n) Σ ε²_s| / (√n · τ̂),  창 = [t−w+1, t] 의 유효 잔차 (과거만 → 실시간 계산 가능).
결측(NaN)은 그 관측을 건너뛴 것과 수학적으로 같게 처리한다 (유효 개수 누적 k 사용). 유효 관측 < 0.9w 이면 NaN.
임계값: 점근 1.3397 · 창 길이별 iid N(0,1) MC 95% · ETF 별 부트스트랩 95% (1차, D2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

WINDOWS: tuple[int, ...] = (20, 30, 60, 120, 252)
ASYMPTOTIC_5PCT = 1.3397
MIN_VALID_FRAC = 0.9
SEED = 20261012


def _window_stats(W: np.ndarray, min_valid: int) -> np.ndarray:
    """행 = 창. NaN 은 건너뛴 것과 동치. 반환: 창별 통계량 (유효 < min_valid 또는 τ̂≤0 → NaN)."""
    valid = ~np.isnan(W)
    sq = np.where(valid, W, 0.0) ** 2
    n = valid.sum(axis=1)
    k = np.cumsum(valid, axis=1)
    s = np.cumsum(sq, axis=1)
    total = s[:, -1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        path = s - k / n[:, None] * total
        m2 = total[:, 0] / n
        m4 = np.where(valid, W, 0.0) ** 4
        tau2 = m4.sum(axis=1) / n - m2**2
        peak = np.where(valid, np.abs(path), -np.inf).max(axis=1)  # NaN 위치는 최대값 후보에서 제외
        stat = peak / (np.sqrt(n) * np.sqrt(tau2))
    stat[(n < min_valid) | ~(tau2 > 0)] = np.nan
    return stat


def rolling_cusum(e: np.ndarray, w: int) -> np.ndarray:
    """시점 t 에 [t−w+1, t] 창 통계량. 앞 w−1 개는 NaN."""
    e = np.asarray(e, float)
    out = np.full(e.size, np.nan)
    if e.size < w:
        return out
    W = sliding_window_view(e, w)
    if np.isnan(W).all(axis=1).all():
        return out
    out[w - 1 :] = _window_stats(W, int(np.ceil(MIN_VALID_FRAC * w)))
    return out


def iid_stats(draws: np.ndarray) -> np.ndarray:
    """행마다 결측 없는 표본 → 통계량 (임계값 MC 용)."""
    return _window_stats(draws, draws.shape[1])


def normal_critical_value(w: int, reps: int = 20_000, q: float = 0.95, seed: int = SEED) -> float:
    rng = np.random.default_rng([seed, w])
    return float(np.nanquantile(iid_stats(rng.standard_normal((reps, w))), q))


def bootstrap_critical_value(
    resid: np.ndarray, w: int, reps: int = 5_000, q: float = 0.95, seed: int = SEED, salt: int = 0
) -> float:
    """적합 구간 잔차를 iid 재표집해 만든 길이 w 창의 95% 분위 (두꺼운 꼬리 반영)."""
    pool = np.asarray(resid, float)
    pool = pool[np.isfinite(pool)]
    rng = np.random.default_rng([seed, w, salt])
    return float(np.nanquantile(iid_stats(rng.choice(pool, size=(reps, w), replace=True)), q))


def null_alarm_episodes_per_year(
    resid: np.ndarray,
    w: int,
    crit: float,
    n: int,
    sims: int = 100,
    seed: int = SEED,
    salt: int = 0,
    gap: int = 5,
) -> float:
    """귀무(iid 재표집 잔차, 길이 n)에서 연간 경보 에피소드 기대값."""
    pool = np.asarray(resid, float)
    pool = pool[np.isfinite(pool)]
    rng = np.random.default_rng([seed, w, salt, 7])
    counts = []
    for _ in range(sims):
        stat = rolling_cusum(rng.choice(pool, size=n, replace=True), w)
        counts.append(len(episodes(np.nan_to_num(stat, nan=-np.inf) >= crit, gap=gap)))
    return float(np.mean(counts) / (n / 252))


def episodes(alarm: np.ndarray, gap: int = 5) -> list[tuple[int, int]]:
    """경보일 위치를 에피소드 (시작, 끝) 로 묶는다. 경보 사이 공백 ≤ gap 거래일이면 같은 에피소드."""
    pos = np.flatnonzero(np.asarray(alarm, bool))
    if pos.size == 0:
        return []
    out, start, prev = [], int(pos[0]), int(pos[0])
    for p in pos[1:]:
        if p - prev > gap + 1:
            out.append((start, prev))
            start = int(p)
        prev = int(p)
    out.append((start, prev))
    return out


def window_khat(e: np.ndarray, t: int, w: int) -> int | None:
    """시점 t 창 안의 사후 변화 위치 k̂ (전체 시계열 위치). 실시간 값이 아님."""
    seg = np.asarray(e[t - w + 1 : t + 1], float)
    idx = np.flatnonzero(np.isfinite(seg))
    if idx.size < 2:
        return None
    v = seg[idx] ** 2
    path = np.cumsum(v) - np.arange(1, v.size + 1) / v.size * v.sum()
    return int(t - w + 1 + idx[int(np.argmax(np.abs(path)))])


def yearly_blocks(dates: pd.DatetimeIndex, e: np.ndarray) -> pd.DataFrame:
    """달력연도마다 사후 CUSUM (D7)."""
    rows = []
    for y in sorted(set(dates.year)):
        m = np.asarray(dates.year == y)
        seg = e[m]
        stat = _window_stats(seg[None, :], int(np.ceil(MIN_VALID_FRAC * m.sum())))[0]
        k = window_khat(e, int(np.flatnonzero(m)[-1]), int(m.sum()))
        rows.append(
            {
                "year": y,
                "n": int(np.isfinite(seg).sum()),
                "T": stat,
                "khat_date": dates[k].date() if k is not None else None,
            }
        )
    return pd.DataFrame(rows)
