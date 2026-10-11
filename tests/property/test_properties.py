"""속성·변형(metamorphic) 테스트."""

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from r2h.detection import VolScaledThreshold
from r2h.detection.paper2020_cusum import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.evaluation import MatchConfig, bh_qvalues, match_alarms
from r2h.features import rolling_corr, vol_scaled_return

finite = st.floats(-0.2, 0.2, allow_nan=False, allow_infinity=False)


@settings(max_examples=60, deadline=None)
@given(arrays(float, st.integers(30, 120), elements=finite), st.floats(0.1, 50))
def test_vol_scaled_return_scale_invariant(r, c):
    s = pd.Series(r, index=pd.bdate_range("2024-01-01", periods=len(r)))
    a, b = vol_scaled_return(s, 10), vol_scaled_return(s * c, 10)
    # pandas' rolling std keeps running sums over the whole series: when a window's spread is tiny relative to
    # the largest value seen so far, the residue is version-dependent (documented in features/price.py).
    # Compare only well-conditioned windows: sigma > 1e-4 x running max |r|.
    run_max = s.abs().expanding().max().shift(1)
    sigma = s.rolling(10).std().shift(1)
    ok = a.notna() & b.notna() & (sigma > 1e-4 * run_max)
    np.testing.assert_allclose(a[ok], b[ok], rtol=1e-6, atol=1e-9)


@settings(max_examples=40, deadline=None)
@given(arrays(float, 60, elements=st.floats(-1, 1)), arrays(float, 60, elements=st.floats(-1, 1)))
def test_rolling_corr_bounded_and_symmetric(x, y):
    idx = pd.bdate_range("2024-01-01", periods=60)
    xs, ys = pd.Series(x, index=idx), pd.Series(y, index=idx)
    a, b = rolling_corr(xs, ys, 15)["rho"], rolling_corr(ys, xs, 15)["rho"]
    assert ((a.dropna() >= -1) & (a.dropna() <= 1)).all()
    np.testing.assert_allclose(a, b, equal_nan=True, atol=1e-12)


@settings(max_examples=60, deadline=None)
@given(arrays(float, st.integers(5, 200), elements=st.floats(-10, 10)), st.floats(0.01, 100))
def test_cusum_statistic_scale_invariant(e, c):
    tau = np.mean(e**4) - np.mean(e**2) ** 2
    if not np.isfinite(tau) or tau <= 1e-8:
        return
    kw = {"tie_policy": ArgmaxTiePolicy.FIRST, "degenerate_tau_policy": DegenerateTauPolicy.RAISE}
    a, b = cusum_squares_test(e, **kw), cusum_squares_test(e * c, **kw)
    assert np.isclose(a.statistic, b.statistic, rtol=1e-6)


@settings(max_examples=60, deadline=None)
@given(arrays(float, st.integers(1, 50), elements=st.floats(0, 1)))
def test_bh_monotone_and_bounded(p):
    q = bh_qvalues(p)
    assert ((q >= p - 1e-12) & (q <= 1)).all()
    o = np.argsort(p, kind="stable")
    assert (np.diff(q[o]) >= -1e-12).all()


@settings(max_examples=40, deadline=None)
@given(
    st.lists(st.integers(0, 199), unique=True, max_size=25),
    st.lists(st.integers(0, 190), unique=True, max_size=8),
    st.integers(0, 10),
    st.integers(0, 5),
)
def test_matching_conserves_counts(alarm_pos, ev_pos, max_delay, cooldown):
    cal = pd.bdate_range("2024-01-01", periods=200)
    al = pd.DataFrame(
        {"ticker": "A", "signal_at": cal[sorted(alarm_pos)], "score": 1.0, "is_alarm": True, "mode": "online"}
    )
    ev = pd.DataFrame(
        {
            "event_id": [f"e{i}" for i in range(len(ev_pos))],
            "ticker": "A",
            "event_start": cal[sorted(ev_pos)],
            "direction": 1,
        }
    )
    a, e = match_alarms(al, ev, cal, MatchConfig(max_delay=max_delay, cooldown=cooldown))
    assert len(a) == len(alarm_pos) and len(e) == len(ev_pos)
    assert (a["status"] == "TP").sum() == e["detected"].sum()
    assert (e.loc[e["detected"], "delay"].between(0, max_delay)).all()


def test_negative_control_iid_noise_false_alarm_rate_near_nominal():
    """iid 정규 잡음에서 z ≥ 3 경보율은 정규 꼬리 확률(≈0.00135)의 몇 배 안이어야 한다 (탐지 '성능' 아님)."""
    rng = np.random.default_rng(20261012)
    rates = []
    for _ in range(20):
        s = pd.Series(rng.normal(0, 0.01, 1500), index=pd.bdate_range("2010-01-01", periods=1500))
        out = VolScaledThreshold(window=60, k=3.0).run(s, ticker="N", data_version="v")
        rates.append(out["is_alarm"].iloc[61:].mean())
    assert 0.0005 < float(np.mean(rates)) < 0.004
