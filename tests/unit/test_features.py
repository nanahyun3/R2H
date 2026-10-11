import numpy as np
import pandas as pd
import pytest

from r2h.features import (
    RegimeRule,
    log_returns,
    moving_average,
    null_band,
    rolling_corr,
    rolling_volatility,
    sign_regimes,
    vol_scaled_return,
    volume_ratio,
)

IDX = pd.bdate_range("2024-01-01", periods=8)


def test_log_returns_first_row_nan_and_values():
    p = pd.Series([100.0, 110.0, 99.0], index=IDX[:3])
    r = log_returns(p)
    assert np.isnan(r.iloc[0])
    np.testing.assert_allclose(r.iloc[1:], [np.log(1.1), np.log(0.9)])


@pytest.mark.parametrize("bad", [0.0, -5.0])
def test_log_returns_rejects_nonpositive(bad):
    with pytest.raises(ValueError):
        log_returns(pd.Series([100.0, bad], index=IDX[:2]))


def test_log_returns_keeps_nan_gaps():
    r = log_returns(pd.Series([100.0, np.nan, 121.0], index=IDX[:3]))
    assert r.isna().sum() == 3  # diff across a gap is undefined


def test_rolling_window_warmup_1_to_n():
    r = pd.Series(np.arange(8, dtype=float), index=IDX)
    for w in range(2, 6):
        v = rolling_volatility(r, w)
        assert v.isna().sum() == w - 1
        assert rolling_volatility(r, w, exclude_current=True).isna().sum() == w
        assert moving_average(r, w).isna().sum() == w - 1


def test_min_periods_bounds():
    r = pd.Series(np.ones(8), index=IDX)
    with pytest.raises(ValueError):
        rolling_volatility(r, 3, min_periods=4)
    with pytest.raises(ValueError):
        moving_average(r, 0)


def test_zero_volatility_gives_nan_not_inf():
    r = pd.Series([0.01] * 6 + [0.05, 0.0], index=IDX)
    z = vol_scaled_return(r, window=3)
    assert not np.isinf(z).any()
    assert np.isnan(z.iloc[6])  # previous 3 returns constant → σ = 0


def test_volume_ratio_zero_base():
    v = pd.Series([0, 0, 0, 10, 20, 30, 40, 50], index=IDX, dtype=float)
    vr = volume_ratio(v, 3)
    assert np.isnan(vr.iloc[3])  # base mean of 3 zeros
    assert vr.iloc[6] == pytest.approx(40 / 20)


def test_vol_scaled_uses_previous_sigma_only():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(size=100), index=pd.bdate_range("2024-01-01", periods=100))
    z = vol_scaled_return(r, window=20)
    t = 50
    expected = r.iloc[t] / r.iloc[t - 20 : t].std(ddof=1)
    assert z.iloc[t] == pytest.approx(expected)


def test_rolling_corr_matches_pandas_and_flags_constant():
    rng = np.random.default_rng(2)
    idx = pd.bdate_range("2024-01-01", periods=80)
    x, y = pd.Series(rng.normal(size=80), index=idx), pd.Series(rng.normal(size=80), index=idx)
    out = rolling_corr(x, y, 20)
    np.testing.assert_allclose(out["rho"], x.rolling(20).corr(y), atol=1e-12, equal_nan=True)
    c = pd.Series(1.0, index=idx)
    oc = rolling_corr(x, c, 20)
    assert oc["rho"].isna().all() and oc["const"].iloc[19:].all()


def test_rolling_corr_pairwise_nan_and_spearman():
    idx = pd.bdate_range("2024-01-01", periods=30)
    x = pd.Series(np.arange(30, dtype=float), index=idx)
    y = x**3
    y.iloc[5] = np.nan
    out = rolling_corr(x, y, 10, method="spearman", min_periods=8)
    assert out["rho"].dropna().eq(1.0).all()
    assert out["n_eff"].iloc[10] == 9
    with pytest.raises(ValueError):
        rolling_corr(x, y.iloc[1:], 10)


def test_null_band():
    assert null_band(60) == pytest.approx(1.96 / np.sqrt(60))


def test_sign_regimes_confirm_lag_is_persist_minus_one():
    idx = pd.bdate_range("2024-01-01", periods=60)
    rho = pd.Series(np.r_[np.full(20, 0.5), np.full(20, -0.5), np.full(20, 0.5)], index=idx)
    ev = sign_regimes(rho, RegimeRule(band=0.1, persist=10))
    assert ev["is_initial"].tolist() == [True, False, False]
    assert (ev["confirm_lag_days"] == 9).all()
    assert ev["candidate_at"].iloc[1] == idx[20] and ev["confirmed_at"].iloc[1] == idx[29]
    assert ev["zero_cross_at"].iloc[1] == idx[20]


def test_sign_regimes_ignores_short_excursions():
    idx = pd.bdate_range("2024-01-01", periods=40)
    v = np.full(40, 0.4)
    v[15:20] = -0.4  # only 5 days below
    ev = sign_regimes(pd.Series(v, index=idx), RegimeRule(band=0.1, persist=10))
    assert len(ev) == 1 and bool(ev["is_initial"].iloc[0])
