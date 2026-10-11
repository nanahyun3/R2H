"""두 사건 집합의 시간 근접 귀무검정 (원형 이동) 과 BH q 값.

원본: SA_ETF Track A ``src/r2h/research_a/event_matching.py`` 의 ``proximity_count``, ``circular_shift_test_fast``,
``bh_qvalues`` — 계산식 변경 없음 (서식·타입 힌트만). Track A 는 이 함수로 상관 사건 ↔ 가격 사건 근접을 검정했다
(46,000 검정, research/cross_asset_track_a.md). 임의의 사건 위치 배열(예: CUSUM 경보 vs 정답 사건)에 그대로 쓸 수 있다.

H0: 두 집합의 시간 배치는 무관 (각자의 군집 구조는 보존). P 위치 전체를 같은 offset 만큼 원형 이동.
T = ±max_lag 안에 P 가 있는 C 의 수. p = (1 + #{T* ≥ T}) / (B + 1) (단측).
주의: 둘 다 고변동 국면에 몰리는 공동 의존은 귀무에 남는다. 검정 간 강한 양의 의존 → BH 의 FDR 보장은 PRDS 가정에 기댄다.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def proximity_count(cpos: np.ndarray, ppos: np.ndarray, max_lag: int) -> int:
    """C 중 ±max_lag 안에 P 가 하나라도 있는 개수 (다대일 허용)."""
    if len(cpos) == 0 or len(ppos) == 0:
        return 0
    ps = np.sort(ppos)
    lo = np.searchsorted(ps, cpos - max_lag, side="left")
    hi = np.searchsorted(ps, cpos + max_lag, side="right")
    return int((hi > lo).sum())


def circular_shift_test_fast(
    cpos: np.ndarray,
    ppos: np.ndarray,
    n: int,
    max_lag: int,
    B: int = 1000,
    seed: int = 20261011,
    min_shift: int | None = None,
) -> dict[str, Any]:
    """B 개 원형 이동을 한 번의 searchsorted 로 계산. shift u ~ U{min_shift, …, n−min_shift−1}."""
    cpos = np.asarray(cpos, int)
    ppos = np.asarray(ppos, int)
    t_obs = proximity_count(cpos, ppos, max_lag)
    if len(cpos) == 0 or len(ppos) == 0:
        return {
            "T_obs": t_obs,
            "T_null_mean": 0.0,
            "T_null_p95": 0.0,
            "p_value": 1.0,
            "B": B,
            "seed": seed,
            "n_C": len(cpos),
            "n_P": len(ppos),
            "ratio_obs_null": np.nan,
        }
    ms = min_shift if min_shift is not None else 2 * max_lag + 1
    rng = np.random.default_rng(seed)
    us = rng.integers(ms, n - ms, size=B)
    off = (np.arange(B) * 4 * n)[:, None]
    P = np.sort((ppos[None, :] + us[:, None]) % n, axis=1) + off
    flat = P.ravel()
    lo = np.searchsorted(flat, (cpos[None, :] - max_lag + off).ravel(), side="left").reshape(B, -1)
    hi = np.searchsorted(flat, (cpos[None, :] + max_lag + off).ravel(), side="right").reshape(B, -1)
    null = (hi > lo).sum(axis=1)
    return {
        "T_obs": t_obs,
        "T_null_mean": float(null.mean()),
        "T_null_p95": float(np.quantile(null, 0.95)),
        "p_value": float((1 + (null >= t_obs).sum()) / (B + 1)),
        "B": B,
        "seed": seed,
        "n_C": len(cpos),
        "n_P": len(ppos),
        "ratio_obs_null": float(t_obs / null.mean()) if null.mean() > 0 else np.nan,
    }


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg q 값 (탐색적 다중비교 보정)."""
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = p[o] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[o] = np.minimum(q, 1)
    return out
