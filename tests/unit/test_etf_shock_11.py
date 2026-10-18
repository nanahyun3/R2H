"""11번 개별 ETF 급변 구간 테스트 — 계약 11-lock-1 §2–§6 (경계 σ, 분산 기여, 창 이탈, CUSUM 재현, 원본 보호)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.etf_shock import pipeline as P
from r2h.multihorizon.core import midrank_past

ROOT = Path(__file__).resolve().parents[2]


def test_boundary_matches_midrank_rule():
    """경계 σ 역산: 동점이 없으면 U ≥ 0.9 ⟺ x > b (합성 자료)."""
    rng = np.random.default_rng(20261018)
    x = rng.lognormal(size=600)
    u, _, ties = midrank_past(x, 252)
    b = P.boundary_sigma(x, 252, 0.90)
    ok = np.isfinite(u) & (ties == 0)
    assert ((x[ok] > b[ok]) == (u[ok] >= 0.90)).all()


@pytest.fixture(scope="module")
def res():
    return P.run(ROOT)


def test_contract_freeze():
    for line in (ROOT / P.OUT_DIR / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == d, name


def test_cusum_reproduces_w3(res):
    assert res["cusum_info"]["n_checked"] == 72


def test_intervals_match_daily_states(res):
    d = res["daily"]
    for (t, q), x in res["intervals"].groupby(["ticker", "q"]):
        a = d[d["ticker"] == t].reset_index(drop=True)[f"A{q}"]
        assert int(x["duration"].sum()) == int((a == 1).sum())  # 구간 일수 합 = A=1 일수 (전체 달력)
        for _, r in x.iterrows():
            assert (a.iloc[r["i0"]:r["i1"] + 1] == 1).all()
            assert r["i0"] == 0 or a.iloc[r["i0"] - 1] != 1  # 앞날은 1 이 아님 (0 또는 NA)


def test_window_exit_definition(res):
    d = res["daily"]
    for _, r in res["intervals"][res["intervals"]["window_exit_end"]].iterrows():
        x = d[d["ticker"] == r["ticker"]].reset_index(drop=True)
        top = int(x.index[x["date"] == pd.Timestamp(r["top1_date"])][0])
        assert r["i1"] + 1 == top + r["q"] and x.loc[r["i1"] + 1, f"A{r['q']}"] == 0


def test_shock_type_threshold(res):
    iv = res["intervals"]
    assert ((iv["top1_share"] >= 0.30) == (iv["shock_type"] == "단일 충격형")).all()


def test_no_cusum_outside_2021_2025(res):
    cu = res["cusum"]
    assert cu["date"].dt.year.between(2021, 2025).all()
    iv = res["intervals"]
    out = iv[pd.to_datetime(iv["end"]).dt.year < 2021]
    assert (out["cusum_coverage_A20"] == 0).all()


def test_no_alarm_on_shock_days(res):
    io = res["inside_outside"]
    assert int(io[io["side"] == "A20 날"]["alarm_days"].sum()) == 0
