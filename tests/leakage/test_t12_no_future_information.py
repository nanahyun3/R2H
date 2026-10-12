"""T12 누수 테스트 — 미래 연도 교란 불변 · 연중 prefix 불변 · 보정 cutoff · RV 사후성 (명세 §8.1 #2–#4, §13 #1–#10)."""

import copy

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from r2h.annual_expanding.config import load_config
from r2h.annual_expanding.fit import fit_annual, forecast_year, standardize
from r2h.annual_expanding.folds import inner_split
from r2h.annual_expanding.worker import run_ticker
from r2h.svrgarch_etf.rolling import rolling_cusum


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


META = {"data_version": "syn", "git_sha": "test", "code_sha": "test"}


def _tables(tmp, s, cfg, tag):
    run_ticker("SYN", s, cfg, tmp / tag, META)
    return {p.name: p.read_bytes() for p in sorted((tmp / tag / "SYN").glob("*.csv"))}


@pytest.fixture(scope="module")
def base_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("t12")
    cfg = small_cfg()
    s = garch_series()
    return tmp, cfg, s, _tables(tmp, s, cfg, "base")


def _rows_before(data: bytes, year: int) -> list[str]:
    lines = data.decode().splitlines()
    head = lines[0].split(",")
    yi = head.index("year")
    return [ln for ln in lines[1:] if int(ln.split(",")[yi]) < year]


def test_future_year_perturbation_leaves_earlier_years_unchanged(base_run):
    tmp, cfg, s, base = base_run
    s2 = s.copy()
    s2[s2.index >= "2022-01-01"] *= -3.0  # 2022 이후 데이터 교란
    pert = _tables(tmp, s2, cfg, "pert")
    for name in base:
        assert _rows_before(base[name], 2022) == _rows_before(pert[name], 2022), name


def test_rerun_is_byte_identical(base_run):
    tmp, cfg, s, base = base_run
    assert _tables(tmp, s, cfg, "rerun") == base


def test_within_year_prefix_invariance_of_forecast_residual_and_rolling():
    s = garch_series()
    hist = s[s.index < "2021-01-01"].to_numpy()
    test = s[(s.index >= "2021-01-01") & (s.index < "2022-01-01")].to_numpy()
    n_tr, _ = inner_split(hist.size, small_cfg())
    af = fit_annual(hist, n_tr)
    t_cut = 120
    test2 = test.copy()
    test2[t_cut + 1 :] = np.random.default_rng(9).standard_normal(test.size - t_cut - 1) * 10
    for pol in ("A", "B"):
        v1, v2 = forecast_year(af.fit, hist, test, pol), forecast_year(af.fit, hist, test2, pol)
        # t 일 예측분산은 t−1 까지 → t_cut+1 일까지 동일
        np.testing.assert_array_equal(v1[: t_cut + 2], v2[: t_cut + 2])
        e1, e2 = standardize(test, v1), standardize(test2, v2)
        np.testing.assert_array_equal(e1[: t_cut + 1], e2[: t_cut + 1])
        r1, r2 = rolling_cusum(e1, 60), rolling_cusum(e2, 60)
        np.testing.assert_array_equal(r1[: t_cut + 1], r2[: t_cut + 1])


def test_calibration_and_training_cutoffs_precede_test(base_run):
    tmp, *_ = base_run
    d = tmp / "base" / "SYN"
    ph = pd.read_csv(d / "annual_posthoc.csv")
    assert (pd.to_datetime(ph.calibration_cutoff) < pd.to_datetime(ph.year.astype(str) + "-01-01")).all()
    fm = pd.read_csv(d / "fold_manifest.csv")
    assert fm.leak_check_train_end_lt_test_start.all()
    fs = pd.read_csv(d / "fit_summary.csv")
    assert (pd.to_datetime(fs.train_cutoff) < pd.to_datetime(fs.year.astype(str) + "-01-01")).all()


def test_realized_vol_is_ex_post_only(base_run):
    tmp, *_ = base_run
    vol = pd.read_csv(tmp / "base" / "SYN" / "annual_vol_diagnostics.csv")
    assert vol.known_at.str.contains("ex-post").all()
    # RV 는 다른 결과표의 입력이 아니다: 미래 RV 를 바꿔도 같은 해 진단·임계값이 불변인지는 위 교란 테스트가 보장
    for y, row in vol.set_index("year").iterrows():
        assert str(row.known_at).startswith(str(y))
