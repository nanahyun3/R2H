"""W4 계산 규칙 단위 테스트 — 계약 W4-lock-1 §3–§8 (수치·그룹·라벨·데이터 경계)."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.multihorizon.core import midrank_past
from r2h.peer_shock.core import (
    and3,
    annualized_vol,
    etf_state_table,
    final_labels,
    global_states,
    group_states,
    intervals,
    lower_flag,
    or3,
    pair_ratio_state,
    peer_log_ratio,
    percent_log_returns_gap,
    upper_flag,
    verdict,
)

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "configs/t18_peer_shock_w4_v1.json").read_text(encoding="utf-8"))
P = {"A_upper": 0.90, "B_lower": 0.05, "B_upper": 0.95, "min_ref": 5, "max_ref": None}


# ── 계약 동결 ─────────────────────────────────────────────────────────────
def test_contract_freeze_sha():
    for line in (ROOT / "research/peer_relative_shock_w4/CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name


def test_thresholds_frozen():
    assert (CFG["A_upper"], CFG["B_lower"], CFG["B_upper"]) == (0.90, 0.05, 0.95)
    assert CFG["q_main"] == [20, 60] and CFG["min_reference_obs"] == 252 and CFG["std_ddof"] == 1


# ── 수치 계산 ─────────────────────────────────────────────────────────────
def test_log_returns_and_gap_not_filled():
    c = pd.Series([100.0, 110.0, np.nan, 121.0, 121.0])
    r = percent_log_returns_gap(c).to_numpy()
    assert np.isnan(r[0]) and r[1] == pytest.approx(100 * np.log(1.1))
    assert np.isnan(r[2]) and np.isnan(r[3])  # 결측 다음 날도 결측 (전일값 채우기 없음)
    assert r[4] == 0.0
    with pytest.raises(ValueError):
        percent_log_returns_gap(pd.Series([1.0, 0.0]))


def test_annualized_sample_std():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 1, 30)
    v = annualized_vol(r, 20)
    assert np.isnan(v[18]) and v[19] == pytest.approx(np.sqrt(252) * np.std(r[:20], ddof=1))
    r2 = r.copy()
    r2[25] = np.nan
    v2 = annualized_vol(r2, 20)
    assert np.isnan(v2[25:]).all()  # 창 안 결측 → 결측


def test_multiplier_normalization():
    dates = pd.date_range("2020-01-01", periods=10)
    base = np.linspace(10, 20, 10)
    sigma = {"X": {20: 2 * base}, "Y": {20: base}, "Z": {20: base}}
    t = etf_state_table(dates, sigma, "X", ["Y", "Z"], 1, {"X": 2.0}, [20], P)
    assert np.allclose(t["sigma_adj"], base) and np.allclose(t["L"], 0.0)
    t2 = etf_state_table(dates, {"X": {20: base}, "Y": {20: base}}, "X", ["Y"], 1, {"X": -1.0}, [20], P)
    assert np.allclose(t2["sigma_adj"], base)  # 인버스 −1 → |m| = 1


def test_midrank_ties_and_strict_past():
    u, n, ties = midrank_past(np.array([1.0, 1.0, 1.0, 2.0, 1.0]), 1)
    assert np.isnan(u[0])  # 기준 0개
    assert u[1] == 0.5 and ties[1] == 1  # 동점 → 0.5
    assert u[3] == 1.0
    assert u[4] == pytest.approx((0 + 0.5 * 3) / 4)
    # 당일 값은 기준에 없다: 극단값을 당일에 넣어도 그날 U 는 과거만으로 결정
    x = np.arange(10, dtype=float)
    x2 = x.copy()
    x2[9] = 1e9
    assert midrank_past(x, 3)[0][9] == midrank_past(x2, 3)[0][9] == 1.0


def test_peer_log_ratio_median_and_zero_vol():
    own = np.array([2.0, 0.0, 2.0, 2.0, np.nan])
    peers = np.array([[1.0, 3.0, np.nan], [1.0, 1.0, 1.0], [0.0, 0.0, 1.0], [np.nan, np.nan, 1.0], [1.0, 1.0, 1.0]])
    L, med, nv, st = peer_log_ratio(own, peers, 2)
    assert L[0] == pytest.approx(np.log(2 / 2.0)) and nv[0] == 2
    assert list(st) == ["OK", "ZERO_VOL_NUMERATOR", "ZERO_VOL_DENOMINATOR", "PEER_INSUFFICIENT_ON_DATE", "VOL_MISSING"]
    assert np.isnan(L[1:]).all()  # epsilon 없음


def test_two_sided_tail_flags():
    u = np.array([0.04, 0.05, 0.5, 0.95, 0.96, np.nan])
    assert list(upper_flag(u, 0.95)[:5]) == [0, 0, 0, 1, 1]
    assert list(lower_flag(u, 0.05)[:5]) == [1, 1, 0, 0, 0]
    b = or3(upper_flag(u, 0.95), lower_flag(u, 0.05))
    assert list(b[:5]) == [1, 1, 0, 1, 1] and np.isnan(b[5])


def test_three_valued_logic():
    one, zero, na = np.array([1.0]), np.array([0.0]), np.array([np.nan])
    assert and3(one, one)[0] == 1 and and3(one, zero)[0] == 0 and np.isnan(and3(one, na)[0])
    assert and3(zero, na)[0] == 0  # 확정 거짓은 NA 와 무관
    assert or3(one, na)[0] == 1 and np.isnan(or3(zero, na)[0]) and or3(zero, zero)[0] == 0


# ── 그룹·라벨 ─────────────────────────────────────────────────────────────
def _groups():
    with (ROOT / CFG["exposure_groups"]).open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    g: dict[str, list[str]] = {}
    for r in rows:
        g.setdefault(r["exposure_group"], []).append(r["ticker"])
    return rows, g


def test_universe_20_unique_and_17_groups():
    rows, g = _groups()
    tick = [r["ticker"] for r in rows]
    assert len(tick) == 20 == len(set(tick))
    assert len(g) == 17
    assert sorted(g[CFG["kospi200_group"]]) == sorted(["069500", "102110", "122630", "114800"])
    assert sum(len(v) for v in g.values()) == 20  # 각 ETF 는 한 그룹에만


def test_peer_group_distinct_from_exposure_group():
    with (ROOT / CFG["peer_mapping"]).open(encoding="utf-8") as fh:
        m = list(csv.DictReader(fh))
    rows, g = _groups()
    grp = {r["ticker"]: r["exposure_group"] for r in rows}
    adopted = [r for r in m if r["adopted"] == "True"]
    assert {r["eval_ticker"] for r in adopted} == set(grp)  # 20/20 매핑
    assert all(r["peer_ticker"] != r["eval_ticker"] for r in adopted)  # 자기 자신 제외
    # 133690 ↔ 219480 은 서로 Peer 지만 노출 그룹은 다르다
    pairs = {(r["eval_ticker"], r["peer_ticker"]) for r in adopted}
    assert ("133690", "219480") in pairs and grp["133690"] != grp["219480"]
    # 늦은 상장은 채택되지 않는다
    assert all(r["first_obs"] <= CFG["peer_listing_cutoff"] for r in adopted)


def _synthetic(n=40, n_groups=3):
    """그룹 3개(첫 그룹은 Core Pair) 합성 상태."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(1)
    sig = {t: {20: rng.uniform(5, 10, n)} for t in ["C1", "C2", "S1", "S2", "P1", "P2"]}
    peers = {"C1": ["C2"], "C2": ["C1"], "S1": ["P1", "P2"], "S2": ["P1", "P2"]}
    etf = pd.concat([etf_state_table(dates, sig, t, peers[t], 1, {}, [20], P) for t in peers], ignore_index=True)
    core = {20: pair_ratio_state(sig["C1"][20], sig["C2"][20], P)}
    groups = {"K": ["C1", "C2"], "S1": ["S1"], "S2": ["S2"]}
    return dates, etf, core, groups


