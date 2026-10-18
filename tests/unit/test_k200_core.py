"""12번 핵심 계산 단위 시험 — 분할 이동 CoS · Page CUSUM · SVR 경로 일정 · 블록 임계값."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from r2h.k200_controlled import core as C
from r2h.svrgarch_etf.rolling import rolling_cusum


def _rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


def test_rolling_segmented_without_reset_equals_original() -> None:
    e = _rng().standard_normal(400)
    e[[10, 77, 200]] = np.nan
    for w in (20, 60):
        assert np.array_equal(C.rolling_segmented(e, w, []), rolling_cusum(e, w), equal_nan=True)


def test_rolling_reset_only_removes_coverage() -> None:
    """초기화 후 w−1 일만 NA 가 되고, 같은 창이 들어가는 날의 값은 그대로 (G1 의 일반형)."""
    e = _rng(1).standard_normal(500)
    w, resets = 60, [150, 320]
    T0, T1 = C.rolling_segmented(e, w, []), C.rolling_segmented(e, w, resets)
    na = np.zeros(500, bool)
    for r in resets:
        na[r : r + w - 1] = True
    assert np.isnan(T1[na]).all()
    ok = ~na & np.isfinite(T0)
    assert np.array_equal(T1[ok], T0[ok])


def test_days_since_reset() -> None:
    since, count = C.days_since_reset(10, [4, 7])
    assert since.tolist() == [0, 1, 2, 3, 0, 1, 2, 0, 1, 2]
    assert count.tolist() == [0, 0, 0, 0, 1, 1, 1, 2, 2, 2]


def test_page_single_equals_batch() -> None:
    E = _rng(2).standard_t(5, size=(5, 300))
    E[0, 50] = np.nan
    mask = np.zeros_like(E, dtype=bool)
    mask[:, 120] = True
    for lam, h in ((2.0, 4.0), (0.5, 3.0)):
        al_b = C.page_alarm_batch(E, lam, h, mask)
        for i in range(E.shape[0]):
            _, al = C.page_alarm(E[i], lam, h, [120])
            assert np.array_equal(al, al_b[i])


def test_page_free_codes_and_reset() -> None:
    e = np.array([3.0] + [0.0] * 8 + [3.0, 3.0, np.nan, 3.0])
    S, code = C.page_free(e, 2.0, [10])
    inc = C.page_increment(e, 2.0)
    assert S[0] == pytest.approx(max(0.0, inc[0]))
    assert code[10] == 2  # 외부 초기화
    assert S[10] == pytest.approx(inc[10])
    assert S[11] == S[10]  # NaN 은 상태 유지
    assert (code[1:9] == 1).any()  # 자연 0 복귀


def test_page_alarm_resets_after_alarm() -> None:
    e = np.full(20, 3.0)
    S, al = C.page_alarm(e, 2.0, 1.0)
    inc = C.page_increment(np.array([3.0]), 2.0)[0]
    first = int(np.ceil(1.0 / inc)) - 1
    assert al[first] and not al[:first].any()
    assert S[first + 1] == pytest.approx(inc)


def test_block_quantile_hits_alpha() -> None:
    T = _rng(3).standard_normal((2000, 100))
    blocks = [np.arange(100) < 50, np.arange(100) >= 50]
    c = C.crit_block_alpha(T, blocks, 0.05)
    assert C.block_alarm_rate(T >= c, blocks) == pytest.approx(0.05, abs=0.002)


def test_calibrate_page_h_monotone_rate() -> None:
    E = _rng(4).standard_normal((400, 245))
    blocks = [np.ones(245, bool)]
    h = C.calibrate_page_h(E, 2.0, blocks, 0.2)
    rate = C.block_alarm_rate(C.page_alarm_batch(E, 2.0, h), blocks)
    assert rate <= 0.2 + 1e-12
    assert C.block_alarm_rate(C.page_alarm_batch(E, 2.0, h * 0.97), blocks) > rate - 1e-12


def test_scheduled_positions_annual_and_step() -> None:
    dates = pd.bdate_range("2019-01-02", "2021-12-31")
    m = C.market_from_returns(np.zeros(len(dates)), dates, int(np.searchsorted(dates, pd.Timestamp("2020-01-01"))))
    ann = C.scheduled_positions(m, "annual")
    assert ann[0] == 0 and len(ann) == 2 and m.eval_dates[ann[1]].year == 2021
    assert C.scheduled_positions(m, 63)[:3] == [0, 63, 126]


def test_svr_path_annual_equals_w3_contract() -> None:
    """연간·확장형 일반화 경로 = 연도별 fit_annual / forecast_year 직접 호출 (G2)."""
    from r2h.annual_expanding.fit import fit_annual, forecast_year, standardize

    rng = _rng(5)
    dates = pd.bdate_range("2019-01-02", "2021-12-31")
    r = rng.standard_normal(len(dates)) * (1 + 0.5 * np.sin(np.arange(len(dates)) / 40))
    es = int(np.searchsorted(dates, pd.Timestamp("2020-01-01")))
    m = C.market_from_returns(r, dates, es)
    p = C.svr_path(m, C.SVRPolicy())
    ref = []
    for y in (2020, 2021):
        pre = dates < pd.Timestamp(f"{y}-01-01")
        tm = (dates >= pd.Timestamp(f"{y}-01-01")) & (dates < pd.Timestamp(f"{y + 1}-01-01"))
        af = fit_annual(r[pre], round(0.7 * pre.sum()))
        ref.append(standardize(r[tm], forecast_year(af.fit, r[pre], r[tm], "A")))
    assert np.array_equal(p.e, np.concatenate(ref), equal_nan=True)


def test_trailing_window_truncation_flag() -> None:
    rng = _rng(6)
    dates = pd.bdate_range("2019-01-02", "2020-12-31")
    es = int(np.searchsorted(dates, pd.Timestamp("2020-01-01")))
    m = C.market_from_returns(rng.standard_normal(len(dates)), dates, es)
    p = C.svr_path(m, C.SVRPolicy(window=504))
    assert p.fits[0]["history_truncated"] and p.fits[0]["n_history"] == es
    q = C.svr_path(m, C.SVRPolicy())
    assert np.array_equal(p.e, q.e, equal_nan=True)  # 이력이 창보다 짧으면 확장형과 같다
