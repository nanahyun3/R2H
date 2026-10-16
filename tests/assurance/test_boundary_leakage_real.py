"""A-2 Q1·Q2 — 실데이터(069500)에서 연도 경계 누수 직접 검사.

기존 tests/leakage/test_t12_no_future_information.py 는 합성 GARCH 로 '교란 연도보다 이전 연도 행' 만 본다.
여기서는 실데이터로 **교란한 그 연도 자체** 의 사전 결정값이 불변인지 본다.

교란: 2022-01-01 이후 일별 수익률에 일별 배율 U(0.3, 3) 을 곱한다 (seed 고정).
부호 반전은 쓰지 않는다 (입력이 r² 라 사실상 무교란이 된다).

불변이어야 하는 것 (연도 2022 는 교란 연도)
- 2020·2021 모든 결과표 행 (바이트)
- 2022 fit_summary (C, γ², ε, val_mae, history_hash, model_hash) — 연초 결정
- 2022 이동창 임계값 `pointwise_null_quantile` · 귀무 기대 에피소드 — 풀과 w, n_days 만의 함수
- 2022 연간 임계값 (iid_insample / block / normal) — n_test_residuals 가 같은 행만
변해야 하는 것 (교란이 실제로 작동했다는 대조): 2022 annual_T
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest
from _real import have_raw

pytestmark = pytest.mark.skipif(not have_raw(), reason="data/raw 없음 (원시 시세는 저장소 밖)")

pytest.importorskip("sklearn")

from r2h.annual_expanding.config import load_config  # noqa: E402
from r2h.annual_expanding.fit import fit_annual, forecast_year, standardize  # noqa: E402
from r2h.annual_expanding.folds import inner_split  # noqa: E402
from r2h.annual_expanding.worker import run_ticker  # noqa: E402
from r2h.svrgarch_etf.data import load_close_panel, percent_log_returns  # noqa: E402
from r2h.svrgarch_etf.rolling import rolling_cusum  # noqa: E402

from _real import RAW  # noqa: E402

TICKER = "069500"
CUT = pd.Timestamp("2022-01-01")
META = {"data_version": "a_assurance", "git_sha": "a_assurance", "code_sha": "a_assurance"}


def _cfg():
    cfg = copy.deepcopy(load_config())
    cfg["folds"]["test_calendar_years"] = [2020, 2021, 2022]
    cfg["cusum"]["windows"] = [20, 60]
    cfg["calibration"].update(iid_reps=300, normal_reps=300, block_reps=200, null_sims=20)
    return cfg


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("a_leak")
    panel = load_close_panel(str(RAW))  # raw_dir 명시 — 네트워크 경로 금지
    s = percent_log_returns(panel.close)[TICKER]
    rng = np.random.default_rng(20261016)
    s2 = s.copy()
    m = s2.index >= CUT
    s2[m] = s2[m] * rng.uniform(0.3, 3.0, int(m.sum()))
    cfg = _cfg()
    run_ticker(TICKER, s, cfg, tmp / "base", META)
    run_ticker(TICKER, s2, cfg, tmp / "pert", META)

    def load(tag):
        d = tmp / tag / TICKER
        return {p.stem: pd.read_csv(p, dtype={"ticker": str}) for p in sorted(d.glob("*.csv"))}

    return load("base"), load("pert"), s, s2


def test_years_before_perturbation_identical(runs):
    base, pert, *_ = runs
    for name in base:
        a = base[name][base[name].year < 2022].reset_index(drop=True)
        b = pert[name][pert[name].year < 2022].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_exact=True, obj=name)


def test_perturbed_year_fit_is_preyear_decision(runs):
    base, pert, *_ = runs
    cols = ["history_strategy", "C", "gamma_squared", "epsilon", "val_mae", "n_history", "history_hash", "model_hash"]
    a = base["fit_summary"].query("year == 2022")[cols].reset_index(drop=True)
    b = pert["fit_summary"].query("year == 2022")[cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_perturbed_year_thresholds_are_preyear_decision(runs):
    base, pert, *_ = runs
    key = ["policy", "window", "boundary_mode", "calibration_method"]
    a = base["annual_cusum_diagnostics"].query("year == 2022").set_index(key).sort_index()
    b = pert["annual_cusum_diagnostics"].query("year == 2022").set_index(key).sort_index()
    for c in ("pointwise_null_quantile", "expected_null_episodes", "null_prob_any_episode", "calibration_cutoff"):
        pd.testing.assert_series_equal(a[c], b[c], check_exact=True, obj=c)

    k2 = ["policy", "calibration_method"]
    pa = base["annual_posthoc"].query("year == 2022").set_index(k2).sort_index()
    pb = pert["annual_posthoc"].query("year == 2022").set_index(k2).sort_index()
    same_n = pa.n_test_residuals == pb.n_test_residuals
    assert same_n.sum() >= 10  # 비양수 분산 변화로 n 이 바뀐 행만 비교에서 빠진다
    pd.testing.assert_series_equal(pa.annual_critical[same_n], pb.annual_critical[same_n], check_exact=True)
    # 대조: 교란은 실제로 그해 통계량을 바꾼다
    assert not np.allclose(pa.annual_T.to_numpy(float), pb.annual_T.to_numpy(float))


def test_within_year_prefix_invariance_real():
    panel = load_close_panel(str(RAW))
    s = percent_log_returns(panel.close)[TICKER].dropna()
    hist = s[s.index < "2023-01-01"].to_numpy()
    test = s[(s.index >= "2023-01-01") & (s.index < "2024-01-01")].to_numpy()
    n_tr, _ = inner_split(hist.size, _cfg())
    af = fit_annual(hist, n_tr)
    t_cut = 100
    test2 = test.copy()
    test2[t_cut + 1 :] *= np.random.default_rng(7).uniform(0.3, 3.0, test.size - t_cut - 1)
    for pol in ("A", "B"):
        v1, v2 = forecast_year(af.fit, hist, test, pol), forecast_year(af.fit, hist, test2, pol)
        np.testing.assert_array_equal(v1[: t_cut + 2], v2[: t_cut + 2])  # t 일 예측은 t−1 까지
        assert not np.array_equal(v1, v2)
        e1, e2 = standardize(test, v1), standardize(test2, v2)
        np.testing.assert_array_equal(e1[: t_cut + 1], e2[: t_cut + 1])
        np.testing.assert_array_equal(rolling_cusum(e1, 60)[: t_cut + 1], rolling_cusum(e2, 60)[: t_cut + 1])