def test_kospi_counted_once_and_core_rule():
    dates, etf, core, groups = _synthetic()
    gs = group_states(etf, groups, "K", ("C1", "C2"), core, [20])
    assert gs.groupby("date").size().eq(3).all()  # 그룹당 한 번
    k = gs[gs["group"] == "K"].reset_index(drop=True)
    a1 = etf[(etf.ticker == "C1")]["A"].to_numpy()
    a2 = etf[(etf.ticker == "C2")]["A"].to_numpy()
    assert np.array_equal(k["GROUP_A"].to_numpy(), and3(a1, a2), equal_nan=True)
    assert np.array_equal(k["GROUP_B"].to_numpy(), core[20]["B"].to_numpy(), equal_nan=True)
    assert np.array_equal(k["GROUP_AB"].to_numpy(), and3(k["GROUP_A"], k["GROUP_B"]), equal_nan=True)


def test_global_requires_all_groups():
    d = pd.Timestamp("2021-01-04")
    base = {"date": d, "q": 20, "GROUP_B_UP": 1.0, "GROUP_B_DOWN": 0.0}
    full = pd.DataFrame([{**base, "group": f"g{i}", "GROUP_A": 1.0, "GROUP_B": 1.0, "GROUP_AB": 1.0} for i in range(17)])
    assert global_states(full, 17)["GLOBAL_AB"].iloc[0] == 1
    sixteen = full.copy()
    sixteen.loc[0, ["GROUP_AB"]] = 0.0
    assert global_states(sixteen, 17)["GLOBAL_AB"].iloc[0] == 0  # 16/17 은 급변 아님
    na = full.copy()
    na.loc[0, ["GROUP_AB"]] = np.nan
    g = global_states(na, 17)
    assert np.isnan(g["GLOBAL_AB"].iloc[0]) and g["n_eval_AB"].iloc[0] == 16  # NA 를 0 으로 채우지 않음
    with pytest.raises(AssertionError):
        global_states(full.iloc[:16], 17)


