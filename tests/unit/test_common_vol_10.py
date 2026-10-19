"""10번 공통 고변동성 후보 규칙 테스트 — 계약 10-lock-1 §1.1·§2–§6 (구간 규칙·NA·검열·포함관계·09 승계)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.common_vol import pipeline as P
from r2h.common_vol.core import candidate_flag, containment_map, extract_intervals, interval_profile, jaccard

ROOT = Path(__file__).resolve().parents[2]
NAN = np.nan


# ── 일별 판정 ─────────────────────────────────────────────────────────────
def test_candidate_flag_na_not_zero():
    f = candidate_flag(np.array([9, 8, 12, 9]), np.array([17, 17, 16, 17]), 9, 17)
    assert f[0] == 1 and f[1] == 0 and np.isnan(f[2]) and f[3] == 1  # 평가 불가일은 N_A 가 커도 NA


# ── 구간 추출 ─────────────────────────────────────────────────────────────
def _iv(flag, mask=None):
    f = np.asarray(flag, float)
    return extract_intervals(f, np.ones(f.size, bool) if mask is None else np.asarray(mask, bool))


def test_one_day_and_no_gap_merge():
    rows = _iv([0, 1, 0, 1, 1, 0])
    assert [(r["i0"], r["i1"]) for r in rows] == [(1, 1), (3, 4)]  # 하루짜리 보존, 하루 공백도 병합 안 함


def test_na_is_boundary_not_false():
    rows = _iv([1, 1, NAN, 1, 0])
    assert [(r["i0"], r["i1"]) for r in rows] == [(0, 1), (3, 3)]
    assert rows[0]["exit_reason"] == "NA_BOUNDARY" and rows[1]["entry_after"] == "AFTER_NA"


def test_censoring_uses_neighbouring_period_state():
    flag = [1, 1, 1, 0, 1, 1]
    mask = [False, True, True, False, False, False]  # 기간 = 인덱스 1–2
    (r,) = _iv(flag, mask)
    assert (r["i0"], r["i1"]) == (1, 2)
    assert r["left_censored"] is True and r["right_censored"] is False  # 직전 1 → 좌측 검열, 직후 0 → 아님
    (r,) = _iv([NAN, 1, 1, 1], [False, True, True, False])
    assert r["left_censored"] == "UNKNOWN" and r["right_censored"] is True
    (r,) = _iv([0, 1], [False, True])
    assert r["right_censored"] == "UNKNOWN"  # 달력 끝


def test_year_boundary_is_continuous():
    """달력 연도가 바뀌어도 거래일이 이어지면 같은 구간 (기간 마스크 안)."""
    dates = pd.DatetimeIndex(["2021-12-29", "2021-12-30", "2022-01-03", "2022-01-04", "2022-01-05"])
    (r,) = _iv([0, 1, 1, 1, 0])
    assert (dates[r["i0"]].year, dates[r["i1"]].year) == (2021, 2022) and r["i1"] - r["i0"] + 1 == 3


def test_real_year_crossing_interval(res):
    """실제 주분석에서 연도를 넘는 구간이 하나의 구간으로 남는다 (q20 k3 2024-12 → 2025-01)."""
    iv = res["intervals"]
    x = iv[(iv["period"] == "PRIMARY") & (pd.to_datetime(iv["start"]).dt.year != pd.to_datetime(iv["end"]).dt.year)]
    assert len(x) >= 1
    d = res["daily"]
    for _, r in x.iterrows():
        assert (d.loc[r["i0"]:r["i1"], r["rule"]] == 1).all()  # 연말·연초 사이에 끊김 없음


def test_period_boundary_censoring_real(res):
    """주분석 마지막 날(2025-12-30)에 이어지는 구간은 2026-01-02 상태로 우측 검열된다."""
    iv = res["intervals"]
    x = iv[(iv["period"] == "PRIMARY") & (iv["exit_reason"] == "PERIOD_END")]
    d = res["daily"].set_index("date")
    for _, r in x.iterrows():
        nxt = d.loc["2026-01-02", r["rule"]]
        assert r["right_censored"] == (True if nxt == 1 else (False if nxt == 0 else "UNKNOWN"))


def test_period_mask_must_be_contiguous():
    with pytest.raises(ValueError):
        _iv([1, 1, 1], [True, False, True])


def test_profile_distinguishes_simultaneous_and_ever():
    a = np.array([[1, 1, 0], [0, 1, 1]], float)  # 2일 × 3그룹: 같은 날 최대 2, ever 3
    z = np.zeros_like(a)
    p = interval_profile(0, 1, a, z, z, ["g1", "g2", "g3"], pd.DatetimeIndex(["2024-01-02", "2024-01-03"]))
    assert p["max_n_A"] == 2 and p["n_groups_ever"] == 3 and p["groups_always"] == "g2"
    assert p["stability_consecutive_jaccard"] == pytest.approx(1 / 3) and p["core_share"] == pytest.approx(1 / 3)


def test_jaccard_and_containment():
    assert jaccard(set(), set()) != jaccard(set(), set())  # 둘 다 공집합이면 NaN
    assert jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3)
    lo = pd.DataFrame({"interval_id": ["L1"], "i0": [0], "i1": [10]})
    hi = pd.DataFrame({"interval_id": ["S1", "S2"], "i0": [1, 6], "i1": [3, 8]})
    assert containment_map(hi, lo).to_dict() == {"S1": "L1", "S2": "L1"}
    with pytest.raises(AssertionError):
        containment_map(pd.DataFrame({"interval_id": ["S"], "i0": [9], "i1": [12]}), lo)


# ── 실제 데이터: 09 승계·무결성·교차 앵커 ───────────────────────────────────
@pytest.fixture(scope="module")
def res():
    return P.run(ROOT)


def test_contract_freeze():
    for line in (ROOT / P.OUT_DIR / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == d, name


def test_w4_inheritance(res):
    gbp = pd.read_csv(ROOT / res["cfg"]["w4_inputs"]["global_by_period"])
    pc = res["verify"]["period_check"].merge(gbp, on=["period", "q"])
    assert (pc["max_n_A_x"] == pc["max_n_A_y"]).all() and (pc["days17_A_x"] == pc["days17_A_y"]).all()
    assert res["verify"]["w4_verdict"] == "VALID_ZERO_INTERVALS" and res["verify"]["w4_intervals"] == 0


def test_primary_fully_evaluable(res):
    d = res["daily"][res["daily"]["period"] == "PRIMARY"]
    assert len(d) == 1225 and (d["n_eval_A_q20"] == 17).all() and (d["n_eval_A_q60"] == 17).all()


def test_nesting_same_q(res):
    d = res["daily"]
    for q in (20, 60):
        for k1, k2 in ((3, 6), (6, 9), (9, 10), (10, 12), (12, 17)):
            assert not ((d[f"q{q}_k{k2}"] == 1) & (d[f"q{q}_k{k1}"] != 1)).any()


def test_interval_days_match_daily(res):
    s = res["summary"].set_index("rule")
    d = res["daily"][res["daily"]["period"] == "PRIMARY"]
    for r in s.index:
        assert s.loc[r, "candidate_days"] == int((d[r] == 1).sum())
    assert (res["integrity"]["candidate_days"] >= 0).all()


def test_c3_c4_equal_w4_max_days(res):
    """C3(q20 k12)·C4(q60 k6) 는 09 관측 최대값과 같은 k 라 날짜 집합이 max_participation_days 와 같아야 한다."""
    mpd = pd.read_csv(ROOT / res["cfg"]["w4_inputs"]["max_participation_days"])
    d = res["daily"][res["daily"]["period"] == "PRIMARY"]
    for q, rule in ((20, "q20_k12"), (60, "q60_k6")):
        row = mpd[(mpd["q"] == q) & (mpd["state"] == "A")].iloc[0]
        want = set()
        for span in row["spans"].split(";"):
            a, b = span.split("~")
            want |= set(d.loc[(d["date"] >= a) & (d["date"] <= b), "date"])
        got = set(d.loc[d[rule] == 1, "date"])
        assert got == want and len(got) == row["n_days_at_max"]
        assert int(res["summary"].set_index("rule").loc[rule, "observed_max_n_A"]) == row["max_groups"]


def test_zero_rules_report_gap(res):
    s = res["summary"]
    z = s[s["n_intervals"] == 0]
    assert (z["gap_k_minus_max"] == z["k"] - z["observed_max_n_A"]).all() and (z["gap_k_minus_max"] > 0).all()


def test_2026_and_2020_not_in_primary(res):
    iv = res["intervals"]
    p = iv[iv["period"] == "PRIMARY"]
    assert pd.to_datetime(p["start"]).dt.year.between(2021, 2025).all() and pd.to_datetime(p["end"]).dt.year.between(2021, 2025).all()
    pil = res["summary_pilot"].set_index("rule")
    w4 = pd.read_csv(ROOT / res["cfg"]["w4_inputs"]["global_by_period"]).set_index(["period", "q"])
    assert pil.loc["q20_k17", "candidate_days"] == w4.loc[("PILOT", 20), "days17_A"]


# ── 10-lock-2 ─────────────────────────────────────────────────────────────
from r2h.common_vol import lock2 as L2  # noqa: E402


def test_circular_null_preserves_marginals_and_kstar():
    rng = np.random.default_rng(1)
    a = (rng.random((300, 5)) < 0.2).astype(int)
    pd_, pf = L2.circular_null(a, 200, np.random.default_rng(2))
    assert pd_[0] == pytest.approx(1.0) and pf[0] == pytest.approx(1.0)
    assert np.all(np.diff(pd_) <= 1e-12) and np.all(np.diff(pf) <= 1e-12)  # k 에 대해 단조 감소
    assert pd_[1:].sum() == pytest.approx(a.sum() / 300, rel=1e-9)  # Σ_k P(N≥k) = E[N] = 그룹 평균 합 (원형 이동은 주변 분포 보존)
    assert L2.kstar(np.array([1, 0.5, 0.04, 0.0]), 0.05) == 2 and L2.kstar(np.array([1, 1.0]), 0.05) == -1


def test_hysteresis_rule():
    n = np.array([0, 9, 8, 7, 6, 9, 10, 8, 0])
    v = np.ones(n.size, bool)
    assert L2.hysteresis(n, v, 9, 7, np.ones(n.size, bool)) == [(1, 3), (5, 7)]
    v[2] = False  # NA 는 끊는 경계
    assert L2.hysteresis(n, v, 9, 7, np.ones(n.size, bool)) == [(1, 1), (5, 7)]


def test_lock2_freeze_and_anchors(res):
    for line in (ROOT / P.OUT_DIR / "CONTRACT_FREEZE_SHA256_LOCK2.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == d, name
    x = L2.run(ROOT, res)
    ks = x["kstar"].set_index("q")
    assert int(ks.loc[20, "k_star_fw"]) == 9 and int(ks.loc[60, "obs_max"]) < int(ks.loc[60, "k_star_fw"])
    h1 = x["hysteresis"].query("rule == 'H1'")
    c1 = res["intervals"].query("rule == 'q20_k9' and period == 'PRIMARY'")
    assert list(h1["i0"]) == list(c1["i0"]) and list(h1["i1"]) == list(c1["i1"])  # C1 내부에 N_A 7–8 하락 없음


# ── PART R 모델 입력 ──────────────────────────────────────────────────────
from r2h.common_vol import model_input as MI  # noqa: E402


@pytest.fixture(scope="module")
def mi(res):
    return MI.run(ROOT, res, L2.run(ROOT, res))


def test_model_spec_freeze():
    for line in (ROOT / P.OUT_DIR / "CONTRACT_FREEZE_SHA256_MODEL_INPUT.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == d, name


def test_etf_intervals_match_a20(mi):
    for t, f in mi["feats"].items():
        x = mi["etf_intervals"][mi["etf_intervals"]["ticker"] == t]
        assert int(x["duration"].sum()) == int((f["A20"] == 1).sum())
        for _, r in x.iterrows():
            assert (f["A20"].iloc[r["i0"]:r["i1"] + 1] == 1).all()
            assert str(r["available_from"]) > str(r["start"])  # 다음 거래일부터 사용


def test_windows_alignment_and_labels(mi):
    idx, X, M = mi["datasets"]["D1"]
    assert X.shape == (len(idx), 60, 13) and M.shape == X.shape
    f = mi["feats"]["069500"]
    j = idx.index[(idx["ticker"] == "069500") & (idx["end_date"].astype(str) == "2024-08-05")][0]
    n = mi["datasets"]["norm"]["069500"]["r"]
    assert X[j, -1, 0] == pytest.approx((f.loc["2024-08-05", "r"] - n["mean"]) / n["std"], abs=1e-4)
    k = int(np.flatnonzero(f.index == pd.Timestamp("2024-08-02"))[0])  # 2024-08-05 직전 거래일
    jj = idx.index[(idx["ticker"] == "069500") & (idx["end_date"].astype(str) == "2024-08-02")][0]
    assert idx.loc[jj, "y_next5_A20"] == float((f["A20"].iloc[k + 1:k + 6] == 1).any())


def test_normal_windows_have_no_shock(mi):
    idx = mi["datasets"]["D3"][0]
    for _, r in idx.sample(50, random_state=0).iterrows():
        a = mi["feats"][r["ticker"]]["A20"]
        e = int(np.flatnonzero(a.index == pd.Timestamp(r["end_date"]))[0])
        assert (a.iloc[e - 59:e + 6] == 0).all()


def test_embargo_and_splits(mi):
    idx = mi["datasets"]["D1"][0]
    assert int(idx["embargo"].sum()) == 20 * 5 * 3  # 20종 × 지평 5일 × 경계 3개
    assert set(idx["split"]) == {"train", "val", "test", "holdout_non_blind"}
