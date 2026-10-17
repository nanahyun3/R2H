# ruff: noqa: E501  — 한국어 설명·표 머리 문자열
"""W3 관측 분석 — 관측 경로 · 검정 판정 · 공동 구간 · 방향 · 순차 탐지 · 가격 반응 (노트북 08 이 호출).

관측 경로는 MC 반복과 같은 ``run_pipeline``·``q_score``·``rep_statistics`` 를 지난다. MC 결과는 Git 제외
``outputs/t15/mc/`` 에서 읽는다. 판정 규칙은 계약 W3-lock-1 과 설정 JSON 그대로다.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.multihorizon.core import log_variance_ratio, midrank_past, realized_variance

from . import inference
from .mc import energy, return_diagnostics
from .pipeline import POLICIES, PipelineOut, load_returns, run_pipeline
from .scores import (
    TailTable,
    all_subsets,
    anchor_of,
    j_all,
    j_k,
    lag_max,
    member_stack,
    q_score,
    rep_statistics,
    run_lengths,
    stage_conditional,
)
from .validity import n1_tables, n3_table, n4_table, statistic_valid

STAGES = ["S1", "S2", "S3", "S4", "S5"]
PRIMARY_W = [20, 30, 60, 120]


@dataclass
class Obs:
    cfg: dict
    root: Path
    R: pd.DataFrame  # 관측 수익률 2019-01-03..2025-12-30
    out: PipelineOut
    tt: TailTable
    Q: np.ndarray  # (ETF, 정책, 주 창, 일)
    Qlag: np.ndarray
    lag_used: np.ndarray
    tickers: list[str]
    subsets: list[tuple[str, ...]]

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.out.eval_dates


def mc_dir(root: Path) -> Path:
    return root / "outputs" / "t15" / "mc"


def load_obs(cfg: dict, root: Path) -> Obs:
    """관측 6종을 MC 와 같은 함수로 처리하고 보정 꼬리표로 Q 를 만든다."""
    R = load_returns(cfg, root / "data" / "raw")
    out = run_pipeline(R, cfg)
    z = np.load(mc_dir(root) / "tail_table.npz")
    tt = TailTable(z["table"], z["n_pool"], z["edges"])
    Q = q_score(out.T[:, :, :4], tt, out.pos_in_year)
    Qlag, lag_used = lag_max(Q)
    tickers = list(cfg["universe"]["tickers"])
    return Obs(cfg, root, R, out, tt, Q, Qlag, lag_used, tickers, all_subsets(tickers))


def sub_name(s: tuple[str, ...]) -> str:
    return "+".join(s)


# ── 귀무 적합도 ────────────────────────────────────────────────────


def null_validity(obs: Obs) -> dict:
    """N1 (연도별 적합) · N3 · N4 (연도 모형별 envelope, 2/5 규칙) · Ljung–Box → 통계량별 H0-B 유효성. N5 는 따로 진단."""
    d = mc_dir(obs.root)
    years = list(obs.cfg["sample"]["evaluation_years"])
    n1 = pd.read_csv(d / "null_model_N1.csv")
    lb = pd.read_csv(d / "null_model_ljungbox.csv", dtype={"ticker": str})
    etf_ok, joint_ok = n1_tables(n1, len(obs.tickers))
    cal = dict(np.load(d / "cal_diag.npz"))
    per = [return_diagnostics(obs.R[obs.R.index < pd.Timestamp(f"{y}-01-01")].to_numpy()) for y in years]
    od = {k: np.stack([x[k] for x in per]) for k in per[0]}
    n3 = n3_table(od, cal, lb, etf_ok, obs.tickers, years)
    n4 = n4_table(od, cal, obs.tickers, years)
    valid_sub = {sub_name(s): statistic_valid(s, joint_ok, n3, n4) for s in obs.subsets}
    stages = obs.cfg["universe"]["stages"]
    valid_stage = {k: statistic_valid(tuple(stages[k]), joint_ok, n3, n4) for k in STAGES}
    return {
        "n1": n1,
        "n1_joint_ok": joint_ok,
        "n1_etf_ok": dict(zip(obs.tickers, etf_ok.tolist(), strict=True)),
        "n3": pd.DataFrame(n3),
        "n4": pd.DataFrame(n4),
        "lb": lb,
        "valid_subset": valid_sub,
        "valid_stage": valid_stage,
    }


def n5_marginal(obs: Obs, max_reps: int = 2000) -> pd.DataFrame:
    """N5 진단 (게이트 아님): 관측 T 의 중앙값·IQR 이 보정 반복 envelope 안인가 (ETF·정책·주 창)."""
    T = np.load(mc_dir(obs.root) / "cal_T.npy", mmap_mode="r")
    rows = []
    for i, tk in enumerate(obs.tickers):
        for p_i, p in enumerate(POLICIES):
            for w_i, w in enumerate(PRIMARY_W):
                cal = np.asarray(T[:max_reps, i, p_i, w_i, :], dtype=np.float64)
                med = np.nanmedian(cal, axis=1)
                iqr = np.nanquantile(cal, 0.75, axis=1) - np.nanquantile(cal, 0.25, axis=1)
                x = obs.out.T[i, p_i, w_i]
                om, oi = float(np.nanmedian(x)), float(np.nanquantile(x, 0.75) - np.nanquantile(x, 0.25))
                rows.append(
                    {
                        "ticker": tk,
                        "policy": p,
                        "w": w,
                        "median_obs": om,
                        "median_lo": float(np.quantile(med, 0.005)),
                        "median_hi": float(np.quantile(med, 0.995)),
                        "iqr_obs": oi,
                        "iqr_lo": float(np.quantile(iqr, 0.005)),
                        "iqr_hi": float(np.quantile(iqr, 0.995)),
                        "median_inside": bool(np.quantile(med, 0.005) <= om <= np.quantile(med, 0.995)),
                        "iqr_inside": bool(np.quantile(iqr, 0.005) <= oi <= np.quantile(iqr, 0.995)),
                    }
                )
    return pd.DataFrame(rows)


# ── 검정 ───────────────────────────────────────────────────────────


def _load(name: str, root: Path) -> dict[str, np.ndarray]:
    return dict(np.load(mc_dir(root) / f"{name}.npz"))


def h0a_status(pa: dict[str, inference.MCP | None], alpha: float) -> bool:
    """H0-A 기각 = 두 방법 모두 기각 (합산하지 않고 교집합으로만 쓴다 — 보수적 규칙, H0-A 계산 전 고정)."""
    return all(m is not None and m.p <= alpha for m in pa.values())


def test_tables(obs: Obs, val: dict, cond_valid: dict[str, bool] | None = None) -> dict[str, pd.DataFrame]:
    """주 경로 S1–S5 (고정 순서) 와 57개 부분집합 (Holm) 판정표. DCC 주, CCC·H0-A 민감도."""
    cfg = obs.cfg
    st = rep_statistics(obs.Q, cfg)
    dccn, cccn = _load("null_eval_dcc", obs.root), _load("null_eval_ccc", obs.root)
    h0a = {m: _load(f"h0a_{m}", obs.root) for m in cfg["null_models"]["H0A"]["methods"]}
    a1 = cfg["multiple_testing"]["alpha_primary"]
    a2 = cfg["multiple_testing"]["alpha_secondary"]
    B = dccn["M_subset"].shape[0]
    # 주 경로
    rows, raw_status = [], []
    for k, name in enumerate(STAGES):
        if k == 0:
            obs_v, nd, nc = st.M_subset[0], dccn["M_subset"][:, 0], cccn["M_subset"][:, 0]
            na = {m: h0a[m]["M_subset"][:, 0] for m in h0a}
            stat_name = "M_S1 = max J_all(S1)"
        else:
            obs_v, nd, nc = st.C_stage[k - 1], dccn["C_stage"][:, k - 1], cccn["C_stage"][:, k - 1]
            na = {m: h0a[m]["C_stage"][:, k - 1] for m in h0a}
            stat_name = f"C_{name} (신규 {cfg['universe']['stage_new_ticker'][name]} 조건부 참여)"
        pd_, pc = inference.mc_pvalue(obs_v, nd), inference.mc_pvalue(obs_v, nc)
        pa = {m: inference.mc_pvalue(obs_v, na[m]) for m in na}
        valid = val["valid_stage"][name]
        cvalid = True if (k == 0 or cond_valid is None) else cond_valid[name]
        d = inference.decide(pd_, a1)
        if pd_ is None:
            s = "NOT_ESTIMABLE"
        elif not valid or not cvalid:
            s = "NULL_MODEL_INVALID"
        elif d == "SIGNIFICANT":
            s = "SIGNIFICANT_H0B"
        elif d == "INSUFFICIENT_MONTE_CARLO":
            s = d
        else:
            s = "SIGNIFICANT_H0A_ONLY" if h0a_status(pa, a1) else "NOT_SIGNIFICANT"
        raw_status.append(s)
        j2p = inference.mc_pvalue(st.M2_stage[k], dccn["M2_stage"][:, k])
        s_idx = obs.subsets.index(tuple(cfg["universe"]["stages"][name]))
        jap = inference.mc_pvalue(st.M_subset[s_idx], dccn["M_subset"][:, s_idx])
        rows.append(
            {
                "stage": name,
                "members": sub_name(tuple(cfg["universe"]["stages"][name])),
                "statistic": stat_name,
                "obs": obs_v,
                "B_dcc": B,
                "k_exceed_dcc": None if pd_ is None else pd_.k,
                "p_dcc": None if pd_ is None else pd_.p,
                "p_dcc_label": "" if pd_ is None else pd_.label(),
                "p_dcc_ci99_low": None if pd_ is None else pd_.ci_low,
                "p_dcc_ci99_high": None if pd_ is None else pd_.ci_high,
                "h0b_valid": valid,
                "conditional_null_valid": cvalid,
                "p_ccc": None if pc is None else pc.p,
                **{f"p_h0a_{m}": (None if pa[m] is None else pa[m].p) for m in pa},
                "status": s,
                "j2_obs": st.M2_stage[k],
                "j2_p_dcc_descriptive": None if j2p is None else j2p.p,
                "jall_obs": st.M_subset[s_idx],
                "jall_p_dcc_descriptive": None if jap is None else jap.p,
            }
        )
    seq = inference.fixed_sequence(raw_status)
    stage = pd.DataFrame(rows)
    stage["confirmatory_status"] = seq
    # 부분집합
    names = [sub_name(s) for s in obs.subsets]
    pvals = {n: inference.mc_pvalue(st.M_subset[i], dccn["M_subset"][:, i]) for i, n in enumerate(names)}
    fam_ok = inference.family_resolution_ok(B, a2 / len(names))
    holm = inference.holm(pvals, a2, val["valid_subset"])
    if not fam_ok:
        holm = {
            n: ("INSUFFICIENT_MONTE_CARLO" if v not in ("NOT_ESTIMABLE", "NULL_MODEL_INVALID") else v)
            for n, v in holm.items()
        }
    minp = inference.minp_adjusted(
        {n: st.M_subset[i] for i, n in enumerate(names)}, dccn["M_subset"], names, val["valid_subset"]
    )
    ccc_fam_ok = inference.family_resolution_ok(cccn["M_subset"].shape[0], a2 / len(names))
    srows = []
    for i, s in enumerate(obs.subsets):
        n = names[i]
        m = pvals[n]
        pc = inference.mc_pvalue(st.M_subset[i], cccn["M_subset"][:, i])
        pa = {mm: inference.mc_pvalue(st.M_subset[i], h0a[mm]["M_subset"][:, i]) for mm in h0a}
        status = holm[n]
        if status == "NOT_SIGNIFICANT" and h0a_status(pa, a2 / len(names)):
            status = "SIGNIFICANT_H0A_ONLY"
        srows.append(
            {
                "subset": n,
                "size": len(s),
                "anchor": anchor_of(s, obs.tickers),
                "contains_153130": "153130" in s,
                "M_obs": st.M_subset[i],
                "k_exceed_dcc": None if m is None else m.k,
                "p_dcc": None if m is None else m.p,
                "p_dcc_label": "" if m is None else m.label(),
                "p_dcc_ci99_low": None if m is None else m.ci_low,
                "p_dcc_ci99_high": None if m is None else m.ci_high,
                "h0b_valid": val["valid_subset"][n],
                "holm_status": holm[n],
                "status": status,
                "p_minp_adjusted": minp.get(n),
                "p_ccc": None if pc is None else pc.p,
                "ccc_family_status": "OK" if ccc_fam_ok else "INSUFFICIENT_MONTE_CARLO",
                **{f"p_h0a_{mm}": (None if pa[mm] is None else pa[mm].p) for mm in pa},
                "J2_obs_descriptive": st.M2_subset[i],
                "cum_excess_obs": st.cum_excess[i],
                "longest_run_obs": st.longest_run[i],
            }
        )
    sub = pd.DataFrame(srows)
    return {
        "stage": stage,
        "subset": sub,
        "family_resolution_ok": pd.DataFrame(
            [
                {
                    "family": "secondary_57",
                    "B": B,
                    "strictest": a2 / len(names),
                    "B_x_strictest": B * a2 / len(names),
                    "ok": fam_ok,
                }
            ]
        ),
    }


def conditional_null_check(obs: Obs) -> tuple[pd.DataFrame, dict[str, bool]]:
    """승인서 §7.4·§12: 앞 단계는 실제로 변하고 신규 ETF 는 변하지 않는 H1_POWER 시나리오에서 C_Sk 기각률 (α=0.02).

    S2–S5 는 V1 (S1 만 분산 ×2), S3–S5 는 V2 (S1+148070 ×2) 에서 본다. Wilson 95% 하한이 0.02 를 넘으면
    그 단계의 조건부 귀무는 성립하지 않는다 → NULL_MODEL_INVALID (확증 사슬 중단).
    """
    cfg = obs.cfg
    alt = pickle.load(open(mc_dir(obs.root) / "alt_results.pkl", "rb"))
    dccn = _load("null_eval_dcc", obs.root)
    a1 = cfg["multiple_testing"]["alpha_primary"]
    crit = [
        float(
            np.quantile(
                np.where(np.isfinite(dccn["C_stage"][:, k]), dccn["C_stage"][:, k], -np.inf),
                1 - a1,
                method="higher",
            )
        )
        for k in range(4)
    ]
    checks = {"V1": STAGES[1:], "V2": STAGES[2:]}
    rows, ok = [], {s: True for s in STAGES[1:]}
    for scen, stages in checks.items():
        reps = [r for (n, _), r in alt if n == scen]
        for stg in stages:
            k = STAGES.index(stg) - 1
            rej = sum(bool(np.isfinite(r["C_stage"][k]) and r["C_stage"][k] >= crit[k]) for r in reps)
            lo, hi = inference.wilson(rej, len(reps))
            valid = lo <= a1
            ok[stg] &= valid
            rows.append(
                {
                    "scenario": scen,
                    "stage": stg,
                    "new_etf_unchanged": cfg["universe"]["stage_new_ticker"][stg],
                    "R": len(reps),
                    "rejections": rej,
                    "rate": rej / len(reps),
                    "wilson_low": lo,
                    "wilson_high": hi,
                    "alpha": a1,
                    "conditional_null_valid": valid,
                }
            )
    return pd.DataFrame(rows), ok


def size_check(obs: Obs) -> pd.DataFrame:
    """holdout 귀무 반복을 관측처럼 판정 → 실제 크기 (S1 0.02, S2–S5 각 0.02, 부분집합 Holm 가족 FWER)."""
    cfg = obs.cfg
    dccn, hold = _load("null_eval_dcc", obs.root), _load("null_eval_holdout", obs.root)
    a1, a2 = cfg["multiple_testing"]["alpha_primary"], cfg["multiple_testing"]["alpha_secondary"]
    B = dccn["M_subset"].shape[0]

    def pv(x: np.ndarray, null: np.ndarray) -> np.ndarray:
        srt = np.sort(np.where(np.isfinite(null), null, -np.inf))
        k = B - np.searchsorted(srt, x, side="left")
        p = (1 + k) / (B + 1)
        return np.where(np.isfinite(x), p, np.nan)

    rows = []
    H = hold["M_subset"].shape[0]
    p1 = pv(hold["M_subset"][:, 0], dccn["M_subset"][:, 0])
    rows.append(_size_row("S1 (M_S1, α=0.02)", int(np.nansum(p1 <= a1)), H, a1))
    for k in range(4):
        pk = pv(hold["C_stage"][:, k], dccn["C_stage"][:, k])
        rows.append(
            _size_row(
                f"{STAGES[k + 1]} 조건부 참여 (α=0.02, 추정 불가 반복은 비기각)",
                int(np.nansum(pk <= a1)),
                H,
                a1,
            )
        )
    P = np.column_stack(
        [pv(hold["M_subset"][:, i], dccn["M_subset"][:, i]) for i in range(hold["M_subset"].shape[1])]
    )
    m = P.shape[1]
    rej = 0
    for r in range(H):
        ps = np.sort(np.where(np.isfinite(P[r]), P[r], 1.0))
        thr = a2 / (m - np.arange(m))
        rej += int(ps[0] <= thr[0])  # Holm 가족 FWER = 첫 단계 기각 여부
    rows.append(_size_row("부분집합 57 Holm 가족 (FWER α=0.02)", rej, H, a2))
    return pd.DataFrame(rows)


def _size_row(label: str, k: int, n: int, alpha: float) -> dict:
    lo, hi = inference.wilson(k, n)
    return {
        "test": label,
        "rejections": k,
        "R": n,
        "size": k / n,
        "wilson_low": lo,
        "wilson_high": hi,
        "nominal": alpha,
        "within": lo <= alpha <= hi or hi < alpha,
    }


# ── 합성 검정력 ─────────────────────────────────────────────────────


def power_tables(obs: Obs) -> dict[str, pd.DataFrame]:
    """대립 시나리오: 경로 수준 판정 · 변화 후 유의일 검출률/지연 · 참여 · 구간 경계 · 단기 q 대비 CUSUM 지연."""
    cfg = obs.cfg
    d = mc_dir(obs.root)
    alt = pickle.load(open(d / "alt_results.pkl", "rb"))
    dccn = _load("null_eval_dcc", obs.root)
    a1 = cfg["multiple_testing"]["alpha_primary"]
    crit_M1 = float(np.quantile(dccn["M_subset"][:, 0], 1 - a1, method="higher"))
    crit_C = [
        float(
            np.nanquantile(
                np.where(np.isfinite(dccn["C_stage"][:, k]), dccn["C_stage"][:, k], -np.inf),
                1 - a1,
                method="higher",
            )
        )
        for k in range(4)
    ]
    hz = cfg["alternatives"]["detection_horizon_days"]
    by: dict[str, list[dict]] = {}
    for (name, _), r in alt:
        by.setdefault(name, []).append(r)
    prow, drow, lrow = [], [], []
    for name, reps in sorted(by.items()):
        n = len(reps)
        rec: dict = {"scenario": name, "R": n}
        k1 = sum(r["M_subset"][0] >= crit_M1 for r in reps)
        rec["path_S1_reject"] = k1 / n
        for k in range(4):
            kk = sum(np.isfinite(r["C_stage"][k]) and r["C_stage"][k] >= crit_C[k] for r in reps)
            rec[f"path_{STAGES[k + 1]}_cond_reject"] = kk / n
        prow.append(rec)
        fams = sorted({k.split(":detected_60")[0] for r in reps for k in r if k.endswith(":detected_60")})
        for fam in fams:
            det = [r[f"{fam}:detected_60"] for r in reps]
            delay = np.array([r[f"{fam}:delay"] for r in reps], float)
            row = {"scenario": name, "family": fam, "R": n, "detected_60": sum(det) / n}
            lo, hi = inference.wilson(sum(det), n)
            row.update(detected_60_wilson_low=lo, detected_60_wilson_high=hi)
            for h in hz:
                row[f"detected_within_{h}"] = float(np.sum(delay < h) / n)
            row["median_delay_detected"] = float(np.nanmedian(delay)) if np.isfinite(delay).any() else np.nan
            row["n_detected"] = int(np.isfinite(delay).sum())
            row["false_sig_before_tau"] = float(np.mean([r[f"{fam}:any_sig_before_tau"] for r in reps]))
            es = np.array([r.get(f"{fam}:ep_start_err", np.nan) for r in reps], float)
            ee = np.array([r.get(f"{fam}:ep_end_err", np.nan) for r in reps], float)
            row["ep_start_err_median"] = float(np.nanmedian(es)) if np.isfinite(es).any() else np.nan
            row["ep_end_err_median"] = float(np.nanmedian(ee)) if np.isfinite(ee).any() else np.nan
            drow.append(row)
        aff = np.stack([r["affected_mask"] for r in reps])
        par = np.stack([r["participated"] for r in reps])
        recall = par[aff].mean() if aff.any() else np.nan
        over = par[~aff].mean() if (~aff).any() else np.nan
        prow[-1].update(participation_recall=recall, over_participation=over)
        keys = sorted({k for r in reps for v in r["delays"].values() for k in v})
        for key in keys:
            vals = np.array([v[key] for r in reps for v in r["delays"].values()], float)
            if vals.size == 0:
                continue
            lrow.append(
                {
                    "scenario": name,
                    "signal": key,
                    "n_affected_etf_reps": vals.size,
                    "detected_60": float(np.isfinite(vals).mean()),
                    "median_delay": float(np.nanmedian(vals)) if np.isfinite(vals).any() else np.nan,
                }
            )
    return {
        "path": pd.DataFrame(prow),
        "detection": pd.DataFrame(drow),
        "delays": pd.DataFrame(lrow),
        "criticals": pd.DataFrame(
            [{"crit_M_S1_q98": crit_M1, **{f"crit_C_{STAGES[k + 1]}_q98": crit_C[k] for k in range(4)}}]
        ),
    }


def short_window_eligibility(obs: Obs, delays: pd.DataFrame) -> pd.DataFrame:
    """w=3·7·14 (및 참고 20–120) W1 규칙을 W3 own-valid 표본에 적용: holdout 귀무 크기 · V1 검출·지연 · 퇴화.

    임계값 = H0_CALIBRATION own-valid 연간 최대의 95% 분위 (ETF·정책·창). 검출은 V1 의 영향 ETF (069500·229200) 풀.
    """
    d = mc_dir(obs.root)
    crit = json.loads((d / "w3_individual_criticals.json").read_text())
    hold = _load("null_eval_holdout", obs.root)["annual_max_own"]
    T = np.load(d / "cal_T.npy", mmap_mode="r")
    v1 = delays[delays.scenario.eq("V1")].set_index("signal")
    wins = PRIMARY_W + list(obs.cfg["pipeline"]["windows_short_eligibility"])
    rows = []
    for i, tk in enumerate(obs.tickers):
        for p_i, p in enumerate(POLICIES):
            for w_i, w in enumerate(wins):
                c = crit[f"w3:{tk}:{p}:{w}"]
                h = hold[:, i, p_i, w_i, :].ravel()
                h = h[np.isfinite(h)]
                k = int(np.sum(h >= c))
                _, hi = inference.wilson(k, h.size)
                sample = np.asarray(T[:200, i, p_i, w_i, :], dtype=np.float64)[
                    :, obs.out.pos_in_year >= w - 1
                ]
                rows.append(
                    {
                        "ticker": tk,
                        "policy": p,
                        "w": w,
                        "role": "단기 적격성 연구" if w in (3, 7, 14) else "주 창 (참고, W1 판정 불변)",
                        "crit_w3_annual_max_q95": c,
                        "null_any_alarm_per_etf_year": k / max(h.size, 1),
                        "null_wilson_high": hi,
                        "size_ok": hi <= 0.10,
                        "nan_share_own_valid": float(np.mean(~np.isfinite(sample))),
                        "distinct_values_200reps": int(
                            np.unique(np.round(sample[np.isfinite(sample)], 10)).size
                        ),
                    }
                )
    df = pd.DataFrame(rows)
    det, med, n = [], [], []
    for _, r in df.iterrows():
        key = f"cusum_w3crit_{r.policy}_w{r.w}"
        if key in v1.index:
            det.append(v1.loc[key, "detected_60"])
            med.append(v1.loc[key, "median_delay"])
            n.append(v1.loc[key, "n_affected_etf_reps"])
        else:
            det.append(np.nan)
            med.append(np.nan)
            n.append(0)
    df["v1_detected_60_pooled_affected"] = det
    df["v1_median_delay"] = med
    df["v1_n"] = n
    lo = [
        inference.wilson(round(dd * nn), int(nn))[0] if nn else np.nan
        for dd, nn in zip(df.v1_detected_60_pooled_affected, df.v1_n, strict=True)
    ]
    df["v1_detected_wilson_low"] = lo
    df["power_ok"] = (
        (df.v1_detected_wilson_low >= 0.15)
        & (df.v1_detected_60_pooled_affected * df.v1_n >= 30)
        & (df.v1_median_delay <= 30)
    )
    df["verdict"] = np.where(df.size_ok & df.power_ok, "ELIGIBLE", "NOT_ELIGIBLE")
    return df


def robustness_compare(obs: Obs) -> pd.DataFrame:
    """승인서 §10 초기 조건 민감도: burn-in 2000 (ROBUSTNESS) 대 500 (주) 의 주 통계량 귀무 분위."""
    a, b = _load("null_eval_dcc", obs.root), _load("null_eval_robustness", obs.root)
    rows = []
    for name, ka, idx in [("M_S1", "M_subset", 0)] + [(f"C_{STAGES[k + 1]}", "C_stage", k) for k in range(4)]:
        x, y = a[ka][:, idx], b[ka][:, idx]
        x, y = x[np.isfinite(x)], y[np.isfinite(y)]
        for q in (0.5, 0.9, 0.98):
            rows.append(
                {
                    "statistic": name,
                    "quantile": q,
                    "burn500": float(np.quantile(x, q)),
                    "burn2000": float(np.quantile(y, q)),
                    "n500": x.size,
                    "n2000": y.size,
                }
            )
    return pd.DataFrame(rows)


def h0a_diagnostics(obs: Obs) -> pd.DataFrame:
    """H0-A 진단: 방법별 반복 수 · 고유 변환 수 (중복) · 평균 접합부 수 · 허용 이동 수 (창별 유효 구간 길이 범위)."""
    rows = []
    L = {
        w: [
            int(np.sum((obs.out.year_of_day == y) & (obs.out.pos_in_year >= w - 1)))
            for y in np.unique(obs.out.year_of_day)
        ]
        for w in PRIMARY_W
    }
    for m in obs.cfg["null_models"]["H0A"]["methods"]:
        z = _load(f"h0a_{m}", obs.root)
        rows.append(
            {
                "method": m,
                "reps": int(z["junction"].size),
                "unique_transforms": int(np.unique(z["transform_key"]).size),
                "mean_junctions": float(z["junction"].mean()),
                "allowed_shifts_per_etf_year_w20_to_w120": "; ".join(
                    f"w{w}:{min(v)}–{max(v)}" for w, v in L.items()
                ),
                "year_boundary": "변환은 연도 안에서만 (경계 넘지 않음)",
            }
        )
    return pd.DataFrame(rows)


# ── 일별 공동 점수·구간 ────────────────────────────────────────────


def joint_daily(obs: Obs, s: tuple[str, ...]) -> pd.DataFrame:
    """한 집합의 일별 J_all·J_2 (정책·창 최대), 최대를 만든 (정책, w), 이용 가능 시차, 구성원별 Q."""
    st = member_stack(obs.Q, obs.Qlag, s, obs.tickers)
    a = anchor_of(s, obs.tickers)
    others = [t for t in s if t != a]
    lags = np.stack([np.zeros_like(obs.lag_used[0])] + [obs.lag_used[obs.tickers.index(t)] for t in others])
    ja = j_all(st)
    j2 = j_k(st, 2)
    flat = np.where(np.isfinite(ja), ja, -np.inf).reshape(-1, ja.shape[-1])
    arg = flat.argmax(axis=0)
    jmax = flat[arg, np.arange(flat.shape[1])]
    jmax[~np.isfinite(jmax)] = np.nan
    p_i, w_i = np.unravel_index(arg, ja.shape[:2])
    off = np.nanmax(np.where(np.isfinite(lags), lags, 0), axis=0)  # 구성원이 쓴 가장 큰 양의 시차
    off_at = np.maximum(0, off[p_i, w_i, np.arange(len(arg))])
    j2max = np.where(np.isfinite(j2), j2, -np.inf).max(axis=(0, 1))
    j2max[~np.isfinite(j2max)] = np.nan
    df = pd.DataFrame(
        {
            "date": obs.dates,
            "subset": sub_name(s),
            "J_all_max": jmax,
            "argmax_policy": np.array(POLICIES)[p_i],
            "argmax_w": np.array(PRIMARY_W)[w_i],
            "available_offset": np.where(np.isfinite(jmax), off_at, np.nan),
            "J2_max": j2max,
        }
    )
    for t in s:
        q = obs.Qlag[obs.tickers.index(t)] if t != a else obs.Q[obs.tickers.index(t)]
        df[f"Q_{t}"] = q[p_i, w_i, np.arange(len(arg))]
    return df


def episodes(obs: Obs, tests: dict[str, pd.DataFrame], val: dict) -> pd.DataFrame:
    """탐색 구간 = J_all_max ≥ c0 연속일. 유의일(≥ 유의일 기준)·구간 수준 p·상태·시점 필드를 붙인다."""
    cfg = obs.cfg
    c0 = float(cfg["episodes"]["episode_level_threshold_c0"])
    dccn = _load("null_eval_dcc", obs.root)
    a1, a2 = cfg["multiple_testing"]["alpha_primary"], cfg["multiple_testing"]["alpha_secondary"]
    B = dccn["M_subset"].shape[0]
    s1 = tuple(cfg["universe"]["stages"]["S1"])
    sub_status = tests["subset"].set_index("subset").status.to_dict()
    s1_status = tests["stage"].set_index("stage").loc["S1", "status"]
    inference_done = json.loads((mc_dir(obs.root) / "inference_meta.json").read_text())["completed_at"]
    rows = []
    dates = obs.dates
    for s_i, s in enumerate(obs.subsets):
        dj = joint_daily(obs, s)
        lvl = a1 if s == s1 else a2 / len(obs.subsets)
        crit = float(np.quantile(dccn["M_subset"][:, s_i], 1 - lvl, method="higher"))
        j = dj.J_all_max.to_numpy()
        flag = np.isfinite(j) & (j >= c0)
        null_ce = dccn["cum_excess"][:, s_i]
        for a, b in run_lengths(flag):
            seg = j[a : b + 1]
            ce = float((seg - c0).sum())
            k = int(np.sum(null_ce >= ce))
            p_ep = (1 + k) / (B + 1)
            n_sig = int(np.sum(seg >= crit))
            glob = s1_status if s == s1 else sub_status[sub_name(s)]
            if not val["valid_subset"][sub_name(s)]:
                day_status = "NULL_MODEL_INVALID"
            elif n_sig > 0 and glob == "SIGNIFICANT_H0B":
                day_status = "SIGNIFICANT_H0B"
            elif n_sig > 0 and glob == "INSUFFICIENT_MONTE_CARLO":
                day_status = "INSUFFICIENT_MONTE_CARLO"
            else:
                day_status = "EXPLORATORY"
            ep_status = "EXPLORATORY"
            if s == s1 and day_status == "SIGNIFICANT_H0B":
                ep_status = "SIGNIFICANT_H0B" if p_ep <= a1 else "NOT_SIGNIFICANT"
            peak = a + int(np.nanargmax(seg))
            first_avail = a + int(dj.available_offset.iloc[a])
            stage = next((k_ for k_ in STAGES if set(s) <= set(cfg["universe"]["stages"][k_])), "OFF_PATH")
            rows.append(
                {
                    "subset": sub_name(s),
                    "size": len(s),
                    "stage_min_containing": stage,
                    "episode_start_at": dates[a].date(),
                    "episode_end_at": dates[b].date(),
                    "joint_anchor_at": dates[peak].date(),
                    "joint_confirmed_at": dates[min(first_avail, len(dates) - 1)].date(),
                    "episode_confirmed_at": "RIGHT_CENSORED"
                    if b == len(dates) - 1
                    else str(dates[b + 1].date()),
                    "n_days": b - a + 1,
                    "duration_trading_days": b - a + 1,
                    "max_J": float(np.nanmax(seg)),
                    "cumulative_excess": ce,
                    "n_days_ge_day_critical": n_sig,
                    "day_critical": crit,
                    "peak_policy": dj.argmax_policy.iloc[peak],
                    "peak_w": int(dj.argmax_w.iloc[peak]),
                    "retrospective_p_value": p_ep,
                    "p_label": f"≤ {1 / (B + 1):.2g}" if k == 0 else f"{p_ep:.4g}",
                    "day_level_status": day_status,
                    "episode_level_status": ep_status,
                    "inference_completed_at": inference_done,
                }
            )
    return pd.DataFrame(rows)


def direction(obs: Obs, ep: pd.DataFrame) -> pd.DataFrame:
    """구간 e² 평균 / 직전 60 평가일 e² 평균 (최대 정책) → 확대 ≥1.25 · 축소 ≤0.8 (유의성 주장 없음)."""
    cfg = obs.cfg
    up, dn = cfg["direction"]["expansion_if_ratio_ge"], cfg["direction"]["contraction_if_ratio_le"]
    pos = {d.date(): k for k, d in enumerate(obs.dates)}
    out = []
    for _, r in ep.iterrows():
        a, b = pos[r.episode_start_at], pos[r.episode_end_at]
        p_i = POLICIES.index(r.peak_policy)
        labels, ratios = [], []
        for t in r.subset.split("+"):
            e = obs.out.e[obs.tickers.index(t), p_i]
            if a < 60:
                labels.append("UNDETERMINED")
                ratios.append(np.nan)
                continue
            num = np.nanmean(e[a : b + 1] ** 2)
            den = np.nanmean(e[a - 60 : a] ** 2)
            ratio = num / den if den > 0 else np.nan
            ratios.append(ratio)
            labels.append("EXP" if ratio >= up else ("CON" if ratio <= dn else "UNDETERMINED"))
        if all(x == "EXP" for x in labels):
            lab = "COMMON_EXPANSION"
        elif all(x == "CON" for x in labels):
            lab = "COMMON_CONTRACTION"
        elif "EXP" in labels and "CON" in labels:
            lab = "MIXED"
        else:
            lab = "UNDETERMINED"
        out.append(
            {
                "direction": lab,
                "member_ratios": ";".join(f"{x:.2f}" for x in ratios),
                "member_labels": ";".join(labels),
            }
        )
    return pd.concat([ep.reset_index(drop=True), pd.DataFrame(out)], axis=1)


# ── 순차 탐지 (승인서 §5) ──────────────────────────────────────────


def q_signals(obs: Obs) -> dict[str, pd.DataFrame]:
    """ETF 별 일별 q 신호 (W2 규칙, 엄밀 과거 확장형 mid-rank ≥252): q=1 일간 충격, q≥3 확대·고변동성."""
    ev = np.asarray(obs.R.index.isin(obs.dates))
    out = {}
    for tk in obs.tickers:
        r = obs.R[tk].to_numpy(float)
        cols = {}
        for q in (1, 3, 7, 14, 20, 30, 60, 120):
            v = realized_variance(r, q)
            uv, _, _ = midrank_past(v, 252)
            cols[f"HIGH_q{q}"] = uv[ev] >= 0.9
            cols[f"UV_q{q}"] = uv[ev]
            if q > 1:
                d, _, _ = log_variance_ratio(v, q)
                ud, _, _ = midrank_past(d, 252)
                cols[f"EXP_q{q}"] = ud[ev] >= 0.9
                cols[f"UD_q{q}"] = ud[ev]
        out[tk] = pd.DataFrame(cols, index=obs.dates)
    return out


def cusum_alarm_flags(obs: Obs, threshold: str = "w3") -> dict[tuple[str, str, int], np.ndarray]:
    """개별 CUSUM 일별 경보. threshold="w3": W3 own-valid 보정 임계값 (주, lock-2 §6) · "w1": W1 동결 임계값 (무결성 대조용)."""
    if threshold == "w3":
        c3 = json.loads((mc_dir(obs.root) / "w3_individual_criticals.json").read_text())
    else:
        pipe = pd.read_csv(
            obs.root / "research/window_study_w1/results/03_synthetic/pipeline/pipeline_thresholds.csv"
        )
        c1 = {
            (p, int(w)): float(c)
            for p, w, c in zip(pipe.policy, pipe.w, pipe.critical_annual_max, strict=True)
        }
    flags = {}
    for i, tk in enumerate(obs.tickers):
        for p_i, p in enumerate(POLICIES):
            for w_i, w in enumerate(PRIMARY_W):
                c = c3[f"w3:{tk}:{p}:{w}"] if threshold == "w3" else c1[p, w]
                T = obs.out.T[i, p_i, w_i]
                flags[tk, p, w] = np.isfinite(T) & (T >= c)
    return flags


def energy_candidates(obs: Obs) -> np.ndarray:
    """E(h) 의 보정 꼬리 u ≤ 0.01 후보 (ETF, 정책, h, 일) — 탐색 후보, 보정된 경보 아님."""
    E = energy(obs.out.e, obs.out.year_of_day, [1, 3, 7, 14])
    z = np.load(mc_dir(obs.root) / "energy_table.npz")
    from .scores import tail_u

    u = tail_u(E, TailTable(z["table"], z["n_pool"], z["edges"]), obs.out.pos_in_year)
    return np.isfinite(u) & (u <= 0.01)


def sequential_alarm_episodes(
    obs: Obs, qs: dict[str, pd.DataFrame], flags: dict, ecand: np.ndarray, lookback: int = 60
) -> pd.DataFrame:
    """CUSUM 경보 에피소드마다 직전 60일 안의 가장 가까운 단기 후보 연속구간 시작 → 경보까지 관측 지연."""
    rows = []
    dates = obs.dates
    for (tk, p, w), f in flags.items():
        i = obs.tickers.index(tk)
        for a, b in run_lengths(f):
            lo = max(0, a - lookback)
            rec = {
                "ticker": tk,
                "policy": p,
                "w": w,
                "alarm_start": dates[a].date(),
                "alarm_end": dates[b].date(),
                "alarm_days": b - a + 1,
            }
            for q in (3, 7, 14):
                s = qs[tk][f"EXP_q{q}"].to_numpy()
                runs = [rr for rr in run_lengths(s[: a + 1]) if rr[1] >= lo]
                rec[f"lag_from_q{q}_EXP"] = a - runs[-1][0] if runs else np.nan
            for h_i, h in enumerate((1, 3, 7, 14)):
                s = ecand[i, POLICIES.index(p), h_i]
                runs = [rr for rr in run_lengths(s[: a + 1]) if rr[1] >= lo]
                rec[f"lag_from_E{h}"] = a - runs[-1][0] if runs else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def case_sequence(obs: Obs, qs: dict[str, pd.DataFrame], flags: dict, start: str, end: str) -> pd.DataFrame:
    """사례 창 [start, end] 에서 ETF 별 첫 단기 후보(q=1·3·7·14)·첫 CUSUM 경보(w, 정책 A·B·base 중 최초)·신호 소멸일."""
    dates = obs.dates
    m = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    idx = np.flatnonzero(m)
    rows = []

    def first(flag: np.ndarray) -> str:
        k = np.flatnonzero(flag[idx])
        return str(dates[idx[k[0]]].date()) if k.size else "NONE"

    def last(flag: np.ndarray) -> str:
        k = np.flatnonzero(flag[idx])
        return str(dates[idx[k[-1]]].date()) if k.size else "NONE"

    for tk in obs.tickers:
        rec = {
            "ticker": tk,
            "window": f"{start}~{end}",
            "first_daily_shock_q1": first(qs[tk]["HIGH_q1"].to_numpy()),
        }
        for q in (3, 7, 14):
            rec[f"first_EXP_q{q}"] = first(qs[tk][f"EXP_q{q}"].to_numpy())
        for q in (20, 60, 120):
            rec[f"first_HIGH_q{q}"] = first(qs[tk][f"HIGH_q{q}"].to_numpy())
        for w in PRIMARY_W:
            anyp = np.logical_or.reduce([flags[tk, p, w] for p in POLICIES])
            rec[f"first_CUSUM_w{w}"] = first(anyp)
            rec[f"last_CUSUM_w{w}"] = last(anyp)
            rec[f"first_valid_CUSUM_w{w}"] = first(
                np.isfinite(obs.out.T[obs.tickers.index(tk), 0, PRIMARY_W.index(w)])
            )
        rows.append(rec)
    return pd.DataFrame(rows)


# ── 가격 반응 (탐색, EXPLORATORY_REUSED_DATA) ──────────────────────


def price_response(
    obs: Obs, ep: pd.DataFrame, qs: dict[str, pd.DataFrame], seed: int
) -> dict[str, pd.DataFrame]:
    """공동 신호 이용 가능일 종가 다음 날부터 H 일 누적 로그수익률(%) · 나머지 5종 대비 · 최대 상승/하락 · 반전 여부.

    비교: 단독 반응 (한 ETF 만 Q ≥ c0, 어떤 쌍도 J_all ≥ c0 아님) · 2종 이상 (J_2(S5) ≥ c0 구간) · H0-B 유의 구간
    · 같은 ETF·연도·사전 U_V(q=20) 십분위 대조일 (±20일 안 후보 없음). 추론은 20일 날짜 블록 bootstrap.
    """
    cfg = obs.cfg
    c0 = float(cfg["episodes"]["episode_level_threshold_c0"])
    H = cfg["price"]["horizons"]
    r = obs.R.loc[obs.dates]
    rv = r.to_numpy()
    n = len(obs.dates)
    rng = np.random.default_rng(seed)

    def fwd(i_etf: int, t: int, h: int) -> tuple[float, float, float, float]:
        if t + h >= n:
            return (np.nan,) * 4
        seg = rv[t + 1 : t + 1 + h, i_etf]
        oth = np.delete(rv[t + 1 : t + 1 + h], i_etf, axis=1).mean(axis=1)
        path = np.cumsum(seg)
        return float(seg.sum()), float((seg - oth).sum()), float(path.max()), float(path.min())

    pos = {d.date(): k for k, d in enumerate(obs.dates)}
    events = []
    # 2종 이상·H0-B 유의: 구간 표의 집합 구간에서 (구성원 ETF 별)
    sig_any = ep[ep.day_level_status.eq("SIGNIFICANT_H0B")]
    multi = ep[ep.size.ge(2)]
    for kind, frame in (("two_or_more_etf", multi), ("h0b_significant", sig_any)):
        for _, e in frame.iterrows():
            t = pos[pd.Timestamp(e.joint_confirmed_at).date()]
            for tk in e.subset.split("+"):
                events.append((kind, tk, t, e.subset))
    # 단독 반응: 한 ETF 만 max Q ≥ c0 이고 그날 어떤 쌍의 J_all 도 c0 미만
    qmax = np.where(np.isfinite(obs.Q), obs.Q, -np.inf).max(axis=(1, 2))  # (ETF, 일)
    pair_hit = np.zeros(n, bool)
    for s in [s for s in obs.subsets if len(s) == 2]:
        ja = j_all(member_stack(obs.Q, obs.Qlag, s, obs.tickers))
        pair_hit |= np.where(np.isfinite(ja), ja, -np.inf).max(axis=(0, 1)) >= c0
    single = (qmax >= c0).sum(axis=0) == 1
    for i, tk in enumerate(obs.tickers):
        f = single & (qmax[i] >= c0) & ~pair_hit
        for a, _ in run_lengths(f):
            events.append(("single_etf_only", tk, a, tk))
    # 대조일: 같은 ETF·연도, 그날 사전 U_V(q=20) 십분위가 같고 ±20일 안에 어떤 후보도 없는 날 중 가장 가까운 날
    cand = (qmax >= c0).any(axis=0) | pair_hit
    near = np.convolve(cand.astype(int), np.ones(41, int), mode="same") > 0
    rows = []
    for kind, tk, t, label in events:
        i = obs.tickers.index(tk)
        for h in H:
            R_, rel, mx, mn = fwd(i, t, h)
            pre = float(rv[max(0, t - 19) : t + 1, i].sum())
            rows.append(
                {
                    "group": kind,
                    "ticker": tk,
                    "event": label,
                    "t_index": t,
                    "date": obs.dates[t].date(),
                    "h": h,
                    "ret": R_,
                    "rel_vs_other5": rel,
                    "max_up": mx,
                    "max_down": mn,
                    "pre20": pre,
                    "reversal": float(np.sign(pre) != np.sign(R_)) if np.isfinite(R_) else np.nan,
                }
            )
        uv = qs[tk]["UV_q20"].to_numpy()
        dec = np.floor(np.clip(uv[t], 0, 0.9999) * 10) if np.isfinite(uv[t]) else np.nan
        yr = obs.dates.year == obs.dates[t].year
        ok = yr & ~near & np.isfinite(uv) & (np.floor(np.clip(uv, 0, 0.9999) * 10) == dec)
        cands = np.flatnonzero(ok)
        if cands.size and np.isfinite(dec):
            c = int(cands[np.argmin(np.abs(cands - t))])
            for h in H:
                R_, rel, mx, mn = fwd(i, c, h)
                rows.append(
                    {
                        "group": f"control_for_{kind}",
                        "ticker": tk,
                        "event": label,
                        "t_index": c,
                        "date": obs.dates[c].date(),
                        "h": h,
                        "ret": R_,
                        "rel_vs_other5": rel,
                        "max_up": mx,
                        "max_down": mn,
                        "pre20": float(rv[max(0, c - 19) : c + 1, i].sum()),
                        "reversal": np.nan,
                    }
                )
    ev = pd.DataFrame(rows)
    # 날짜 블록 bootstrap (20일 블록) — 그룹·지평별 중앙값의 95% 구간
    summ = []
    for (g, h), grp in ev.groupby(["group", "h"], sort=True):
        x = grp.dropna(subset=["ret"])
        if x.empty:
            continue
        blocks = (x.t_index // 20).to_numpy()
        ub = np.unique(blocks)
        meds = []
        for _ in range(2000):
            pick = rng.choice(ub, ub.size, replace=True)
            sel = np.concatenate([np.flatnonzero(blocks == bb) for bb in pick])
            meds.append(np.median(x.ret.to_numpy()[sel]))
        summ.append(
            {
                "group": g,
                "h": h,
                "n_events": len(x),
                "n_date_blocks": int(ub.size),
                "median_ret": float(x.ret.median()),
                "ci95_low": float(np.quantile(meds, 0.025)),
                "ci95_high": float(np.quantile(meds, 0.975)),
                "median_rel_vs_other5": float(x.rel_vs_other5.median()),
                "share_up": float((x.ret > 0).mean()),
                "median_max_up": float(x.max_up.median()),
                "median_max_down": float(x.max_down.median()),
                "reversal_share": float(x.reversal.mean()) if x.reversal.notna().any() else np.nan,
                "label": cfg["price"]["label"],
            }
        )
    return {"events": ev, "summary": pd.DataFrame(summ)}


def confirmatory_power_requirement(
    summary: pd.DataFrame, events: pd.DataFrame, alpha: float = 0.01, power: float = 0.8
) -> pd.DataFrame:
    """미래 독립 확증 검정 설계용: 관측 중앙 차이를 효과크기로 둘 때 필요한 사건 수 (정규 근사, 양측 α=0.01)."""
    from scipy import stats

    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    rows = []
    for h in sorted(events.h.unique()):
        for g in ("two_or_more_etf", "h0b_significant"):
            a = events[(events.group == g) & (events.h == h)].ret.dropna()
            c = events[(events.group == f"control_for_{g}") & (events.h == h)].ret.dropna()
            if len(a) < 5 or len(c) < 5:
                continue
            delta = float(a.mean() - c.mean())
            sd = float(np.sqrt((a.var() + c.var()) / 2))
            n_req = float(np.ceil(2 * (z * sd / delta) ** 2)) if delta != 0 else np.inf
            rows.append(
                {
                    "group": g,
                    "h": h,
                    "observed_mean_diff": delta,
                    "pooled_sd": sd,
                    "n_per_group_required_alpha_0.01_power_0.8": n_req,
                    "note": "효과크기는 탐색 자료에서 추정 — 낙관적일 수 있다",
                }
            )
    return pd.DataFrame(rows)


def pair_correlation_shift(obs: Obs, ep: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """H5 보조 진단: 공동 구간 전후 60일 수익률 상관 변화 (탐색, 보정 없음)."""
    r = obs.R.loc[obs.dates].to_numpy()
    pos = {d.date(): k for k, d in enumerate(obs.dates)}
    rows = []
    for _, e in ep[ep.size.ge(2)].iterrows():
        a, b = pos[e.episode_start_at], pos[e.episode_end_at]
        if a < window or b + window >= len(obs.dates):
            continue
        for x, y in combinations(e.subset.split("+"), 2):
            i, j = obs.tickers.index(x), obs.tickers.index(y)
            pre = np.corrcoef(r[a - window : a, i], r[a - window : a, j])[0, 1]
            post = np.corrcoef(r[b + 1 : b + 1 + window, i], r[b + 1 : b + 1 + window, j])[0, 1]
            rows.append(
                {
                    "subset": e.subset,
                    "episode_start_at": e.episode_start_at,
                    "pair": f"{x}+{y}",
                    "corr_pre60": pre,
                    "corr_post60": post,
                    "delta": post - pre,
                }
            )
    return pd.DataFrame(rows)


def participation_table(obs: Obs) -> pd.DataFrame:
    """그림 08-3(나)·표: 단계 S_k (k=2..5) 의 E_{k−1} 에서 각 ETF 의 평균 시차 Q (|E|≥5 칸의 정책·창 최대). 기술 통계."""
    cfg = obs.cfg
    jc = cfg["joint"]["primary_test_statistics"]
    rows = []
    for k in range(1, 5):
        prev = tuple(cfg["universe"]["stages"][STAGES[k - 1]])
        for tk in obs.tickers:
            r = stage_conditional(obs.Q, obs.Qlag, prev, tk, obs.tickers, float(jc["c_E"]), int(jc["min_E"]))
            rows.append(
                {
                    "stage": STAGES[k],
                    "ticker": tk,
                    "role": "신규"
                    if tk == cfg["universe"]["stage_new_ticker"][STAGES[k]]
                    else ("기존" if tk in prev else "미편입(참고)"),
                    "mean_Qlag_on_E": r.stat,
                    "max_cell_n": int(np.nanmax(r.cell_n)) if r.cell_n.size else 0,
                }
            )
    return pd.DataFrame(rows)
