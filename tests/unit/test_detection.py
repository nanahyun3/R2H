import numpy as np
import pandas as pd
import pytest

from r2h.detection import (
    SIGNAL_COLUMNS,
    Detector,
    PageCUSUM,
    PosthocCUSUMSquares,
    SignalContractViolation,
    VolScaledThreshold,
    params_hash,
    validate_signals,
)
from r2h.detection.paper2020_cusum import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test

IDX = pd.bdate_range("2024-01-01", periods=300)


def noise(seed: int = 0, n: int = 300) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(0, 0.01, n), index=IDX[:n])


@pytest.mark.parametrize("det", [VolScaledThreshold(), PageCUSUM(), PosthocCUSUMSquares()])
def test_detectors_satisfy_protocol_and_schema(det):
    assert isinstance(det, Detector)
    out = det.run(noise(), ticker="SYN", data_version="v")
    assert tuple(out.columns) == SIGNAL_COLUMNS
    assert out["is_alarm"].dtype == bool
    assert (out["params_hash"] == params_hash(det.params())).all()


def test_threshold_warmup_has_no_alarm_and_nan_score():
    out = VolScaledThreshold(window=60, k=3).run(noise(), ticker="SYN", data_version="v")
    head = out.iloc[:61]  # r_0 … r_60: σ_{t-1}(60) undefined until t = 60
    assert head["score"].iloc[:60].isna().all() and not head["is_alarm"].any()


def test_threshold_fires_on_spike_with_direction():
    r = noise()
    r.iloc[200] = 0.08
    up = VolScaledThreshold(k=4).run(r, ticker="SYN", data_version="v")
    down = VolScaledThreshold(k=4, direction=-1).run(r, ticker="SYN", data_version="v")
    assert bool(up["is_alarm"].iloc[200]) and not bool(down["is_alarm"].iloc[200])


def test_threshold_edge_equal_to_k_is_alarm():
    r = pd.Series([0.01, -0.01, 0.01, -0.01, 0.0], index=IDX[:5])
    sd = r.iloc[:4].std(ddof=1)
    r.iloc[4] = 2.0 * sd
    out = VolScaledThreshold(window=4, k=2.0).run(r, ticker="SYN", data_version="v")
    assert out["score"].iloc[4] == pytest.approx(2.0) and bool(out["is_alarm"].iloc[4])


def test_page_cusum_detects_mean_shift_and_resets():
    r = noise(3)
    r.iloc[150:170] += 0.02
    out = PageCUSUM(window=60, drift=0.5, threshold=5.0).run(r, ticker="SYN", data_version="v")
    hits = np.flatnonzero(out["is_alarm"].to_numpy())
    assert hits.size >= 1 and 150 <= hits[0] <= 160
    # after each alarm the statistic restarts from 0 (next score < threshold + max increment)
    s = out["score"].to_numpy()
    for h in hits:
        if h + 1 < len(s) and not np.isnan(s[h + 1]):
            assert s[h + 1] < 5.0


def test_page_cusum_rejects_bad_params():
    with pytest.raises(ValueError):
        PageCUSUM(threshold=0).run(noise(), ticker="SYN", data_version="v")


def test_detectors_reject_unsorted_index():
    r = noise().iloc[::-1]
    with pytest.raises(ValueError):
        VolScaledThreshold().run(r, ticker="SYN", data_version="v")
    with pytest.raises(TypeError):
        PageCUSUM().run(noise().reset_index(drop=True), ticker="SYN", data_version="v")


def test_posthoc_marks_mode_and_uses_full_sample():
    e = pd.Series(
        np.r_[
            np.random.default_rng(0).standard_normal(150), 3 * np.random.default_rng(1).standard_normal(150)
        ],
        index=IDX,
    )
    out = PosthocCUSUMSquares().run(e, ticker="SYN", data_version="v")
    assert len(out) == 1 and out["mode"].iat[0] == "posthoc"
    assert out["available_until"].iat[0] == IDX[-1] and out["signal_at"].iat[0] < IDX[-1]
    # argmax localisation is noisy at n=300; require the estimate within n/10 of the true break (seed-fixed: 171)
    assert bool(out["is_alarm"].iat[0]) and abs(IDX.get_loc(out["signal_at"].iat[0]) - 150) <= len(IDX) // 10


def test_paper_cusum_golden_vector():
    """Golden case carried over unchanged from SA_ETF Track B tests/test_core.py::test_cusum_golden."""
    res = cusum_squares_test(
        [1.0, 1.0, 1.0, 3.0],
        tie_policy=ArgmaxTiePolicy.FIRST,
        degenerate_tau_policy=DegenerateTauPolicy.RAISE,
    )
    np.testing.assert_allclose(res.centered_path, [-2.0, -4.0, -6.0, 0.0])
    assert res.tau_squared == pytest.approx(12.0)
    assert res.statistic == pytest.approx(0.8660254037844386)
    assert res.change_index_one_based == 3 and res.reject is False


def test_paper_cusum_degenerate_and_ties():
    with pytest.raises(ValueError):
        cusum_squares_test(
            np.ones(10), tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
        )
    nan_res = cusum_squares_test(
        np.ones(10), tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RETURN_NAN
    )
    assert np.isnan(nan_res.statistic) and nan_res.reject is False
    with pytest.raises(ValueError):
        cusum_squares_test(
            [1.0, 1.0, 1.0, 3.0, np.inf],
            tie_policy=ArgmaxTiePolicy.FIRST,
            degenerate_tau_policy=DegenerateTauPolicy.RAISE,
        )


def _sig(**over):
    base = {
        "ticker": ["A"],
        "signal_at": [IDX[5]],
        "score": [1.0],
        "is_alarm": [True],
        "method_id": ["m"],
        "mode": ["online"],
        "model_version": ["0"],
        "data_version": ["v"],
        "available_until": [IDX[5]],
        "params_hash": ["h"],
    }
    base.update(over)
    return pd.DataFrame(base)


def test_signal_contract_violations():
    validate_signals(_sig())
    with pytest.raises(SignalContractViolation, match="future leakage"):
        validate_signals(_sig(available_until=[IDX[6]]))
    validate_signals(_sig(mode=["posthoc"], available_until=[IDX[6]]))  # allowed for posthoc
    with pytest.raises(SignalContractViolation, match="infinite"):
        validate_signals(_sig(score=[np.inf]))
    with pytest.raises(SignalContractViolation, match="NaN"):
        validate_signals(_sig(score=[np.nan]))
    with pytest.raises(SignalContractViolation, match="mode"):
        validate_signals(_sig(mode=["batch"]))
    with pytest.raises(SignalContractViolation, match="bool"):
        validate_signals(_sig(is_alarm=[1]))
    with pytest.raises(SignalContractViolation, match="duplicate"):
        validate_signals(pd.concat([_sig(), _sig()]))
    with pytest.raises(SignalContractViolation, match="missing"):
        validate_signals(_sig().drop(columns="params_hash"))


def test_params_hash_stable():
    assert params_hash({"a": 1, "b": 2.0}) == params_hash({"b": 2.0, "a": 1})
    assert params_hash({"a": 1}) != params_hash({"a": 2})
