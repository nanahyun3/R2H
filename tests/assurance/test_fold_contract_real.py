"""A-1/A-2 Q1 — fold 경계 계약을 원자료에서 독립 재계산해 결과표와 대조한다 (r2h 코드 미사용).

검사
1. 20종 종가 해시 = 기준
2. fold_manifest 420행 (20 ETF × 7 연도 × 3 전략) 의 날짜·표본 수·상태를 독립 계산값과 대조
3. fit_summary 의 history_hash = '검정연도 1월 1일 이전 유효 수익률만' 의 float64 해시
   → 연도 y 모형의 학습 입력에 y 이후 관측이 한 개도 없다는 직접 증거 (전략별)
"""

from __future__ import annotations

import pandas as pd
import pytest

from _real import RESULTS, array_hash16, close_hash_ok, have_raw, returns_panel, tickers

pytestmark = pytest.mark.skipif(not have_raw(), reason="data/raw 없음 (원시 시세는 저장소 밖)")

YEARS = range(2020, 2027)


@pytest.fixture(scope="module")
def r() -> pd.DataFrame:
    return returns_panel()


def _train_mask(dates: pd.DatetimeIndex, y: int, s: str):
    pre = dates < pd.Timestamp(f"{y}-01-01")
    if s == "expanding":
        return pre
    if s == "trailing_2y":
        return pre & (dates >= pd.Timestamp(f"{y - 2}-01-01"))
    if s == "frozen_2019":
        return dates < pd.Timestamp("2020-01-01")
    raise ValueError(s)


def _status(y: int, s: str) -> str:
    if s == "trailing_2y" and y - 2019 < 2:
        return "SKIP_INSUFFICIENT_HISTORY"
    if (s == "trailing_2y" and y - 2019 == 2) or (s == "frozen_2019" and y == 2020):
        return "IDENTICAL_TO_EXPANDING"
    return {2020: "PILOT_SHORT_HISTORY", 2026: "PARTIAL_NON_BLIND"}.get(y, "PRIMARY")


def test_close_hashes_match_reference():
    assert all(close_hash_ok(t) for t in tickers())


def test_return_panel_shape(r):
    assert r.shape == (1902, 20)
    assert str(r.index[0].date()) == "2019-01-03" and str(r.index[-1].date()) == "2026-10-02"
    assert int(r.isna().sum().sum()) == 2


def test_fold_manifest_matches_independent_recomputation(r):
    fm = pd.read_csv(RESULTS / "fold_manifest.csv", dtype={"ticker": str})
    assert len(fm) == 20 * 7 * 3
    fm = fm.set_index(["ticker", "year", "history_strategy"])
    n_checked = 0
    for t in tickers():
        v = r[t].dropna()
        d = pd.DatetimeIndex(v.index)
        for y in YEARS:
            test = d[(d >= pd.Timestamp(f"{y}-01-01")) & (d < pd.Timestamp(f"{y + 1}-01-01"))]
            for s in ("expanding", "trailing_2y", "frozen_2019"):
                row = fm.loc[(t, y, s)]
                st = _status(y, s)
                assert row.fold_status == st, (t, y, s)
                assert int(row.n_test) == len(test)
                assert bool(row.leak_check_train_end_lt_test_start)
                if st == "SKIP_INSUFFICIENT_HISTORY":
                    assert int(row.n_train_history) == 0
                    continue
                tr = d[_train_mask(d, y, s)]
                n_tr = round(0.7 * len(tr))
                assert int(row.n_train_history) == len(tr)
                assert int(row.n_inner_train) == n_tr and int(row.n_inner_val) == len(tr) - n_tr
                assert row.train_start == str(tr[0].date()) and row.train_end == str(tr[-1].date())
                assert row.test_start == str(test[0].date()) and row.test_end == str(test[-1].date())
                assert tr[-1] < test[0]
                assert n_tr >= 150 and len(tr) - n_tr >= 50
                n_checked += 1
    assert n_checked == 140 + 120 + 140  # expanding 140 + trailing_2y 120 (2020 skip 제외) + frozen_2019 140


def test_fit_history_hash_uses_only_pre_year_observations(r):
    fs = pd.read_csv(RESULTS / "fit_summary.csv", dtype={"ticker": str, "history_hash": str})
    n = 0
    for row in fs.itertuples():
        v = r[row.ticker].dropna()
        d = pd.DatetimeIndex(v.index)
        h = v.to_numpy(float)[_train_mask(d, int(row.year), row.history_strategy)]
        assert array_hash16(h) == row.history_hash, (row.ticker, row.year, row.history_strategy)
        assert int(row.n_history) == h.size
        assert pd.Timestamp(row.train_cutoff) < pd.Timestamp(f"{row.year}-01-01")
        n += 1
    # expanding 140 + trailing_2y 실제 대조 (2022–2026) 100 + frozen_2019 실제 대조 (2021–2026) 120
    assert n == 360
