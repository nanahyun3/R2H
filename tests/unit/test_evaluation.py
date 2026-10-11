import numpy as np
import pandas as pd
import pytest

from r2h.evaluation import (
    GroundTruthViolation,
    MatchConfig,
    bh_qvalues,
    chronological_split,
    circular_shift_test_fast,
    event_metrics,
    match_alarms,
    proximity_count,
    recall_at_fp_cap,
    validate_ground_truth,
    walk_forward,
)

CAL = pd.bdate_range("2024-01-01", periods=100)


def alarms_at(positions, ticker="A", mode="online"):
    return pd.DataFrame(
        {
            "ticker": ticker,
            "signal_at": CAL[list(positions)],
            "score": 1.0,
            "is_alarm": True,
            "mode": mode,
        }
    )


def events_at(starts, ticker="A", length=5, direction=1):
    return pd.DataFrame(
        {
            "label_version": "t",
            "event_id": [f"{ticker}-{s}" for s in starts],
            "ticker": ticker,
            "event_start": CAL[list(starts)],
            "event_end": CAL[[s + length - 1 for s in starts]],
            "direction": direction,
            "threshold_definition": "x",
            "created_from_window": "x",
        }
    )


def test_tp_fp_fn_and_delay():
    a, e = match_alarms(alarms_at([12, 50, 90]), events_at([10, 40, 70]), CAL, MatchConfig(max_delay=5))
    assert a["status"].tolist() == ["TP", "FP", "FP"]
    assert e["detected"].tolist() == [True, False, False] and e["delay"].iloc[0] == 2
    m = event_metrics(a, e, ticker_years=1.0)
    assert (m.n_events, m.n_detected, m.n_missed, m.n_fp) == (3, 1, 2, 2)
    assert (
        m.recall == pytest.approx(1 / 3) and m.delay_mean == 2 and m.alarm_precision == pytest.approx(1 / 3)
    )


def test_multiple_alarms_same_event_are_duplicates_not_fp():
    a, e = match_alarms(alarms_at([10, 11, 13]), events_at([10]), CAL, MatchConfig(max_delay=5))
    assert a["status"].tolist() == ["TP", "DUPLICATE", "DUPLICATE"]
    assert event_metrics(a, e, 1.0).n_fp == 0


def test_cooldown_suppresses_before_matching():
    a, _ = match_alarms(
        alarms_at([30, 31, 32, 36]), events_at([80]), CAL, MatchConfig(max_delay=5, cooldown=3)
    )
    assert a["status"].tolist() == ["FP", "SUPPRESSED", "SUPPRESSED", "FP"]


def test_max_delay_boundary_inclusive_and_pre_tolerance():
    a, _ = match_alarms(alarms_at([15]), events_at([10]), CAL, MatchConfig(max_delay=5))
    assert a["status"].iat[0] == "TP"
    a, _ = match_alarms(alarms_at([16]), events_at([10]), CAL, MatchConfig(max_delay=5))
    assert a["status"].iat[0] == "FP"
    a, e = match_alarms(alarms_at([8]), events_at([10]), CAL, MatchConfig(max_delay=5, pre_tolerance=2))
    assert a["status"].iat[0] == "TP" and e["delay"].iat[0] == -2


def test_alarm_prefers_undetected_event_when_windows_overlap():
    a, e = match_alarms(alarms_at([12, 14]), events_at([10, 13]), CAL, MatchConfig(max_delay=5))
    assert a["status"].tolist() == ["TP", "TP"] and e["detected"].all()


def test_direction_filter_and_posthoc_rejected():
    ev = pd.concat([events_at([10]), events_at([50], direction=-1).assign(event_id="A-down")])
    _, e = match_alarms(alarms_at([11]), ev, CAL, MatchConfig(max_delay=5, direction=1))
    assert len(e) == 1
    with pytest.raises(ValueError, match="posthoc"):
        match_alarms(alarms_at([11], mode="posthoc"), ev, CAL, MatchConfig(max_delay=5))


def test_off_calendar_dates_rejected():
    al = alarms_at([1])
    al["signal_at"] = pd.Timestamp("2024-01-06")  # Saturday
    with pytest.raises(ValueError, match="calendar"):
        match_alarms(al, events_at([10]), CAL, MatchConfig(max_delay=5))


