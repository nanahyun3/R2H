"""W2 계산 규칙 단위 테스트 — 계약 §3·§4 (영분산, mid-rank 동점, 시점 누수, 에피소드·중첩 경계, 순위, 설정 동결)."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.multihorizon.core import (
    log_variance_ratio,
    midrank_past,
    overlap_intervals,
    rank_intervals,
    realized_variance,
    runs,
    signal_matrix,
    ticker_features,
)

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "configs/t14_multihorizon_w2_v1.json").read_text(encoding="utf-8"))


def test_config_and_contract_frozen_sha():
    lines = (ROOT / "research/multihorizon_w2/CONTRACT_FREEZE_SHA256.txt").read_text().splitlines()
    for line in lines[:3]:
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name


def test_config_values_match_contract():
    assert CFG["q_main_overlap"] == [3, 7, 14, 20, 30, 60, 120]
    assert CFG["h_price"] == CFG["q_variance"] == [1, 3, 7, 14, 20, 30, 60, 120]
    assert CFG["cusum_windows"] == [20, 30, 60, 120]
    assert (CFG["signal_upper"], CFG["signal_lower"], CFG["min_reference_obs"], CFG["overlap_min_count"]) == (
        0.9,
        0.1,
        252,
        3,
    )
    assert CFG["protocol_version"] == "W2-lock-1"


def test_realized_variance_definition():
    r = np.array([np.nan, 1.0, -2.0, 3.0, 0.0])
    v = realized_variance(r, 3)
    assert np.isnan(v[:3]).all()  # 첫 창에 NaN 포함
    assert v[3] == pytest.approx((1 + 4 + 9) / 3)
    assert v[4] == pytest.approx((4 + 9 + 0) / 3)


def test_q1_ratio_not_defined():
    v = realized_variance(np.array([np.nan, 1.0, 0.0, 2.0]), 1)
    d, dv, st = log_variance_ratio(v, 1)
    assert np.isnan(d).all() and set(st) == {"NOT_DEFINED_Q1"}
    assert dv[3] == pytest.approx(4.0)  # 절대차는 보존


def test_q3_zero_variance_statuses():
    v = np.array([np.nan, np.nan, 1.0, 0.0, 2.0, 0.0, 0.0, 3.0])
    d, _dv, st = log_variance_ratio(v, 3)
    # t=5: V=0, prev=V[2]=1 → 분자 0 ; t=6: V=0, prev=V[3]=0 → 둘 다 0 ; t=7: V=3, prev=V[4]=2 → OK
    assert st[5] == "NUMERATOR_ZERO" and np.isnan(d[5])
    assert st[6] == "BOTH_ZERO" and np.isnan(d[6])
    assert st[7] == "OK" and d[7] == pytest.approx(np.log(1.5))
    v2 = np.array([0.0, 0.0, 0.0, 2.0])
    d2, _, st2 = log_variance_ratio(v2, 3)
    assert st2[3] == "DENOMINATOR_ZERO" and np.isnan(d2[3])
    assert np.isfinite(d[np.array(st) == "OK"]).all()  # epsilon 없이 OK 만 유한


def test_midrank_ties_and_strict_past():
    x = np.array([0.0, 0.0, 1.0, 0.0, 2.0])
    u, n, ties = midrank_past(x, min_ref=2)
    assert np.isnan(u[:2]).all()
    assert u[2] == pytest.approx(1.0)  # 기준 {0,0}, 1 보다 작은 값 2
    assert u[3] == pytest.approx((0 + 0.5 * 2) / 3)  # 기준 {0,0,1}, 동점 2
    assert ties[3] == 2 and n[3] == 3
    assert u[4] == pytest.approx(1.0)


def test_midrank_no_future_leakage():
    rng = np.random.default_rng(1)
    x = rng.normal(size=400)
    u, _, _ = midrank_past(x, 252)
    y = x.copy()
    y[300:] = 1e6  # 미래값을 바꿔도
    u2, _, _ = midrank_past(y, 252)
    assert np.array_equal(u[:300], u2[:300], equal_nan=True)  # 과거 분위는 그대로


def test_midrank_fixed_length_window():
    x = np.arange(10, dtype=float)
    u, n, _ = midrank_past(x, min_ref=2, max_ref=3)
    assert n[9] == 3  # n_ref 는 실제 사용한 최근 기준 수
    assert u[9] == pytest.approx(1.0)  # 최근 3개 {6,7,8} 보다 큼
    z = np.array([5, 1, 2, 3, 0], dtype=float)
    uz, _, _ = midrank_past(z, min_ref=2, max_ref=2)
    assert uz[4] == pytest.approx(0.0)  # 기준 {2,3}


def test_runs_no_gap_merge():
    f = np.array([0, 1, 1, 0, 1, 0, 0, 1], bool)
    assert runs(f) == [(1, 2), (4, 4), (7, 7)]


def _toy_features(n=320):
    dates = pd.bdate_range("2019-01-02", periods=n)
    rng = np.random.default_rng(7)
    r = rng.normal(size=n)
    r[0] = np.nan
    r[290:300] *= 6  # 뒤쪽 충격
    return dates, ticker_features(dates, r, {**CFG, "min_reference_obs": 30})


def test_overlap_interval_bounds_only_simultaneous_days():
    _dates, f = _toy_features()
    sig = signal_matrix(f, CFG)
    sig["HIGH_LEVEL"][:] = False
    idx = sig["HIGH_LEVEL"].index
    # q3,q7 은 100–104, q14 는 103–110, q20 은 104–106
    # → 3개 이상 동시일 = 103–104 (104 는 4개), 105–106 (q14,q20) 은 2개
    sig["HIGH_LEVEL"].loc[idx[100:105], [3, 7]] = True
    sig["HIGH_LEVEL"].loc[idx[103:111], 14] = True
    sig["HIGH_LEVEL"].loc[idx[104:107], 20] = True
    _, iv = overlap_intervals("T", sig, f, CFG)
    hi = iv[iv.channel.eq("HIGH_LEVEL")]
    assert len(hi) == 1
    row = hi.iloc[0]
    assert row.interval_start == str(idx[103].date()) and row.interval_end == str(idx[104].date())
    assert row.max_overlap_count == 4 and row.duration_trading_days == 2
    assert row.active_q_ever == "3,7,14,20" and bool(row.short) and bool(row.mid) and not bool(row["long"])
    assert row.episode_confirmed_at == str(idx[105].date())


def test_rank_min_ties():
    iv = pd.DataFrame(
        {"g": ["a"] * 4, "max_overlap_count": [5, 5, 7, 5], "duration_trading_days": [3, 3, 1, 9]}
    )
    assert rank_intervals(iv, ["g"]).tolist() == [3, 3, 1, 2]


def test_trailing_and_forward_sums_do_not_cross_time():
    from r2h.multihorizon.stage07 import forward_sum, trailing_sum

    x = np.arange(1.0, 11.0)
    tr, fw = trailing_sum(x, 3), forward_sum(x, 3)
    assert np.isnan(tr[:2]).all() and tr[2] == 6.0  # 1+2+3 (t 포함 과거)
    assert fw[0] == 2 + 3 + 4 and np.isnan(fw[-3:]).all()  # t+1..t+3, 자료 끝은 NaN
    y = x.copy()
    y[5:] = 1e6
    assert np.array_equal(trailing_sum(y, 3)[:5], tr[:5], equal_nan=True)
    z = x.copy()
    z[:5] = -1e6
    assert np.array_equal(forward_sum(z, 3)[4:], fw[4:], equal_nan=True)


def test_cross_daily_counts_kospi200_once():
    from r2h.multihorizon.stage06 import cross_daily

    expo = pd.DataFrame(
        {
            "ticker": ["069500", "102110", "122630", "114800", "148070"],
            "exposure_group": ["K", "K", "K", "K", "148070"],
            "exposure_group_us": ["K", "K", "K", "K", "148070"],
            "category": ["broad", "broad", "lev", "lev", "rates"],
        }
    )
    d = pd.Timestamp("2024-08-05")
    ov = pd.DataFrame(
        {
            "ticker": expo.ticker,
            "channel": "EXPANSION",
            "date": d,
            "overlap_count": 3,
            "overlap_candidate_day": True,
        }
    )
    out = cross_daily(ov, expo).iloc[0]
    assert (out.n_etf, out.n_group, out.n_category) == (5, 2, 3)


def test_daily_cusum_respects_year_boundary_and_common_start():
    from r2h.multihorizon.cusum import daily_cusum

    rng = np.random.default_rng(3)
    rows = []
    for y in (2021, 2022):
        dates = pd.bdate_range(f"{y}-01-04", periods=200)
        e = rng.normal(size=200)
        rows.append(
            pd.DataFrame({"ticker": "T", "year": y, "policy": "A", "window": 0, "date": dates, "e": e})
        )
    daily = pd.concat(rows, ignore_index=True)
    ws = [20, 30, 60, 120]
    pipe = {("A", w): 0.5 for w in ws}
    point = {("T", y, "A", w): 0.5 for y in (2021, 2022) for w in ws}
    c = daily_cusum("T", daily, {"common_start_zero_based": 119}, pipe, point, ws)
    for _, g in c.groupby("year"):
        g = g.sort_values("date").reset_index(drop=True)
        assert (
            g.loc[:118, [f"pipe_common_w{w}" for w in ws]].eq("NOT_AVAILABLE").all().all()
        )  # 공통일 시작 전
        assert (
            g.loc[:18, "pipe_own_w20"].eq("NOT_AVAILABLE").all()
            and g.loc[19, "pipe_own_w20"] != "NOT_AVAILABLE"
        )
        assert g.loc[:118, "T_w120"].isna().all()  # 전년도 자료로 창을 채우지 않는다
