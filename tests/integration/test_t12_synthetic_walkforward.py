"""T12 통합 테스트 — 합성 ETF 1종 walk-forward 산출물 계약 · 정책 parity · 이력 상태 (CI 안전)."""

import copy

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from r2h.annual_expanding.config import load_config
from r2h.annual_expanding.fit import fit_annual, forecast_year, insample_variance
from r2h.annual_expanding.folds import inner_split
from r2h.annual_expanding.worker import run_ticker
from r2h.paper2020 import svr_garch as sg
from r2h.paper2020.volatility_proxy import BoundaryPolicy
from r2h.svrgarch_etf.model import M, P, Q

META = {"data_version": "syn", "git_sha": "test", "code_sha": "test"}


def small_cfg():
    cfg = copy.deepcopy(load_config())
    cfg["folds"]["test_calendar_years"] = [2020, 2021, 2022]
    cfg["cusum"]["windows"] = [20, 60]
    cfg["calibration"].update(iid_reps=300, normal_reps=300, block_reps=200, null_sims=20)
    return cfg


def garch_series(start="2019-01-02", end="2022-12-30", seed=1):
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    n = len(idx)
    h, r = np.ones(n), np.empty(n)
    for t in range(n):
        if t:
            h[t] = 0.05 + 0.08 * r[t - 1] ** 2 + 0.9 * h[t - 1]
        r[t] = np.sqrt(h[t]) * rng.standard_normal()
    return pd.Series(r, index=idx, name="SYN")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("t12int")
    run_ticker("SYN", garch_series(), small_cfg(), tmp, META)
    return tmp / "SYN"


def test_every_table_written_with_expected_rows(out):
    cfg = small_cfg()
    ny, nw = len(cfg["folds"]["test_calendar_years"]), len(cfg["cusum"]["windows"])
    assert len(pd.read_csv(out / "annual_vol_diagnostics.csv")) == ny
    assert len(pd.read_csv(out / "annual_forecast_diagnostics.csv")) == ny * 3
    assert len(pd.read_csv(out / "annual_posthoc.csv")) == ny * 3 * 5
    assert len(pd.read_csv(out / "annual_cusum_diagnostics.csv")) == ny * 3 * nw * 2 * 5
    assert len(pd.read_csv(out / "annual_history_ablation.csv")) == ny * 2 * 3
    assert (out / "daily.csv.gz").exists() and (out / "DONE.json").exists()


def test_history_states_follow_protocol(out):
    ab = pd.read_csv(out / "annual_history_ablation.csv").set_index(["year", "policy", "history_strategy"])
    assert ab.loc[(2020, "A", "trailing_2y"), "h_status"] == "SKIP_INSUFFICIENT_HISTORY"
    assert ab.loc[(2020, "A", "frozen_2019"), "h_status"] == "IDENTICAL_TO_EXPANDING"
    assert ab.loc[(2021, "A", "trailing_2y"), "h_status"] == "IDENTICAL_TO_EXPANDING"
    assert ab.loc[(2021, "A", "frozen_2019"), "h_status"] == "COMPUTED"
    assert ab.loc[(2022, "B", "trailing_2y"), "h_status"] == "COMPUTED"
    # frozen_2019 는 2020 fold 모형과 같은 해시
    fs = pd.read_csv(out / "fit_summary.csv").set_index(["year", "history_strategy"])
    assert fs.loc[(2022, "frozen_2019"), "model_hash"] == fs.loc[(2020, "expanding"), "model_hash"]


def test_prequential_not_estimable_in_first_year_and_w252_no_full_window(out):
    ph = pd.read_csv(out / "annual_posthoc.csv")
    first = ph[(ph.year == 2020) & (ph.calibration_method == "iid_prequential")]
    assert (first.calibration_status == "NOT_ESTIMABLE").all() and first.annual_critical.isna().all()
    later = ph[(ph.year == 2021) & (ph.calibration_method == "iid_prequential")]
    assert later.annual_critical.notna().all()


def test_policy_a_carry_equals_whole_series_reset_like_t11():
    """T11 검사와 같은 parity: 검정연도 A 분산 = 전체 경로에 RESET 으로 고정 ĝ 적용한 값."""
    s = garch_series().to_numpy()
    n_hist = 500
    af = fit_annual(s[:n_hist], inner_split(n_hist, small_cfg())[0])
    a = forecast_year(af.fit, s[:n_hist], s[n_hist : n_hist + 200], "A")
    whole = sg.forecast_test_variance(
        af.fit,
        s[: n_hist + 200],
        m=M,
        p=P,
        q=Q,
        input_policy=sg.TestVarianceInputPolicy.OBSERVED_PROXY,
        proxy_boundary=BoundaryPolicy.RESET,
        lag_boundary=BoundaryPolicy.RESET,
        prediction_policy=sg.VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    v = np.full(n_hist + 200, np.nan)
    v[whole.test_indices] = whole.variance
    np.testing.assert_allclose(a, v[n_hist:], rtol=1e-12, atol=1e-12)
    ins = insample_variance(af.fit, s[:n_hist])
    np.testing.assert_allclose(ins[1:], v[1:n_hist], rtol=1e-12, atol=1e-12)


def test_cusum_rows_mark_cross_boundary_and_not_ground_truth(out):
    cu = pd.read_csv(out / "annual_cusum_diagnostics.csv")
    carry = cu[cu.boundary_mode == "CARRY"]
    assert carry.interpretation_status.str.contains("CROSS_BOUNDARY").all()
    assert cu.interpretation_status.str.contains("not_ground_truth").all()
    w60 = cu[(cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED")]
    assert (w60.n_pure_oos_days == w60.n_mask_days).all()
