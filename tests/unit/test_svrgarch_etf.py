"""T11 모듈 테스트 — 합성 데이터만 (CI 안전). sklearn 이 없으면 건너뛴다 (research extra)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# sklearn 은 research extra — 없으면 모듈 전체를 건너뛰어야 하므로 import 보다 먼저 검사한다.
pytest.importorskip("sklearn")

from r2h.detection.paper2020_cusum import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.svrgarch_etf.data import close_sha256, percent_log_returns
from r2h.svrgarch_etf.events import high_vol_flag
from r2h.svrgarch_etf.model import baseline_residuals, fit_etf, fullsample_test
from r2h.svrgarch_etf.rolling import (
    bootstrap_critical_value,
    episodes,
    normal_critical_value,
    rolling_cusum,
    window_khat,
)

ROOT = Path(__file__).resolve().parents[2]
KW = {"tie_policy": ArgmaxTiePolicy.FIRST, "degenerate_tau_policy": DegenerateTauPolicy.RAISE}


def test_vendored_paper_modules_are_byte_identical_to_track_b():
    """SA_ETF research/track-b-paper2020@031157d 의 원본 sha256 과 같아야 한다 (출처 고정)."""
    expected = {
        "cusum.py": "bb686701639743abb1e6e36f31ae1223bc04b03ad419db1f48bc910374aac0fd",
        "svr_garch.py": "7ac250f2825cfd09d41667377033f1b93ebc90d67eca5a48d04e0d3e20d2f644",
        "volatility_proxy.py": "14437996130fc80f778e1cf94652c941b851c95c693a72dec4dfbf6a9944146c",
        "__init__.py": "9c1a26d4cfb8b8dfcd4cd5da22ece266d4992e0d8ea5f01627249a1c47a1e266",
    }
    for name, h in expected.items():
        got = hashlib.sha256((ROOT / "src/r2h/paper2020" / name).read_bytes()).hexdigest()
        assert got == h, name


def test_rolling_cusum_equals_paper_statistic_on_each_window():
    rng = np.random.default_rng(0)
    e = rng.standard_normal(200)
    stat = rolling_cusum(e, 60)
    for t in (59, 100, 199):
        ref = cusum_squares_test(e[t - 59 : t + 1], **KW).statistic
        assert stat[t] == pytest.approx(ref, rel=1e-12)
    assert np.isnan(stat[:59]).all()


def test_rolling_cusum_nan_equals_dropping_the_observation():
    rng = np.random.default_rng(1)
    e = rng.standard_normal(80)
    e[[65, 70]] = np.nan
    stat = rolling_cusum(e, 60)
    seg = e[20:80]
    ref = cusum_squares_test(seg[np.isfinite(seg)], **KW).statistic
    assert stat[79] == pytest.approx(ref, rel=1e-12)


def test_rolling_cusum_needs_90pct_valid_and_is_prefix_invariant():
    e = np.random.default_rng(2).standard_normal(120)
    e2 = e.copy()
    e2[50:60] = np.nan  # 창 60 안 결측 10개 → 유효 50 < 54
    assert np.isnan(rolling_cusum(e2, 60)[59:70]).any()
    f = e.copy()
    f[100:] = 50.0  # 미래 값 변경
    np.testing.assert_array_equal(rolling_cusum(e, 30)[:100], rolling_cusum(f, 30)[:100])


def test_critical_values_reproducible_and_ordered():
    assert normal_critical_value(30, reps=4000) == normal_critical_value(30, reps=4000)
    assert normal_critical_value(20, reps=4000) < normal_critical_value(252, reps=4000) < 1.40
    heavy = np.random.default_rng(3).standard_t(3, 2000)
    assert bootstrap_critical_value(heavy, 60, reps=2000) == bootstrap_critical_value(heavy, 60, reps=2000)


def test_episodes_merge_gap_and_window_khat():
    alarm = np.zeros(40, bool)
    alarm[[3, 4, 9, 30]] = True
    assert episodes(alarm, gap=5) == [(3, 9), (30, 30)]
    assert episodes(alarm, gap=3) == [(3, 4), (9, 9), (30, 30)]
    e = np.r_[np.ones(30), 3 * np.ones(30)] * np.random.default_rng(4).choice([-1, 1], 60)
    assert abs(window_khat(e, 59, 60) - 29) <= 1


def test_fit_etf_policy_a_matches_paper_protocol_and_detects_variance_break():
    rng = np.random.default_rng(5)
    r = pd.Series(
        np.r_[rng.standard_normal(700), 2.5 * rng.standard_normal(300)],
        index=pd.bdate_range("2015-01-01", periods=1000),
    )
    f = fit_etf("SYN", r)  # 내부에서 정책 A 전구간 경로 == 원문 CARRY 검정 경로 를 assert 한다
    assert f.n_fit == 700 and f.n_train == 490
    for pol in ("A", "B"):
        out = fullsample_test(f, pol)
        assert out["status"] == "ok" and out["n_test"] == 300
    e = f.residuals("A")
    assert np.isnan(e[0]) and np.isfinite(e[1:]).all()


def test_baseline_residuals_use_past_sigma_only():
    r = pd.Series(
        np.random.default_rng(6).standard_normal(200), index=pd.bdate_range("2020-01-01", periods=200)
    )
    z = baseline_residuals(r)
    assert z.iloc[100] == pytest.approx(r.iloc[100] / r.iloc[40:100].std(ddof=1))
    assert z.iloc[:40].isna().all()


def test_close_hash_and_returns():
    f = pd.DataFrame({"Date": ["2020-01-02", "2020-01-03"], "Close": ["100", "110"]})
    assert close_sha256(f) == hashlib.sha256(b"2020-01-02,100\n2020-01-03,110").hexdigest()
    close = pd.DataFrame(
        {"261240": [100.0, 101.0, 102.0]}, index=pd.to_datetime(["2019-03-13", "2019-03-14", "2019-03-15"])
    )
    r = percent_log_returns(close)
    assert r["261240"].isna().all()  # DQ 2일 제외
    with pytest.raises(ValueError):
        percent_log_returns(close * 0)


def test_high_vol_flag_is_past_only():
    rng = np.random.default_rng(7)
    c = pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600))), index=pd.bdate_range("2019-01-01", periods=600)
    )
    a = high_vol_flag(c)
    c2 = c.copy()
    c2.iloc[500:] *= np.exp(np.cumsum(rng.normal(0, 0.05, 100)))
    pd.testing.assert_series_equal(a.iloc[:500], high_vol_flag(c2).iloc[:500])
    assert not a.iloc[:270].any()  # 최소 250 관측 전에는 국면 판정 없음
