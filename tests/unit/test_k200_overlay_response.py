"""12B 반응 분석 단위 시험 — 선행후행 부호 · 이벤트 단계 · NA 보존."""

from __future__ import annotations

import numpy as np
import pandas as pd

from r2h.k200_overlay import regimes as R
from r2h.k200_overlay import response as P


def test_lead_lag_sign_policy_lags_by_3() -> None:
    """정책이 시장보다 3일 늦으면 (policy[t] = market[t−3]) k=+3 에서 최대."""
    m = np.random.default_rng(0).standard_normal(600)
    p = np.r_[np.full(3, np.nan), m[:-3]]
    t = P.lead_lag(p, m)
    assert int(t.loc[t["rho"].abs().idxmax(), "lag_k"]) == 3
    assert np.isclose(t.loc[t.lag_k == 3, "rho"].iloc[0], 1.0)


def test_phase_edges() -> None:
    assert R.phase_of(-1, 10) == "pre" and R.phase_of(0, 10) == "onset" and R.phase_of(5, 10) == "onset"
    assert R.phase_of(6, 10) == "during" and R.phase_of(11, 10) == "normalization" and R.phase_of(51, 10) == "outside"
    assert R.phase_of(6, 0) == "normalization" and R.phase_of(-21, 0) == "outside"  # 1일 이벤트: during 없음


def test_event_aligned_nan_and_range_preserved() -> None:
    nd = 100
    mk = pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=nd), "annualized_vol_20": np.linspace(10, 20, nd)})
    meta = pd.DataFrame({"experiment_id": ["a"]})
    x = np.arange(nd, dtype=float)
    x[12] = np.nan
    M = {c: x[None, :].copy() for c in ("T_past_pct", "cusum_raw_T", "cusum_alarm_a05")}
    ev = pd.DataFrame({"interval_id": ["e"], "event_set": ["A_t20"], "period": ["PRIMARY"], "shock_type": ["누적형"],
                       "i_start": [10], "i_end": [15]})
    ea = P.event_aligned(meta, M, mk, ev)
    assert len(ea) == P.REL.size
    r = ea.set_index("rel")
    assert np.isnan(r.loc[2, "T_past_pct"])  # 원래 NaN 은 0 으로 바뀌지 않음
    assert not r.loc[-11, "in_range"] and np.isnan(r.loc[-11, "T_past_pct"])  # 날짜축 밖
    assert r.loc[-10, "T_past_pct"] == 0.0 and r.loc[3, "phase"] == "onset"


def test_spearman_constant_is_nan() -> None:
    rho, n = P.spearman(np.ones(50), np.arange(50.0))
    assert np.isnan(rho) and n == 50