def test_no_events_and_no_alarms():
    a, e = match_alarms(alarms_at([]), events_at([]), CAL, MatchConfig(max_delay=5))
    m = event_metrics(a, e, 2.0)
    assert m.n_events == 0 and np.isnan(m.recall) and np.isnan(m.delay_mean) and m.fp_per_ticker_year == 0
    with pytest.raises(ValueError):
        event_metrics(a, e, 0.0)


def test_recall_at_fp_cap_selects_within_cap_only():
    a1, e1 = match_alarms(alarms_at([10, 40, 70, 90]), events_at([10, 40, 70]), CAL, MatchConfig(max_delay=2))
    a2, e2 = match_alarms(alarms_at([10]), events_at([10, 40, 70]), CAL, MatchConfig(max_delay=2))
    loose, tight = event_metrics(a1, e1, 1.0), event_metrics(a2, e2, 1.0)
    assert recall_at_fp_cap([(1.0, loose), (2.0, tight)], fp_cap=0.5) == (2.0, tight)
    assert recall_at_fp_cap([(1.0, loose), (2.0, tight)], fp_cap=1.0) == (1.0, loose)
    assert recall_at_fp_cap([(1.0, loose)], fp_cap=0.0) is None


def test_ground_truth_contract():
    validate_ground_truth(events_at([10, 20]))
    with pytest.raises(GroundTruthViolation, match="unique"):
        validate_ground_truth(pd.concat([events_at([10]), events_at([10])]))
    bad = events_at([10]).assign(direction=0)
    with pytest.raises(GroundTruthViolation, match="direction"):
        validate_ground_truth(bad)
    mixed = pd.concat([events_at([10]), events_at([20]).assign(label_version="u")])
    with pytest.raises(GroundTruthViolation, match="label versions"):
        validate_ground_truth(mixed)
    rev = events_at([10]).assign(event_end=CAL[[5]])
    with pytest.raises(GroundTruthViolation, match="before"):
        validate_ground_truth(rev)


def test_chronological_split_boundaries_and_overlap():
    idx = pd.bdate_range("2019-01-01", "2026-12-31")
    s = chronological_split(idx, {"dev": ("2019-01-01", "2024-12-31"), "val": ("2025-01-01", "2025-12-31")})
    assert idx[s["dev"][-1]] <= pd.Timestamp("2024-12-31") < idx[s["val"][0]]
    assert not set(s["dev"]) & set(s["val"])
    with pytest.raises(ValueError, match="overlaps"):
        chronological_split(idx, {"a": ("2019-01-01", "2020-01-10"), "b": ("2020-01-10", "2021-01-01")})


@pytest.mark.parametrize("expanding", [False, True])
def test_walk_forward_embargo_and_order(expanding):
    folds = list(walk_forward(100, train=30, test=10, embargo=5, expanding=expanding))
    assert folds
    for tr, te in folds:
        assert tr.max() + 5 < te.min() and te.max() < 100
    assert folds[0][0][0] == 0
    with pytest.raises(ValueError):
        list(walk_forward(100, train=0, test=10))


def test_proximity_and_circular_shift_deterministic():
    c, p = np.array([10, 50, 90]), np.array([11, 70])
    assert proximity_count(c, p, 1) == 1 and proximity_count(c, np.array([], int), 1) == 0
    r1 = circular_shift_test_fast(c, p, 200, 2, B=500, seed=7)
    r2 = circular_shift_test_fast(c, p, 200, 2, B=500, seed=7)
    assert r1 == r2 and 0 < r1["p_value"] <= 1
    assert circular_shift_test_fast(np.array([], int), p, 200, 2)["p_value"] == 1.0


def test_bh_qvalues_known_values():
    q = bh_qvalues(np.array([0.01, 0.04, 0.03, 0.2]))
    # sorted p (0.01, 0.03, 0.04, 0.2) → p·n/rank (0.04, 0.06, 0.0533, 0.2) → running min from the top
    np.testing.assert_allclose(q, [0.04, 0.16 / 3, 0.16 / 3, 0.2])
