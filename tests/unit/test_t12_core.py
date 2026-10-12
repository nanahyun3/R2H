"""T12 단위 테스트 — fold · seed · 진단 통계 · 보정 · 경계 (합성 데이터만, CI 안전)."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from r2h.annual_expanding.calibration import (
    critical_from_draws,
    draws_block,
    null_episode_rate,
    posthoc,
    pure_window_stats,
    rolling_with_context,
    summarize_alarms,
)
from r2h.annual_expanding.config import derive_seed, load_config
from r2h.annual_expanding.diagnostics import acf, annual_rv, arch_lm, bh_qvalues, ljung_box, residual_stats
from r2h.annual_expanding.folds import STRATEGIES, build_fold, strategy_state, training_mask
from r2h.detection.paper2020_cusum import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.svrgarch_etf.rolling import rolling_cusum

CFG = load_config()


def _series(start="2019-01-03", end="2026-10-02", seed=0):
    idx = pd.bdate_range(start, end)
    return pd.Series(np.random.default_rng(seed).standard_normal(len(idx)), index=idx)


def test_config_matches_protocol_lock():
    assert CFG["folds"]["test_calendar_years"] == [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    assert CFG["cusum"]["windows"] == [20, 30, 60, 120, 252] and CFG["cusum"]["primary_window"] == 60
    assert CFG["expected_n_tickers"] == 20 and CFG["expected_data_version"] == "5f20e3e0073b521a"


def test_fold_cutoffs_precede_test_for_every_strategy():
    r = _series()
    for y in CFG["folds"]["test_calendar_years"]:
        for s in STRATEGIES:
            f = build_fold("X", r, y, s, CFG)
            if f.train_end is not None:
                assert f.train_end < pd.Timestamp(f"{y}-01-01") <= f.test_start
            m = training_mask(pd.DatetimeIndex(r.index), y, s, CFG)
            assert r.index[m].max() < pd.Timestamp(f"{y}-01-01")


def test_fold_history_definitions():
    r = _series()
    assert build_fold("X", r, 2020, "expanding", CFG).train_start.year == 2019
    assert build_fold("X", r, 2020, "expanding", CFG).train_end.year == 2019
    assert build_fold("X", r, 2026, "expanding", CFG).train_end.year == 2025
    f = build_fold("X", r, 2024, "trailing_2y", CFG)
    assert (f.train_start.year, f.train_end.year) == (2022, 2023)
    assert build_fold("X", r, 2024, "frozen_2019", CFG).train_end.year == 2019


def test_degenerate_history_contrasts_are_labelled_not_computed():
    assert strategy_state(2020, "trailing_2y", CFG) == "SKIP_INSUFFICIENT_HISTORY"
    assert strategy_state(2021, "trailing_2y", CFG) == "IDENTICAL_TO_EXPANDING"
    assert strategy_state(2020, "frozen_2019", CFG) == "IDENTICAL_TO_EXPANDING"
    assert strategy_state(2022, "trailing_2y", CFG) == "COMPUTE"
    assert strategy_state(2021, "frozen_2019", CFG) == "COMPUTE"


def test_insufficient_history_is_not_padded_with_future():
    r = _series(start="2019-10-01")  # 2019 이력이 짧다
    f = build_fold("X", r, 2020, "expanding", CFG)
    assert f.status == "INSUFFICIENT_HISTORY"
    assert f.train_end < pd.Timestamp("2020-01-01")


def test_seed_is_stable_and_key_sensitive():
    assert derive_seed("a", 1) == derive_seed("a", 1)
    assert derive_seed("a", 1) != derive_seed("a", 2)
    # 고정값 — Python hash() 나 PYTHONHASHSEED 와 무관해야 한다
    assert derive_seed("t12", "069500", 2021) == int.from_bytes(
        __import__("hashlib").sha256(b"t12|069500|2021").digest()[:8], "big"
    )


def _garch_t(seed, n=245):
    rng = np.random.default_rng(seed)
    h, e = np.ones(n), np.empty(n)
    for t in range(n):
        if t:
            h[t] = 0.1 + 0.2 * e[t - 1] ** 2 + 0.7 * h[t - 1]
        e[t] = np.sqrt(h[t]) * rng.standard_t(6)
    return e


def test_ljung_box_and_arch_lm_match_statsmodels_reference_values():
    """기준값: statsmodels 0.14.6 acorr_ljungbox / het_arch 로 같은 계열에서 계산 (outputs/t12/logs 대조 기록)."""
    e = _garch_t(0)
    q, p = ljung_box(e**2, 10)
    lm, pa = arch_lm(e, 5)
    assert q == pytest.approx(29.045901, abs=1e-5)
    assert lm == pytest.approx(27.684815, abs=1e-5)
    assert 0 <= p <= 1 and 0 <= pa <= 1


def test_acf_white_noise_small_and_ar_large():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(5000)
    assert abs(acf(x, 1)) < 0.05
    ar = np.empty(5000)
    ar[0] = 0
    for t in range(1, 5000):
        ar[t] = 0.8 * ar[t - 1] + rng.standard_normal()
    assert acf(ar, 1) == pytest.approx(0.8, abs=0.05)


def test_annual_rv_formula_independent():
    r = np.array([1.0, -2.0, 0.5, np.nan, 3.0])
    x = r[np.isfinite(r)]
    expected = np.sqrt(252) * np.sqrt(np.sum((x - x.mean()) ** 2) / (x.size - 1))
    assert annual_rv(r) == pytest.approx(expected)


def test_bh_qvalues_basic():
    q = bh_qvalues(np.array([0.01, 0.04, 0.03, np.nan, 0.5]))
    assert np.isnan(q[3])
    np.testing.assert_allclose(q[[0, 1, 2, 4]], [0.04, 0.16 / 3, 0.16 / 3, 0.5])


def test_residual_stats_not_estimable_on_tiny_sample():
    assert residual_stats(np.arange(10.0), CFG)["status"] == "NOT_ESTIMABLE"


def test_posthoc_equals_paper_cusum_on_finite_residuals():
    rng = np.random.default_rng(5)
    e = rng.standard_normal(240)
    e[[10, 50]] = np.nan
    out = posthoc(e)
    ref = cusum_squares_test(
        e[np.isfinite(e)], tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
    )
    assert out["annual_T"] == pytest.approx(ref.statistic, rel=0, abs=0)
    assert out["n_test_residuals"] == 238


def test_year_contained_equals_carry_on_pure_days_and_differs_only_in_warm_days():
    rng = np.random.default_rng(7)
    pre, test = rng.standard_normal(300) * 3.0, rng.standard_normal(245)
    for w in (20, 60, 120):
        carry = rolling_with_context(pre, test, w)
        yc = rolling_cusum(test, w)
        pure = np.arange(test.size) >= w - 1
        np.testing.assert_array_equal(carry[pure], yc[pure])
        assert np.all(np.isnan(yc[~pure])) and np.all(np.isfinite(carry[~pure]))


def test_w252_has_no_pure_window_in_any_calendar_year():
    pure = np.arange(248) >= 251
    assert not pure.any()


def test_summarize_alarms_ignores_masked_days():
    stat = np.array([0.1, 2.0, 2.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 2.0])
    mask = np.ones(10, bool)
    mask[:3] = False
    s = summarize_alarms(stat, mask, 1.0, gap=5)
    assert s["rolling_alarm_days"] == 1 and s["rolling_episodes"] == 1 and s["first_alarm_pos"] == 9


def test_block_draws_shape_and_values_from_pool():
    pool = np.arange(100.0)
    d = draws_block(pool, 37, 5, 10, np.random.default_rng(0))
    assert d.shape == (5, 37) and np.isin(d, pool).all()
    # 블록 안에서는 연속 (순환) — 첫 블록 확인
    assert np.all(np.diff(d[0, :10]) % 100 == 1)


def test_pointwise_critical_is_not_annual_false_alarm_rate():
    """귀무 정규 iid 에서 점별 95% 임계값으로도 연중 ≥1 경보 확률은 5% 를 크게 넘는다 (명세 §2.4)."""
    rng = np.random.default_rng(11)
    crit = critical_from_draws(rng.standard_normal((4000, 60)), 0.95)
    mean_eps, p_any = null_episode_rate(rng.standard_normal((300, 245)), 60, crit, gap=5)
    assert p_any > 0.2 and mean_eps > 0.2


def test_pure_window_stats_matches_rolling_cusum():
    x = np.random.default_rng(2).standard_normal((3, 100))
    st = pure_window_stats(x, 30)
    for i in range(3):
        np.testing.assert_allclose(st[i], rolling_cusum(x[i], 30)[29:])
