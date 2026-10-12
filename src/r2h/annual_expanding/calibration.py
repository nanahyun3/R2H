"""임계값 · 귀무 기대 경보 · 연간/이동창 CUSUM 요약 (PROTOCOL_LOCK L4·L5).

모든 임계값은 검정연도 이전 정보(풀)와 키 기반 seed 로만 만든다. 이동창 임계값은 **점별** 95% 분위이며
연간 경보 확률이나 ARL₀ 를 뜻하지 않는다.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from ..paper2020 import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from ..svrgarch_etf.rolling import episodes, iid_stats, rolling_cusum


def _finite(pool: np.ndarray) -> np.ndarray:
    p = np.asarray(pool, float)
    return p[np.isfinite(p)]


def draws_iid(pool: np.ndarray, n: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    return rng.choice(_finite(pool), size=(reps, n), replace=True)


def draws_block(pool: np.ndarray, n: int, reps: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """순환 이동 블록 부트스트랩 — 풀의 단기 의존을 보존하는 **다른 귀무** (C-09)."""
    p = _finite(pool)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, p.size, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % p.size
    return p[idx.reshape(reps, nb * block)[:, :n]]


def draws_normal(n: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal((reps, n))


def critical_from_draws(draws: np.ndarray, q: float) -> float:
    return float(np.nanquantile(iid_stats(draws), q))


def pure_window_stats(x: np.ndarray, w: int) -> np.ndarray:
    """행 = 시뮬레이션 (결측 없음). 반환 (sims, n−w+1) — 창 전체가 표본 안에 든 날의 통계량."""
    sims, n = x.shape
    if n < w:
        return np.empty((sims, 0))
    win = sliding_window_view(x, w, axis=1)  # (sims, n−w+1, w)
    return iid_stats(win.reshape(-1, w)).reshape(sims, n - w + 1)


def null_episode_rate(draws: np.ndarray, w: int, crit: float, gap: int) -> tuple[float, float]:
    """귀무 표본(행)에서 PURE 창 에피소드 수 평균 · 연중 ≥1 에피소드 확률."""
    st = pure_window_stats(draws, w)
    if st.shape[1] == 0:
        return float("nan"), float("nan")
    counts = np.array([len(episodes(row >= crit, gap=gap)) for row in st])
    return float(counts.mean()), float(np.mean(counts > 0))


def posthoc(e: np.ndarray) -> dict[str, Any]:
    """연간 사후 CUSUM — 해당 연도 유효 잔차만. k̂ 는 argmax 위치 (기각 아니면 변화점 아님)."""
    x = np.asarray(e, float)
    keep = np.flatnonzero(np.isfinite(x))
    if keep.size < 30:
        return {"annual_T": np.nan, "khat_pos": None, "n_test_residuals": int(keep.size)}
    res = cusum_squares_test(
        x[keep], tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RETURN_NAN
    )
    k = None if res.change_index_one_based is None else int(keep[res.change_index_one_based - 1])
    return {"annual_T": float(res.statistic), "khat_pos": k, "n_test_residuals": int(keep.size)}


def rolling_with_context(pre: np.ndarray, test: np.ndarray, w: int) -> np.ndarray:
    """CARRY: 사전 연도 마지막 w−1 개 + 검정연도 → 검정연도 날짜의 통계량 (길이 = len(test))."""
    ctx = np.asarray(pre, float)[-(w - 1) :] if w > 1 else np.empty(0)
    joined = np.concatenate([ctx, np.asarray(test, float)])
    stat = rolling_cusum(joined, w)
    return stat[ctx.size :]


def summarize_alarms(stat: np.ndarray, mask: np.ndarray, crit: float, gap: int) -> dict[str, Any]:
    """mask 된 날만 경보로 센다 (mask 밖 = 없음). 통계량 NaN 인 날은 경보 아님."""
    s = np.where(mask, stat, np.nan)
    valid = np.isfinite(s)
    alarm = valid & (np.nan_to_num(s, nan=-np.inf) >= crit)
    eps = episodes(alarm, gap=gap)
    first = int(np.flatnonzero(alarm)[0]) if alarm.any() else None
    return {
        "n_valid_stat_days": int(valid.sum()),
        "rolling_peak_T": float(np.nanmax(s)) if valid.any() else np.nan,
        "rolling_alarm_days": int(alarm.sum()),
        "rolling_episodes": len(eps),
        "first_alarm_pos": first,
    }
