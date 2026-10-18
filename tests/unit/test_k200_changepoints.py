"""E4 변화점 규칙 단위 시험: 미래 정보 누출 없음 · 수작업 계산 일치 · 에지/불응기 · 최소 과거 수 · 효과일."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from r2h.k200_controlled import changepoints as cp


def _synthetic(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """GBM 비슷한 종가와 r = 100·Δlog (r[0]=NaN)."""
    rng = np.random.default_rng(seed)
    lr = rng.standard_t(5, n) * 0.01
    close = 20000.0 * np.exp(np.cumsum(lr))
    r = np.full(n, np.nan)
    r[1:] = 100.0 * np.diff(np.log(close))
    return close, r


def test_rule_ids_count_and_grid():
    ids = cp.rule_ids()
    assert len(ids) == 17 and len(set(ids)) == 17
    assert {"P5", "V20_two", "V20_up", "V20_down", "M5_20", "K60"} <= set(ids)
    assert len(cp.rule_grid()) == 34


# (a) 미래 정보 누출 없음 -------------------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_no_lookahead_scores_thresholds_triggers(seed):
    n = 600
    close, r = _synthetic(n, seed)
    base = cp.compute_scores(close, r)
    base_tr = cp.all_triggers(base, min_prior=60)
    rng = np.random.default_rng(100 + seed)
    for t in (150, 333, 480):
        c2, r2 = close.copy(), r.copy()
        # close 와 r 을 서로 독립적으로 t+1 이후 교란
        c2[t + 1 :] *= np.exp(rng.normal(0, 0.05, n - t - 1))
        r2[t + 1 :] = rng.normal(0, 5, n - t - 1)
        pert = cp.compute_scores(c2, r2)
        for col in base.columns:
            a = base[col].to_numpy()[: t + 1]
            b = pert[col].to_numpy()[: t + 1]
            if a.dtype == bool:
                assert np.array_equal(a, b), col
            else:
                assert np.array_equal(a, b, equal_nan=True), col
        for rid in cp.rule_ids():
            s1 = base[f"{rid}_strength"].to_numpy()
            s2 = pert[f"{rid}_strength"].to_numpy()
            th1, p1 = cp.expanding_threshold(s1, min_prior=60)
            th2, p2 = cp.expanding_threshold(s2, min_prior=60)
            assert np.array_equal(p1[: t + 1], p2[: t + 1], equal_nan=True)
            for q in cp.QUANTILES:
                assert np.array_equal(th1[q][: t + 1], th2[q][: t + 1], equal_nan=True)
        pert_tr = cp.all_triggers(pert, min_prior=60)
        a = base_tr[base_tr.trigger_pos <= t].reset_index(drop=True)
        b = pert_tr[pert_tr.trigger_pos <= t].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


# (b) 수작업 계산 ---------------------------------------------------------------


def test_P_slope_matches_polyfit():
    close, r = _synthetic(80, 3)
    sc = cp.compute_scores(close, r)
    lp = np.log(close)
    for L in cp.P_LENGTHS:
        t = 70
        x = np.arange(L)
        cur = np.polyfit(x, lp[t - L + 1 : t + 1], 1)[0]
        prev = np.polyfit(x, lp[t - 2 * L + 1 : t - L + 1], 1)[0]
        assert sc[f"P{L}_score"][t] == pytest.approx(cur - prev, rel=1e-9, abs=1e-14)
        assert sc[f"P{L}_strength"][t] == pytest.approx(abs(cur - prev), rel=1e-9, abs=1e-14)
        # 데이터 부족 → NaN
        assert np.isnan(sc[f"P{L}_score"][2 * L - 2])
        assert np.isfinite(sc[f"P{L}_score"][2 * L - 1])


def test_V_log_ratio_and_variants():
    close, r = _synthetic(200, 4)
    sc = cp.compute_scores(close, r)
    for L in cp.V_LENGTHS:
        t = 150
        s = np.log(np.var(r[t - L + 1 : t + 1], ddof=1) / np.var(r[t - 2 * L + 1 : t - L + 1], ddof=1))
        assert sc[f"V{L}_two_score"][t] == pytest.approx(s, rel=1e-10)
        assert sc[f"V{L}_two_strength"][t] == pytest.approx(abs(s), rel=1e-10)
        assert sc[f"V{L}_up_strength"][t] == pytest.approx(s, rel=1e-10)
        assert sc[f"V{L}_down_strength"][t] == pytest.approx(-s, rel=1e-10)
        # r[0]=NaN 이 창에 들어가면 NaN: 첫 유효 끝점 = 2L (r[1..2L])
        assert np.isnan(sc[f"V{L}_two_score"][2 * L - 1])
        assert np.isfinite(sc[f"V{L}_two_score"][2 * L])


def test_V_zero_variance_is_nan():
    close = np.full(40, 100.0)
    r = np.zeros(40)
    r[0] = np.nan
    sc = cp.compute_scores(close, r)
    assert sc["V5_two_score"].isna().all()


def test_M_gap_change_cross():
    close = np.array([10, 11, 12, 13, 12, 11, 10, 9, 10, 11, 12, 13], dtype=float)
    r = np.full(close.size, np.nan)
    r[1:] = 100 * np.diff(np.log(close))
    # 작은 쌍으로 수작업 확인을 위해 내부 도우미를 직접 쓴다
    sh, lg = 2, 4
    ma_s = pd.Series(close).rolling(sh).mean().to_numpy()
    ma_l = pd.Series(close).rolling(lg).mean().to_numpy()
    gap_ref = np.log(ma_s / ma_l)
    old = cp.M_PAIRS
    try:
        cp.M_PAIRS = ((sh, lg),)
        sc = cp.compute_scores(close, r)
    finally:
        cp.M_PAIRS = old
    gap = sc["M2_4_gap"].to_numpy()
    assert np.allclose(gap, gap_ref, equal_nan=True)
    ch_ref = gap_ref - np.concatenate(([np.nan] * sh, gap_ref[:-sh]))
    assert np.allclose(sc["M2_4_score"].to_numpy(), ch_ref, equal_nan=True)
    cross_ref = np.zeros(close.size, bool)
    for t in range(1, close.size):
        if np.isfinite(gap_ref[t]) and np.isfinite(gap_ref[t - 1]):
            cross_ref[t] = np.sign(gap_ref[t]) != np.sign(gap_ref[t - 1])
    assert np.array_equal(sc["M2_4_cross"].to_numpy(), cross_ref)
    assert cross_ref.any()


def test_M_default_pairs_match_rolling():
    close, r = _synthetic(150, 5)
    sc = cp.compute_scores(close, r)
    for sh, lg in cp.M_PAIRS:
        g = np.log(pd.Series(close).rolling(sh).mean() / pd.Series(close).rolling(lg).mean()).to_numpy()
        assert np.allclose(sc[f"M{sh}_{lg}_gap"].to_numpy(), g, equal_nan=True, rtol=1e-10)


def test_K_kurtosis_matches_scipy_and_winsor():
    close, r = _synthetic(400, 6)
    sc = cp.compute_scores(close, r)
    for L in cp.K_LENGTHS:
        t = 390
        cw, pw = r[t - L + 1 : t + 1], r[t - 2 * L + 1 : t - L + 1]
        ref = stats.kurtosis(cw, fisher=True, bias=True) - stats.kurtosis(pw, fisher=True, bias=True)
        assert sc[f"K{L}_score"][t] == pytest.approx(ref, rel=1e-9)
        assert sc[f"K{L}_strength"][t] == pytest.approx(abs(ref), rel=1e-9)

        def wk(x):
            lo, hi = np.quantile(x, [0.01, 0.99], method="linear")
            return stats.kurtosis(np.clip(x, lo, hi), fisher=True, bias=True)

        assert sc[f"K{L}_w_score"][t] == pytest.approx(wk(cw) - wk(pw), rel=1e-9)
        assert sc[f"K{L}_n_cur"][t] == L and sc[f"K{L}_n_prev"][t] == L
        assert np.isnan(sc[f"K{L}_score"][2 * L - 1])  # r[0]=NaN 포함
        assert np.isfinite(sc[f"K{L}_score"][2 * L])


def test_nan_in_window_gives_nan():
    close, r = _synthetic(300, 7)
    r[150] = np.nan
    sc = cp.compute_scores(close, r)
    assert np.isnan(sc["V20_two_score"][150])
    assert np.isnan(sc["V20_two_score"][150 + 39])  # 직전 창에 걸림
    assert np.isfinite(sc["V20_two_score"][150 + 40])
    assert sc["K60_n_cur"][150] == 59


# 임계값 -----------------------------------------------------------------------


def test_threshold_strictly_prior_quantile_and_pctile():
    rng = np.random.default_rng(8)
    s = rng.normal(size=300)
    thr, pct = cp.expanding_threshold(s, (0.95, 0.99), min_prior=120)
    for t in (120, 200, 299):
        past = s[:t]
        assert thr[0.95][t] == np.quantile(past, 0.95, method="linear")
        assert thr[0.99][t] == np.quantile(past, 0.99, method="linear")
        assert pct[t] == np.mean(past < s[t])
    assert np.isnan(thr[0.95][119]) and np.isnan(pct[119])


def test_nan_does_not_count_toward_min_prior():
    s = np.arange(300, dtype=float)
    s[::2] = np.nan  # 짝수 위치 NaN → 유한 과거 120개는 t=240 에서야
    thr, pct = cp.expanding_threshold(s, (0.95,), min_prior=120)
    assert np.isnan(thr[0.95][:240]).all()
    assert np.isfinite(thr[0.95][240])
    assert np.isnan(pct[240])  # s[240] 자체가 NaN
    assert np.isfinite(pct[241])


# (c) 에지 · 불응기 -------------------------------------------------------------


def _ex(pattern: str) -> np.ndarray:
    return np.array([c == "1" for c in pattern])


def test_edge_only_no_repeat():
    ex = _ex("0111100110")
    assert cp._edge_refractory(ex, 0).tolist() == [1, 7]


def test_refractory_gap_boundary():
    ex = _ex("0100000000010000000000")  # 에지 1, 11 (차 10), 21 은 없음
    assert cp._edge_refractory(ex, 10).tolist() == [1]  # 11−1=10 ≤ 10 → 무시
    assert cp._edge_refractory(ex, 9).tolist() == [1, 11]
    assert cp._edge_refractory(ex, 0).tolist() == [1, 11]


def test_ignored_edge_long_run_does_not_trigger_later():
    # 에지 1 채택, 에지 4 는 불응기(gap 5) 안 → 무시, 그 초과 구간이 15 까지 이어져도 트리거 없음
    ex = _ex("01001111111111110001")
    assert cp._edge_refractory(ex, 5).tolist() == [1, 19]


def test_refractory_counts_from_adopted_only():
    # 에지 0, 3(무시, gap 4), 6: 6−0=6 > 4 → 채택 (무시된 3 은 t_last 를 갱신하지 않음)
    ex = _ex("1010101")
    assert cp._edge_refractory(ex, 4).tolist() == [0, 6]
    assert cp._edge_refractory(ex, 1).tolist() == [0, 2, 4, 6]


def test_triggers_end_to_end_edge():
    s = np.zeros(200)
    s[:150] = np.linspace(0, 1, 150)[np.random.default_rng(9).permutation(150)]
    s[160:165] = 5.0  # 한 초과 구간
    s[170] = 50.0  # 과거에 5.0 이 다섯 개 들어가 q99 임계가 5.0 이 되므로 더 크게
    out = cp.triggers(s, 0.99, gap=0)
    assert out["trigger_idx"].tolist() == [160, 170]
    out = cp.triggers(s, 0.99, gap=10)
    assert out["trigger_idx"].tolist() == [160]
    assert out["exceed"][160] and not out["exceed"][159] and not out["exceed"][165]


# (d) 과거 < 120 → 트리거 없음 --------------------------------------------------


def test_no_trigger_before_min_prior():
    s = np.zeros(130)
    s[50] = 100.0  # 과거 50 → 임계 NaN
    s[125] = 100.0  # 과거 125 ≥ 120 → 트리거
    out = cp.triggers(s, 0.95, gap=0)
    assert out["trigger_idx"].tolist() == [125]
    assert not out["exceed"][:120].any()
    out = cp.triggers(np.full(119, 1.0), 0.95, gap=0)
    assert out["trigger_idx"].size == 0


# (e) 효과일 = 확정일 + 1 -------------------------------------------------------


def test_effect_is_trigger_plus_one_and_out_of_range():
    s = np.zeros(130)
    s[125] = 100.0
    s[129] = 100.0  # 마지막 날 → 효과일 범위 밖
    out = cp.triggers(s, 0.95, gap=0)
    assert out["trigger_idx"].tolist() == [125, 129]
    assert out["effect_idx"].tolist() == [126]


def test_all_triggers_long_format():
    close, r = _synthetic(700, 10)
    sc = cp.compute_scores(close, r)
    tr = cp.all_triggers(sc)
    assert list(tr.columns) == ["rule", "q", "gap", "trigger_pos", "effect_pos", "strength", "thr", "pctile", "direction"]
    assert set(tr.rule) <= set(cp.rule_ids())
    ok = tr.effect_pos.notna()
    assert (tr.effect_pos[ok].astype(int) == tr.trigger_pos[ok] + 1).all()
    assert (tr.strength > tr.thr).all()
    # 단일 호출 API 와 일치
    one = cp.triggers(sc["V20_two_strength"].to_numpy(), 0.99, 20)
    sub = tr[(tr.rule == "V20_two") & (tr.q == 0.99) & (tr.gap == 20)]
    assert sub.trigger_pos.tolist() == one["trigger_idx"].tolist()
    # gap 이 클수록 트리거는 부분집합
    for rid in cp.rule_ids():
        for q in cp.QUANTILES:
            a = set(tr[(tr.rule == rid) & (tr.q == q) & (tr.gap == 0)].trigger_pos)
            b = set(tr[(tr.rule == rid) & (tr.q == q) & (tr.gap == 20)].trigger_pos)
            assert b <= a
