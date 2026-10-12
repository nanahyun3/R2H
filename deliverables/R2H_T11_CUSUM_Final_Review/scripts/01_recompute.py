"""T11 최종 재평가 — 커밋된 결과표를 캐시 잔차(`outputs/cache/t11_state.npz`)에서 독립 재계산해 대조한다.

사건 기반 평가(P1·P4·C3·공통충격)는 쓰지 않는다. 새 실험이 아니라 재계산이며, 확장 실험은 ``02_extension.py``.
출력: ``analysis/*.csv`` 와 ``analysis/recompute_claims.json`` (보고서 숫자의 단일 출처 일부).

실행 (R2H 루트에서): ``PYTHONPATH=src python deliverables/R2H_T11_CUSUM_Final_Review/scripts/01_recompute.py``
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.paper2020 import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.svrgarch_etf.rolling import (
    ASYMPTOTIC_5PCT,
    SEED,
    WINDOWS,
    bootstrap_critical_value,
    episodes,
    iid_stats,
    null_alarm_episodes_per_year,
    rolling_cusum,
    yearly_blocks,
)

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
RES = REPO / "research" / "svr_garch_cusum_etf" / "results"
OUT = HERE / "analysis"
OUT.mkdir(parents=True, exist_ok=True)
RTYPES = ("svrA", "base")  # 파이프라인 _salt 와 같은 순서
GAP = 5


def kolmogorov_cdf(x: float, terms: int = 200) -> float:
    """sup_{0≤s≤1} |B°(s)| 의 분포함수 (Kolmogorov). 1 − 2 Σ (−1)^{k−1} exp(−2k²x²)."""
    k = np.arange(1, terms + 1)
    return float(1 - 2 * np.sum((-1.0) ** (k - 1) * np.exp(-2 * k**2 * x**2)))


def kolmogorov_quantile(q: float) -> float:
    lo, hi = 0.3, 3.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if kolmogorov_cdf(mid) < q else (lo, mid)
    return (lo + hi) / 2


def main() -> None:
    z = np.load(os.environ.get("T11_STATE", REPO / "outputs" / "cache" / "t11_state.npz"), allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    tickers = [str(t) for t in z["tickers"]]
    ref = pd.read_csv(REPO / "research" / "svr_garch_cusum_etf" / "reference_close_sha256.csv", dtype=str)
    names = dict(zip(ref.ticker, ref.name, strict=True))
    cats = dict(zip(ref.ticker, ref.category, strict=True))
    fit = pd.read_csv(RES / "fit_summary.csv", dtype={"ticker": str})
    full = pd.read_csv(RES / "fullsample_tests.csv", dtype={"ticker": str})
    crit = pd.read_csv(RES / "critical_values.csv", dtype={"ticker": str})
    nul = pd.read_csv(RES / "null_alarm_rate.csv", dtype={"ticker": str})
    yb = pd.read_csv(RES / "yearly_blocks.csv", dtype={"ticker": str})
    roll_csv = pd.read_csv(RES / "rolling_stats.csv.gz", index_col=0, parse_dates=True)
    manifest = json.loads((RES / "run_manifest.json").read_text())
    split = {t: pd.Timestamp(d) for t, d in zip(fit.ticker, fit.split_date, strict=True)}
    n = len(idx)
    claims: dict[str, dict] = {}

    def claim(key: str, value, source: str, status: str = "VERIFIED", note: str = "") -> None:
        claims[key] = {"value": value, "source": source, "status": status, "note": note}

    # ── 1. 임계값의 출처: 원문 표기 1.3397 vs Kolmogorov 이론값
    k95 = kolmogorov_quantile(0.95)
    p_at_paper = kolmogorov_cdf(ASYMPTOTIC_5PCT)
    claim("kolmogorov_q95", round(k95, 4), "01_recompute.kolmogorov_quantile (해석적 급수)")
    claim("paper_cv", ASYMPTOTIC_5PCT, "src/r2h/paper2020/cusum.py PAPER_CRITICAL_VALUE_5_PERCENT", "REPORTED")
    claim(
        "paper_cv_implied_level",
        round(1 - p_at_paper, 4),
        "01_recompute.kolmogorov_cdf(1.3397)",
        note="1.3397 을 Kolmogorov 분포로 읽으면 이 상측 확률 — 원문 값의 유도 근거는 확인하지 못함",
    )

    # ── 2. 사후 검정 재계산 (검정 구간 = 분할일 이후, NaN 제외)
    rng = np.random.default_rng([SEED, 571, 9])
    c_normal_571 = float(np.quantile(iid_stats(rng.standard_normal((20_000, 571))), 0.95))
    claim("c_normal_n571", round(c_normal_571, 4), "01_recompute: iid N(0,1) MC 20,000회, n=571, seed [20261012,571,9]")
    rows = []
    for t in tickers:
        test_mask = np.asarray(idx >= split[t])
        for pol, key in (("A", "svrA"), ("B", "svrB"), ("base", "base")):
            e_all = z[f"res__{t}__{key}"]
            e = e_all[test_mask]
            keep = np.isfinite(e)
            res = cusum_squares_test(
                e[keep], tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
            )
            kdate = idx[test_mask][keep][res.change_index_one_based - 1].date()
            # 적합 구간 잔차 iid 재표집으로 만든 n_test 길이 95% 임계값 (정책 B 의 적합 구간 잔차 = 정책 A)
            pool_key = "base" if pol == "base" else "svrA"
            fit_part = z[f"res__{t}__{pool_key}"][~test_mask]
            c_boot_n = bootstrap_critical_value(fit_part, int(keep.sum()), salt=int(t) * 10 + 3)
            old = full[(full.ticker == t) & (full.policy == pol)].iloc[0]
            rows.append(
                {
                    "ticker": t,
                    "name": names[t],
                    "category": cats[t],
                    "policy": pol,
                    "n_test": int(keep.sum()),
                    "T": res.statistic,
                    "T_committed": float(old["T"]),
                    "abs_diff": abs(res.statistic - float(old["T"])),
                    "khat": str(kdate),
                    "khat_committed": str(old["khat_date"]),
                    "reject_1.3397": res.statistic >= ASYMPTOTIC_5PCT,
                    "reject_committed": bool(old["reject"]),
                    "reject_kolmogorov": res.statistic >= k95,
                    "c_normal_n571": c_normal_571,
                    "reject_normal_n571": res.statistic >= c_normal_571,
                    "c_boot_n": c_boot_n,
                    "reject_boot_n": res.statistic >= c_boot_n,
                }
            )
    fs = pd.DataFrame(rows)
    fs.to_csv(OUT / "fullsample_recomputed.csv", index=False)
    claim("fs_max_abs_diff", float(fs.abs_diff.max()), "analysis/fullsample_recomputed.csv abs_diff (vs results/fullsample_tests.csv T)")
    claim("fs_khat_match", int((fs.khat == fs.khat_committed).sum()), "fullsample_recomputed.csv khat == khat_committed", note="60행 중")
    claim("fs_reject_match", int((fs["reject_1.3397"] == fs.reject_committed).sum()), "fullsample_recomputed.csv", note="60행 중")
    for pol in ("A", "B", "base"):
        s = fs[fs.policy == pol]
        claim(f"fs_reject_{pol}", int(s["reject_1.3397"].sum()), "fullsample_recomputed.csv reject_1.3397")
        claim(f"fs_reject_{pol}_kolm", int(s["reject_kolmogorov"].sum()), "fullsample_recomputed.csv reject_kolmogorov")
        claim(f"fs_reject_{pol}_normal", int(s["reject_normal_n571"].sum()), "fullsample_recomputed.csv reject_normal_n571")
        claim(f"fs_reject_{pol}_boot", int(s["reject_boot_n"].sum()), "fullsample_recomputed.csv reject_boot_n",
              status="VERIFIED", note="EXTENSION 성격의 재판정 — ETF 별 iid 부트스트랩 임계값 (n_test 길이)")
        claim(f"fs_rejected_{pol}", ", ".join(s[s["reject_1.3397"]].ticker), "fullsample_recomputed.csv")
        claim(f"fs_T_median_{pol}", round(float(s["T"].median()), 3), "fullsample_recomputed.csv T 중앙값")

    # ── 3. 정책 A/B 대응
    a = fs[fs.policy == "A"].set_index("ticker")
    b = fs[fs.policy == "B"].set_index("ticker")
    pair = pd.DataFrame(
        {
            "name": a.name,
            "T_A": a["T"],
            "T_B": b["T"],
            "dT": b["T"] - a["T"],
            "rej_A": a["reject_1.3397"],
            "rej_B": b["reject_1.3397"],
            "khat_A": a.khat,
            "khat_B": b.khat,
        }
    )
    pair["khat_gap_days"] = [
        abs(int(idx.searchsorted(pd.Timestamp(x))) - int(idx.searchsorted(pd.Timestamp(y))))
        for x, y in zip(pair.khat_A, pair.khat_B, strict=True)
    ]
    # 분산 경로 비교: 검정 구간에서 B/A 분산 비의 평균과 변동계수 (B 가 상수 쪽으로 평활되는지)
    vr, cvA, cvB = [], [], []
    for t in pair.index:
        m = np.asarray(idx >= split[t])
        va, vb = z[f"varA__{t}"][m], z[f"varB__{t}"][m]
        ok = np.isfinite(va) & np.isfinite(vb)
        vr.append(float(np.median(vb[ok] / va[ok])))
        cvA.append(float(np.std(va[ok]) / np.mean(va[ok])))
        cvB.append(float(np.std(vb[ok]) / np.mean(vb[ok])))
    pair["var_ratio_B_over_A_median"] = vr
    pair["cv_var_A"] = cvA
    pair["cv_var_B"] = cvB
    pair.to_csv(OUT / "policy_pairs.csv")
    claim("ab_T_B_gt_A", int((pair.T_B > pair.T_A).sum()), "policy_pairs.csv T_B > T_A", note="20종 중")
    claim("ab_disagree", int((pair.rej_A != pair.rej_B).sum()), "policy_pairs.csv rej_A != rej_B")
    claim("ab_both_reject", int((pair.rej_A & pair.rej_B).sum()), "policy_pairs.csv")
    claim("ab_khat_same", int((pair.khat_gap_days == 0).sum()), "policy_pairs.csv khat_gap_days == 0")
    claim("ab_cvB_lt_cvA", int((pair.cv_var_B < pair.cv_var_A).sum()), "policy_pairs.csv cv_var_B < cv_var_A",
          status="VERIFIED", note="검정 구간 σ̂² 변동계수 — B 가 덜 변동하는 ETF 수")
    claim("ab_cv_A_median", round(float(np.median(cvA)), 3), "policy_pairs.csv cv_var_A 중앙값")
    claim("ab_cv_B_median", round(float(np.median(cvB)), 3), "policy_pairs.csv cv_var_B 중앙값")

    # ── 4. 동일 기초지수 (KOSPI200) 그룹
    grp = ["069500", "102110", "122630", "114800"]
    g_rows = []
    for t in grp:
        m = np.asarray(idx >= split[t])
        f = fit.set_index("ticker").loc[t]
        g_rows.append(
            {
                "ticker": t,
                "name": names[t],
                "C": f.C,
                "gamma2": f.paper_gamma_squared,
                "epsilon": f.epsilon,
                "val_mae": f.val_mae,
                "T_A": a.loc[t, "T"],
                "T_B": b.loc[t, "T"],
                "T_base": fs[(fs.ticker == t) & (fs.policy == "base")]["T"].iloc[0],
                "khat_A": a.loc[t, "khat"],
                "corr_r_vs_069500_test": float(np.corrcoef(z[f"r__{t}"][m], z["r__069500"][m])[0, 1]),
                "corr_eA_vs_069500_test": float(
                    pd.Series(z[f"res__{t}__svrA"][m]).corr(pd.Series(z["res__069500__svrA"][m]))
                ),
                "median_varA_ratio_vs_069500_scaled": float(
                    np.nanmedian(
                        (z[f"varA__{t}"][m] / np.nanvar(z[f"r__{t}"][m]))
                        / (z["varA__069500"][m] / np.nanvar(z["r__069500"][m]))
                    )
                ),
            }
        )
    gdf = pd.DataFrame(g_rows)
    gdf.to_csv(OUT / "kospi200_group.csv", index=False)
    m0 = np.asarray(idx >= split["069500"])
    claim("k200_corr_r", round(float(gdf.set_index("ticker").loc["102110", "corr_r_vs_069500_test"]), 4), "kospi200_group.csv")
    claim("k200_corr_eA", round(float(gdf.set_index("ticker").loc["102110", "corr_eA_vs_069500_test"]), 4), "kospi200_group.csv")
    claim("k200_TA_069500", round(float(a.loc["069500", "T"]), 3), "fullsample_recomputed.csv")
    claim("k200_TA_102110", round(float(a.loc["102110", "T"]), 3), "fullsample_recomputed.csv")
    claim("k200_TB_069500", round(float(b.loc["069500", "T"]), 3), "fullsample_recomputed.csv")
    claim("k200_TB_102110", round(float(b.loc["102110", "T"]), 3), "fullsample_recomputed.csv")
    claim("k200_params_069500", "C=1, γ²=0.5, ε=0.1", "results/fit_summary.csv", "REPORTED")
    claim("k200_params_102110", "C=100, γ²=1, ε=0.1", "results/fit_summary.csv", "REPORTED")
    # 069500 과 102110 의 이동창(w=60) 통계량 상관 (전 구간)
    s1 = rolling_cusum(z["res__069500__svrA"], 60)
    s2 = rolling_cusum(z["res__102110__svrA"], 60)
    ok = np.isfinite(s1) & np.isfinite(s2)
    claim("k200_roll60_corr", round(float(np.corrcoef(s1[ok], s2[ok])[0, 1]), 3), "rolling_cusum(res svrA, 60) 069500 vs 102110")
    # 잔차 차이의 원천: 같은 수익률을 서로 다른 ĝ 로 나눈 것 — 검정 구간 σ̂_A 비의 분포
    ratio = np.sqrt(z["varA__069500"][m0] / z["varA__102110"][m0])
    claim("k200_sigma_ratio_p05", round(float(np.nanpercentile(ratio, 5)), 3), "sqrt(varA 069500 / varA 102110) 검정 구간 5% 분위")
    claim("k200_sigma_ratio_p95", round(float(np.nanpercentile(ratio, 95)), 3), "같은 비의 95% 분위")
    sel = fit[["ticker", "C", "paper_gamma_squared", "epsilon"]]
    claim("grid_eps_floor", int((sel.epsilon == 0.1).sum()), "results/fit_summary.csv epsilon == 0.1 (grid 하한)", "VERIFIED", note="20종 중")
    claim("grid_C_counts", sel.C.value_counts().sort_index().to_dict(), "results/fit_summary.csv C 분포", "VERIFIED")

    # ── 5. 임계값 재계산 (동일 seed·salt → 바이트 수준 일치 기대)
    c_rows = []
    for t in tickers:
        fit_mask = np.asarray(idx < split[t])
        for rt in RTYPES:
            fit_part = z[f"res__{t}__{rt}"][fit_mask]
            for w in WINDOWS:
                c = bootstrap_critical_value(fit_part, w, salt=int(t) * 10 + RTYPES.index(rt))
                old = crit[(crit.ticker == t) & (crit.rtype == rt) & (crit.window == w)].iloc[0]
                c_rows.append({"ticker": t, "rtype": rt, "window": w, "c": c, "c_committed": float(old.c_bootstrap)})
    cdf = pd.DataFrame(c_rows)
    cdf["abs_diff"] = (cdf.c - cdf.c_committed).abs()
    cdf.to_csv(OUT / "critical_recomputed.csv", index=False)
    claim("crit_max_abs_diff", float(cdf.abs_diff.max()), "critical_recomputed.csv", note="CSV 반올림 6자리 대비")
    cn = crit.groupby("window").c_normal.first()
    for w in WINDOWS:
        sub = crit[(crit.window == w) & (crit.rtype == "svrA")]
        claim(f"crit_boot_A_w{w}_range", f"{sub.c_bootstrap.min():.2f}–{sub.c_bootstrap.max():.2f}", "results/critical_values.csv svrA", "VERIFIED")
        claim(f"crit_normal_w{w}", round(float(cn[w]), 3), "results/critical_values.csv c_normal", "VERIFIED")

    # ── 6. 이동창 통계량 재계산 + 구간별 경보 빈도 (분모 분리)
    roll_diff, ep_rows = 0.0, []
    for t in tickers:
        sp = int(idx.searchsorted(split[t]))
        for rt in RTYPES:
            for w in WINDOWS:
                stat = rolling_cusum(z[f"res__{t}__{rt}"], w)
                col = f"{t}|{rt}|{w}"
                diff = np.nanmax(np.abs(stat - roll_csv[col].to_numpy())) if np.isfinite(stat).any() else 0.0
                roll_diff = max(roll_diff, float(diff))
                c = float(crit[(crit.ticker == t) & (crit.rtype == rt) & (crit.window == w)].c_bootstrap.iloc[0])
                eps = episodes(np.nan_to_num(stat, nan=-np.inf) >= c, gap=GAP)
                starts = np.array([s for s, _ in eps], dtype=int)
                t0 = sp + w - 1  # 창 전체가 검정 구간 안
                first_valid = int(np.flatnonzero(np.isfinite(stat))[0]) if np.isfinite(stat).any() else sp
                n_fit_days = sp - first_valid
                n_test_days = n - t0
                ep_rows.append(
                    {
                        "ticker": t,
                        "rtype": rt,
                        "window": w,
                        "c_boot": c,
                        "episodes_all": len(eps),
                        "rate_all_per_yr": len(eps) / (n / 252),
                        "episodes_fit": int((starts < sp).sum()),
                        "rate_fit_per_yr": (starts < sp).sum() / (n_fit_days / 252),
                        "episodes_boundary": int(((starts >= sp) & (starts < t0)).sum()),
                        "episodes_test": int((starts >= t0).sum()),
                        "rate_test_per_yr": (starts >= t0).sum() / (n_test_days / 252),
                        "n_fit_days_valid": n_fit_days,
                        "n_test_days": n_test_days,
                    }
                )
    er = pd.DataFrame(ep_rows)
    er = er.merge(nul[["ticker", "rtype", "window", "null_episodes_per_year", "observed_episodes_per_year"]],
                  on=["ticker", "rtype", "window"])
    er["obs_all_diff"] = (er.rate_all_per_yr - er.observed_episodes_per_year).abs()
    claim("roll_max_abs_diff", roll_diff, "rolling_cusum(npz 잔차) vs results/rolling_stats.csv.gz", note="CSV 반올림 대비")
    claim("obs_rate_max_diff", float(er.obs_all_diff.max()), "zone_rates.csv rate_all vs null_alarm_rate.observed")
    claim("rate_denominator", f"전 기간 {n} 거래일 / 252 = {n / 252:.3f}년", "pipeline.py obs_rate = size / (len(idx)/252)", "VERIFIED")

    # 귀무 기대 경보율 재계산 (같은 seed·salt·sims=100)
    nr = []
    for t in tickers:
        fit_mask = np.asarray(idx < split[t])
        for rt in RTYPES:
            for w in WINDOWS:
                c = float(crit[(crit.ticker == t) & (crit.rtype == rt) & (crit.window == w)].c_bootstrap.iloc[0])
                v = null_alarm_episodes_per_year(z[f"res__{t}__{rt}"][fit_mask], w, c, n, sims=100,
                                                 salt=int(t) * 10 + RTYPES.index(rt), gap=GAP)
                nr.append(v)
    er["null_recomputed"] = nr
    er["null_diff"] = (er.null_recomputed - er.null_episodes_per_year).abs()
    er.to_csv(OUT / "zone_rates.csv", index=False)
    claim("null_max_diff", float(er.null_diff.max()), "zone_rates.csv null_recomputed vs committed")
    for rt in RTYPES:
        for w in WINDOWS:
            s = er[(er.rtype == rt) & (er.window == w)]
            p = f"rate_{rt}_w{w}"
            claim(f"{p}_all", round(float(s.rate_all_per_yr.mean()), 2), "zone_rates.csv 20종 평균 (전 기간 분모)")
            claim(f"{p}_fit", round(float(s.rate_fit_per_yr.mean()), 2), "zone_rates.csv 20종 평균 (적합 구간, in-sample)")
            claim(f"{p}_test", round(float(s.rate_test_per_yr.mean()), 2), "zone_rates.csv 20종 평균 (순수 검정 구간)")
            claim(f"{p}_null", round(float(s.null_episodes_per_year.mean()), 2), "results/null_alarm_rate.csv 20종 평균 (iid 재표집)")
            claim(f"{p}_test_gt_null", int((s.rate_test_per_yr > s.null_episodes_per_year).sum()), "zone_rates.csv")
            claim(f"{p}_test_zero", int((s.episodes_test == 0).sum()), "zone_rates.csv episodes_test == 0")
            claim(f"{p}_all_gt_null", int((s.rate_all_per_yr > s.null_episodes_per_year).sum()), "zone_rates.csv")

    # ── 7. 연도 블록 재계산
    yr = []
    for t in tickers:
        for rt in RTYPES:
            d = yearly_blocks(idx, z[f"res__{t}__{rt}"])
            d["ticker"], d["rtype"] = t, rt
            yr.append(d)
    ydf = pd.concat(yr)
    mm = ydf.merge(yb, on=["ticker", "rtype", "year"], suffixes=("", "_c"))
    claim("yearly_max_abs_diff", float(np.nanmax(np.abs(mm["T"] - mm["T_c"]))), "yearly_blocks() vs results/yearly_blocks.csv")
    yrr = yb.assign(rej=yb["T"] >= ASYMPTOTIC_5PCT).groupby(["rtype", "year"]).rej.mean().unstack(0)
    yrr.to_csv(OUT / "yearly_reject_share.csv")
    for rt in RTYPES:
        for y in yrr.index:
            claim(f"yearly_{rt}_{y}", round(float(yrr.loc[y, rt]) * 100), "analysis/yearly_reject_share.csv (%, 1.3397)")

    # ── 8. Track B 원문 대비 (캐시 사본, SA_ETF 031157d)
    cache = REPO / "outputs" / "cache"
    emp = pd.read_csv(cache / "031157d__research__track_b_paper2020__reports__EMPIRICAL_ORIGINAL_VS_REPRODUCED.csv")
    emp.to_csv(OUT / "trackb_empirical.csv", index=False)
    ovr = pd.read_csv(cache / "031157d__research__track_b_paper2020__reports__ORIGINAL_VS_REPRODUCED.csv")
    n500 = ovr[ovr.n == 500]
    tb = {}
    for pol in ("clip", "raise", "recursive"):
        done = n500[n500[f"{pol}_status"] != "NOT_RUN"]
        tb[pol] = f"{int(done[f'{pol}_paper_in_ci'].astype(bool).sum())}/{len(done)}"
    ovr_small = n500[["table", "case_id", "label", "kind", "paper", "clip_rate_cond_ok", "clip_reps",
                      "raise_rate_cond_ok", "raise_reps", "recursive_rate_cond_ok", "recursive_reps"]]
    ovr_small.to_csv(OUT / "trackb_mc_n500.csv", index=False)
    claim("trackb_in_ci", tb, "outputs/cache/031157d…ORIGINAL_VS_REPRODUCED.csv n=500 *_paper_in_ci", "REPORTED",
          note="원 감사 패키지의 Wilson 95% CI 판정을 그대로 집계 (반복은 재실행하지 않음)")
    claim("trackb_size_n500", {k: (None if pd.isna(v) else float(v)) for k, v in n500[n500.case_id == "t1_size"].iloc[0][
        ["paper", "clip_rate_cond_ok", "raise_rate_cond_ok", "recursive_rate_cond_ok"]].items()},
        "ORIGINAL_VS_REPRODUCED.csv t1_size n=500", "REPORTED")

    # 매니페스트 사실
    claim("data_version", manifest["data_version"], "results/run_manifest.json", "REPORTED")
    claim("n_returns", n, "t11_state.npz dates")
    claim("first_last", f"{idx[0].date()} ~ {idx[-1].date()}", "t11_state.npz dates")
    claim("split_date", str(split["069500"].date()), "results/fit_summary.csv")
    claim("n_test", int(fit.n_test.iloc[0]), "results/fit_summary.csv")
    claim("n_train", int(fit.n_train.iloc[0]), "results/fit_summary.csv")
    claim("n_val", int(fit.n_validation.iloc[0]), "results/fit_summary.csv")

    (OUT / "recompute_claims.json").write_text(json.dumps(claims, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: v["value"] for k, v in claims.items()}, ensure_ascii=False, default=str)[:6000])


if __name__ == "__main__":
    main()