def test_final_or_across_horizons():
    dates = pd.date_range("2021-01-04", periods=5, freq="B")
    g20 = [1, 0, np.nan, np.nan, 0]
    g60 = [np.nan, 0, 1, np.nan, np.nan]
    gl = pd.DataFrame({"date": list(dates) * 2, "q": [20] * 5 + [60] * 5, "GLOBAL_A": 0.0, "GLOBAL_B": 0.0,
                       "GLOBAL_AB": g20 + g60})
    f = final_labels(gl, [20, 60])
    assert list(f["FINAL_SHOCK"].fillna(-1)) == [1, 0, 1, -1, -1]  # 한쪽 참이면 참, 0 은 둘 다 0 일 때만
    assert list(f["GLOBAL_AB_20_ONLY"].fillna(-1)) == [-1, 0, 0, -1, 0]


def test_intervals_immediate_entry_exit_and_reentry():
    dates = pd.date_range("2021-01-04", periods=10, freq="B")
    flag = np.array([1, 1, 0, 1, np.nan, 1, 1, 0, 0, 1], float)
    iv = intervals(pd.Series(dates), flag, np.array([0, 0, 3, 0, 0, 0, 0, 0, 0, 0]))
    assert list(iv["duration_trading_days"]) == [2, 1, 2, 1]  # 갭 병합 없음·하루 구간 허용
    assert iv["left_censored"].iloc[0] and iv["right_censored"].iloc[-1]
    assert iv["exit_reason"].iloc[0] == "GLOBAL_CONDITION_EXITED"  # 그날 AB 그룹 3 → 정상화 아님
    assert iv["exit_reason"].iloc[1] == "NOT_EVALUABLE"  # NA 는 정상 복귀가 아님
    assert iv["entry_after"].iloc[2] == "NA"
    assert iv["exit_reason"].iloc[2] == "GLOBAL_CONDITION_EXITED|ALL_GROUPS_NORMALIZED"
    assert iv["exit_reason"].iloc[3] == "RIGHT_CENSORED"


def test_intervals_cross_year_boundary_kept():
    dates = pd.to_datetime(["2021-12-29", "2021-12-30", "2022-01-03", "2022-01-04"])
    iv = intervals(pd.Series(dates), np.array([0, 1, 1, 0.0]))
    assert len(iv) == 1 and str(iv["start"].iloc[0]) == "2021-12-30" and str(iv["end"].iloc[0]) == "2022-01-03"


def test_verdict_categories():
    d = pd.date_range("2021-01-04", periods=10, freq="B")
    mk = lambda v: pd.DataFrame({"date": d, "FINAL_SHOCK": v})  # noqa: E731
    assert verdict(mk([0.0] * 9 + [1.0]), CFG)["verdict"] == "LABELS_GENERATED"
    assert verdict(mk([0.0] * 10), CFG)["verdict"] == "VALID_ZERO_INTERVALS"
    assert verdict(mk([np.nan] * 6 + [0.0] * 4), CFG)["verdict"] == "INSUFFICIENT_PEER_COVERAGE"


# ── 데이터 경계 ───────────────────────────────────────────────────────────
def test_no_future_leak_in_states():
    """t 이후 가격을 바꿔도 t 까지의 σ·U·A·B 는 변하지 않는다."""
    n = 80
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(3)
    rets = {t: rng.normal(0, 1, n) for t in ["X", "Y", "Z"]}
    sig = {t: {20: annualized_vol(r, 20)} for t, r in rets.items()}
    base = etf_state_table(dates, sig, "X", ["Y", "Z"], 2, {}, [20], P)
    cut = 60
    rets2 = {t: np.r_[r[:cut], rng.normal(0, 9, n - cut)] for t, r in rets.items()}
    sig2 = {t: {20: annualized_vol(r, 20)} for t, r in rets2.items()}
    alt = etf_state_table(dates, sig2, "X", ["Y", "Z"], 2, {}, [20], P)
    cols = ["sigma", "U_A", "A", "L", "U_B", "B", "AB"]
    pd.testing.assert_frame_equal(base.loc[: cut - 1, cols], alt.loc[: cut - 1, cols])


def test_peer_mapping_script_uses_no_price_statistics():
    src = (ROOT / "scripts/t18_freeze_peer_mapping.py").read_text(encoding="utf-8")
    for bad in ("corr", "std(", "Close", "read_csv", "volatility"):
        assert bad not in src, bad
