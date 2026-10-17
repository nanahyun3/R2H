"""W3 (T15) 공동 CUSUM 검정의 전제 테스트 (계약 §5–§7, 승인서 §17).

각 테스트는 검정의 한 전제에 대응한다 — 모수 회복 (귀무 식별), 정보 경계 (워크포워드), 재현 (관측=반복 경로),
시차·E 재생성 (선택 효과 보정), 해상도 (MC 정밀도), 무효 판정 (귀무 부적합 반영), 누수 (가격 반응).
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.joint_cusum import dcc, h0a, inference, mc, scores, validity
from r2h.joint_cusum.pipeline import all_windows, load_cfg, load_returns, run_pipeline
from r2h.svrgarch_etf.rolling import rolling_cusum

ROOT = Path(__file__).resolve().parents[2]
CFG = load_cfg()
TICKERS = list(CFG["universe"]["tickers"])


def _toy_model(N: int = 3, a: float = 0.04, b: float = 0.90, nu: float = 7.0) -> dcc.MultiT:
    g = tuple(dcc.GarchT(0.02, 0.05, 0.08, 0.88, nu, 0.0, True, "") for _ in range(N))
    qbar = np.array([[1, 0.6, 0.2], [0.6, 1, 0.1], [0.2, 0.1, 1.0]])[:N, :N]
    return dcc.MultiT("DCC", g, qbar, a, b, nu, 0.0, True, "")


# ── 귀무모형 (D3) ──────────────────────────────────────────────────


def test_dcc_t_parameter_recovery() -> None:
    """알려진 DCC-t 에서 모의 → 재적합이 (a, b, ν) 를 회복해야 H0-B 귀무가 식별된다."""
    r, _ = dcc.simulate(_toy_model(), 3000, np.random.default_rng(7))
    f = dcc.fit_multit(r, "DCC")
    assert abs(f.a - 0.04) < 0.02 and abs(f.b - 0.90) < 0.04 and abs(f.nu - 7.0) < 2.0
    assert all(dcc.validity_numeric(f).values())


def test_ccc_t_stable_estimation() -> None:
    """CCC-t 는 a=b=0, ν 만 추정 — 같은 자료에 두 번 적합해도 같은 값 (결정적)."""
    r, _ = dcc.simulate(_toy_model(a=0.0, b=0.0), 2000, np.random.default_rng(3))
    f1, f2 = dcc.fit_multit(r, "CCC"), dcc.fit_multit(r, "CCC")
    assert f1.a == 0 and f1.b == 0 and f1.nu == f2.nu and 4.0 < f1.nu < 12.0


def test_correlation_positive_definite_unit_diagonal() -> None:
    """모의 경로의 모든 R_t 가 양정치이고 대각이 1 이어야 다변량 t 혁신이 정의된다."""
    m = _toy_model()
    _, min_eig = dcc.simulate(m, 500, np.random.default_rng(1))
    assert min_eig > 0
    z = np.random.default_rng(2).standard_normal((300, 3))
    Rt = dcc.dcc_correlations(z, m.a, m.b, m.qbar)
    assert np.allclose(np.diagonal(Rt, axis1=1, axis2=2), 1.0)
    assert np.linalg.eigvalsh(Rt).min() > 0


def test_student_t_innovation_unit_variance() -> None:
    """혁신은 분산 1 로 정규화돼야 GARCH 분산과 상관 해석이 맞다."""
    m = _toy_model(a=0.0, b=0.0)
    m = dcc.MultiT(
        "CCC",
        tuple(dcc.GarchT(0.0, 1.0, 0.0, 0.0, 6.0, 0, True, "") for _ in range(3)),
        m.qbar,
        0,
        0,
        6.0,
        0,
        True,
        "",
    )
    r, _ = dcc.simulate(m, 200_000, np.random.default_rng(5), burn=1)
    assert np.allclose(r.var(axis=0), 1.0, atol=0.05)


# ── 파이프라인: 정보 경계·재현·정책 ─────────────────────────────────


def _small_cfg(years: list[int]) -> dict:
    c = copy.deepcopy(CFG)
    c["sample"]["evaluation_years"] = years
    return c


def _real_returns() -> pd.DataFrame:
    if not (ROOT / "data" / "raw" / "069500.csv").exists():
        pytest.skip("data/raw 없음 (원시 시세는 저장소 밖)")
    return load_returns(CFG, ROOT / "data" / "raw")


def test_annual_refit_information_boundary() -> None:
    """y 년 중간 이후 수익률을 바꿔도 그 이전 날짜의 e·T 와 이전 연도는 변하지 않는다 (사전 정보만 사용)."""
    R = _real_returns()[["069500"]]
    cfg = _small_cfg([2021, 2022])
    a = run_pipeline(R, cfg)
    R2 = R.copy()
    cut = pd.Timestamp("2022-07-01")
    R2.loc[R2.index >= cut, "069500"] *= 3.0
    b = run_pipeline(R2, cfg)
    before = np.asarray(a.eval_dates < cut)
    assert np.array_equal(a.e[..., before], b.e[..., before], equal_nan=True)
    assert np.array_equal(a.T[..., before], b.T[..., before], equal_nan=True)
    assert not np.array_equal(a.e[..., ~before], b.e[..., ~before], equal_nan=True)


def test_individual_cusum_reproduces_t12_cache() -> None:
    """관측 경로 = T12 cache e·vhat (CSV 반올림 이내) — 관측과 MC 반복이 같은 함수를 지난다는 근거."""
    root = (
        ROOT.parents[1]
        / "1016"
        / "R2H_T12_Final"
        / "outputs/t12/work/b_nb_20261016T181251/229200/daily.csv.gz"
    )
    if not root.exists():
        pytest.skip("T12 cache 없음")
    R = _real_returns()[["229200"]]
    out = run_pipeline(R, _small_cfg([2023]))
    d = pd.read_csv(root, dtype={"ticker": str, "policy": str}, parse_dates=["date"])
    for p_i, p in enumerate(("A", "B", "base")):
        b = d[(d.window == 0) & (d.policy == p)].set_index("date").reindex(out.eval_dates)
        assert np.nanmax(np.abs(b.e.to_numpy() - out.e[0, p_i])) < 1e-8
        assert np.nanmax(np.abs(b.vhat.to_numpy() - out.vhat[0, p_i])) < 1e-6


def test_policies_give_distinct_residuals() -> None:
    """세 정책은 다른 분산 입력 → 다른 잔차 (정책별 통계량을 동등 비교하려면 실제로 달라야 한다)."""
    out = run_pipeline(_real_returns()[["148070"]], _small_cfg([2022]))
    eA, eB, eb = out.e[0]
    assert not np.allclose(eA, eB, equal_nan=True) and not np.allclose(eA, eb, equal_nan=True)


def test_short_window_cusum_defined_and_not_available_mask() -> None:
    """w=3·7 은 계산 가능(유효 w 개 필요)하고 첫 w−1 일은 NaN (=NOT_AVAILABLE, 무경보 아님)."""
    e = np.random.default_rng(0).standard_normal(245)
    for w in (3, 7):
        T = rolling_cusum(e, w)
        assert np.isnan(T[: w - 1]).all() and np.isfinite(T[w - 1 :]).mean() > 0.95
        assert np.unique(np.round(T[w - 1 :], 12)).size > 50  # 퇴화(상수) 통계량이 아님
    assert all_windows(CFG) == [20, 30, 60, 120, 3, 7, 14]


# ── 공동 통계량 ────────────────────────────────────────────────────


def test_57_subsets_and_anchor_rule() -> None:
    subs = scores.all_subsets(TICKERS)
    sizes = pd.Series([len(s) for s in subs]).value_counts().to_dict()
    assert len(subs) == CFG["universe"]["n_subsets_expected"] == 57
    assert {str(k): v for k, v in sizes.items()} == CFG["universe"]["subset_sizes_expected"]
    assert scores.anchor_of(("148070", "261220"), TICKERS) == "148070"
    assert scores.anchor_of(("229200", "069500"), TICKERS) == "069500"


def test_lag_max_and_available_at() -> None:
    """시차 +2 로 잡힌 신호의 이용 가능일은 anchor+2 (미래 신호를 쓴 공동 신호는 그날 이후에만 안다)."""
    Q = np.full((1, 10), 0.0)
    Q[0, 6] = 9.0
    val, lag = scores.lag_max(Q)
    assert val[0, 4] == 9.0 and lag[0, 4] == 2  # anchor 4 → 신호 6
    assert val[0, 8] == 9.0 and lag[0, 8] == -2
    assert np.isnan(scores.lag_max(np.full((1, 3), np.nan))[0]).all()


def test_joint_all_requires_every_member_and_j2() -> None:
    st = np.array([[5.0, 1.0, np.nan], [6.0, 7.0, 3.0], [2.0, 8.0, 4.0]])
    assert np.array_equal(scores.j_all(st), np.array([2.0, 1.0, np.nan]), equal_nan=True)
    assert np.array_equal(scores.j_k(st, 2), np.array([5.0, 7.0, 3.0]))


def test_conditional_participation_regenerates_E() -> None:
    """E 는 이 자료의 J_2(S_{k−1}) ≥ c_E 로 다시 만든다. |E| < 5 이면 그 칸은 NOT_ESTIMABLE."""
    n = 50
    Q = np.zeros((3, 1, 1, n))
    Q[0, 0, 0, 10:16] = 6.0
    Q[1, 0, 0, 10:16] = 6.0  # S1 공동일 6개
    Q[2, 0, 0, :] = 1.0
    Q[2, 0, 0, 12] = 3.0
    Qlag, _ = scores.lag_max(Q)
    t3 = ["069500", "229200", "148070"]
    r = scores.stage_conditional(Q, Qlag, ("069500", "229200"), "148070", t3, 4.6, 5)
    assert r.cell_n[0, 0] == 6  # 기준 ETF(069500)는 시차 없음 → 공동일은 기준 ETF 의 6일
    assert np.isclose(
        r.stat,
        Qlag[2, 0, 0][
            (scores.j_k(scores.member_stack(Q, Qlag, ("069500", "229200"), t3), 2)[0, 0] >= 4.6)
        ].mean(),
    )
    Q[0, 0, 0, 13:16] = 0.0
    Q[1, 0, 0, 10:16] = 0.0
    Q[1, 0, 0, 10] = 6.0
    Qlag, _ = scores.lag_max(Q)
    assert np.isnan(scores.stage_conditional(Q, Qlag, ("069500", "229200"), "148070", t3, 4.6, 5).stat)


def test_tail_score_no_extrapolation() -> None:
    pool = np.random.default_rng(0).standard_normal((50, 1, 1, 1, 200))
    tt = scores.build_tail_table(pool, 1001)
    n = int(tt.n_pool[0, 0, 0])
    u = scores.tail_u(np.array([[[[1e9, -1e9, np.nan]]]]), tt)[0, 0, 0]
    assert u[0] == pytest.approx(1 / (n + 1)) and u[1] == pytest.approx(1.0) and np.isnan(u[2])


# ── 추론 (D2·D16) ──────────────────────────────────────────────────


def test_error_budget_and_fixed_sequence() -> None:
    mt = CFG["multiple_testing"]
    assert mt["alpha_primary"] + mt["alpha_secondary"] + mt["alpha_price_reserved"] == pytest.approx(
        mt["alpha_total"]
    )
    seq = inference.fixed_sequence(["SIGNIFICANT_H0B", "NULL_MODEL_INVALID", "SIGNIFICANT_H0B"])
    assert seq == ["SIGNIFICANT_H0B", "NULL_MODEL_INVALID", "CHAIN_STOPPED:SIGNIFICANT_H0B"]


def test_monte_carlo_resolution_and_floor() -> None:
    strict = 0.02 / 57
    assert inference.family_resolution_ok(28_500, strict) and not inference.family_resolution_ok(
        28_000, strict
    )
    m = inference.mc_pvalue(10.0, np.zeros(30_000))
    assert m is not None and m.at_floor and m.label().startswith("≤") and m.p == pytest.approx(1 / 30_001)
    assert inference.decide(m, strict) == "SIGNIFICANT"  # 99% 상한 1.8e-4 < 3.5e-4
    m2 = inference.mc_pvalue(10.0, np.r_[np.full(10, 11.0), np.zeros(29_990)])
    assert inference.decide(m2, strict) == "INSUFFICIENT_MONTE_CARLO"
    assert inference.mc_pvalue(np.nan, np.zeros(5)) is None


def test_holm_marks_invalid_and_stops() -> None:
    null = np.zeros(1000)
    p = {
        "a": inference.mc_pvalue(5.0, null),
        "b": inference.mc_pvalue(-1.0, null),
        "c": inference.mc_pvalue(5.0, null),
    }
    out = inference.holm(p, 0.02, {"a": True, "b": True, "c": False})
    assert out == {"a": "SIGNIFICANT_H0B", "b": "NOT_SIGNIFICANT", "c": "NULL_MODEL_INVALID"}


def test_null_model_invalid_decision() -> None:
    """구성원 하나라도 N3 탈락이면 그 통계량은 NULL_MODEL_INVALID (CCC 로 대체하지 않는다)."""
    n3 = [
        {"ticker": "069500", "N3_pass": True},
        {"ticker": "153130", "N3_pass": False},
        {"ticker": "229200", "N3_pass": True},
    ]
    n4 = [
        {"pair": "069500+229200", "N4_pass": True},
        {"pair": "069500+153130", "N4_pass": True},
        {"pair": "229200+153130", "N4_pass": True},
    ]
    assert validity.statistic_valid(("069500", "229200"), True, n3, n4)
    assert not validity.statistic_valid(("069500", "153130"), True, n3, n4)
    assert not validity.statistic_valid(("069500", "229200"), False, n3, n4)
    cal = {
        "diag_zero_share": np.zeros((100, 1)),
        "diag_kurt": np.zeros((100, 1)),
        "diag_acf_r2": np.zeros((100, 1)),
        "diag_var": np.ones((100, 1)),
    }
    row = validity.n3_table(
        {
            "zero_share": np.array([0.172]),
            "kurt": np.array([0.0]),
            "acf_r2": np.array([0.0]),
            "var": np.array([1.0]),
        },
        cal,
        ["153130"],
    )[0]
    assert not row["zero_share_ok"] and not row["N3_pass"]
    row2 = validity.n3_table(
        {
            "zero_share": np.array([0.008]),
            "kurt": np.array([0.0]),
            "acf_r2": np.array([0.0]),
            "var": np.array([1.0]),
        },
        cal,
        ["069500"],
    )[0]
    assert row2["N3_pass"]


def test_episode_boundaries_and_excess() -> None:
    flag = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1], bool)
    assert scores.run_lengths(flag) == [(1, 2), (4, 4), (7, 9)]
    j = np.array([0, 5, 6, 0, 5, np.nan, 0, 5, 5, 7.0])
    best, longest = scores.max_cumulative_excess(j, 4.0)
    assert best == pytest.approx(1 + 1 + 3) and longest == 3


def test_h0a_same_transform_for_all_policies() -> None:
    """한 ETF-연도의 정책 경로는 같은 변환을 받는다 (정책별 다른 무작위 시차 금지)."""
    yod = np.repeat([2021, 2022], 100)
    Q = np.random.default_rng(1).random((1, 3, 2, 200))
    Q[:, 1] = Q[:, 0] * 2
    out, _ = h0a.transform_Q(Q, yod, [20, 30], "circular_shift", np.random.default_rng(4))
    assert np.allclose(out[:, 1], out[:, 0] * 2, equal_nan=True)
    assert np.isnan(out[0, 0, 0, :19]).all()  # 유효 구간 밖은 NaN 유지


def test_same_seed_determinism_of_rng() -> None:
    a = mc.rep_rng(CFG, "calibration", 5).standard_normal(5)
    b = mc.rep_rng(CFG, "calibration", 5).standard_normal(5)
    c = mc.rep_rng(CFG, "null_eval_dcc", 5).standard_normal(5)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_energy_statistic_boundaries() -> None:
    e = np.ones((1, 130))
    yod = np.repeat([2021], 130)
    E = mc.energy(e, yod, [1, 3])
    assert np.isnan(E[0, 0, :60]).all() and np.isfinite(E[0, 0, 60:]).all() and np.allclose(E[0, 0, 60:], 0.0)
    assert np.isnan(E[0, 1, :62]).all()
