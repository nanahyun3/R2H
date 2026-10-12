"""보고서 숫자의 단일 출처 ``claims.json`` — 재계산(01)과 EXTENSION(02) 결과를 한 파일로 모은다.

DOCX 생성기(05)와 ``SOURCE_EVIDENCE_MATRIX.md`` 는 숫자를 이 파일에서만 읽는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
EXT = HERE / "extension"


def main() -> None:
    claims = json.loads((HERE / "analysis" / "recompute_claims.json").read_text())

    def add(key: str, value, source: str, status: str = "VERIFIED", note: str = "EXTENSION") -> None:
        if key in claims:
            raise KeyError(key)
        claims[key] = {"value": value, "source": source, "status": status, "note": note}

    e1 = pd.read_csv(EXT / "E1_residual_size.csv")
    for _, r in e1.iterrows():
        add(f"E1_{r.dgp}_n{r.n}_{r.critical.split('_')[0]}", round(100 * r.reject_rate, 1),
            f"extension/E1_residual_size.csv ({r.dgp}, n={r.n}, {r.critical})", note=f"EXTENSION · % · MC SE {100 * r.mc_se:.1f}%p · R={r.R}")
    add("E1_c_normal_n60", round(float(e1[(e1.n == 60) & (e1.critical == "normal_mc95")].c.iloc[0]), 3), "E1_residual_size.csv")

    e2 = pd.read_csv(EXT / "E2_pipeline_size_power_summary.csv")
    e2["scenario"] = e2.scenario.fillna("null")  # pandas 가 문자열 "null" 을 결측으로 읽는다
    for _, r in e2.iterrows():
        m = r.measure.replace("posthoc_reject@paper_1.3397", "rej13397").replace("posthoc_reject@kolmogorov_1.3581", "rej13581")
        pct = not ("per_year" in m or "days" in m)
        val = round(100 * r.value, 1) if pct else round(r.value, 2 if "per_year" in m else 0)
        se = "" if pd.isna(r.mc_se) else f" · MC SE {(100 * r.mc_se if pct else r.mc_se):.{1 if pct else 2}f}"
        add(f"E2_{r.scenario}_{r.residual}_{m}", val, f"extension/E2_pipeline_size_power_summary.csv ({r.scenario}, {r.residual}, {r.measure})",
            note=f"EXTENSION · {'%' if pct else ('연간 에피소드' if 'per_year' in m else '거래일')}{se} · R={r.R}")
    reps = pd.read_csv(EXT / "E2_pipeline_size_power_reps.csv")
    reps["scenario"] = reps.scenario.fillna("null")
    add("E2_R", int((reps.scenario == "null").sum()), "E2_pipeline_size_power_reps.csv")
    add("E2_eps_floor_share", round(100 * float((reps.eps == 0.1).mean()), 1), "E2 reps eps == 0.1", note="EXTENSION · 합성 자료에서도 ε grid 하한 선택 비율 %")

    e3 = pd.read_csv(EXT / "E3_stationary_bootstrap.csv", dtype={"ticker": str})
    add("E3_c571_iid_median", round(float(e3.c571_iid.median()), 2), "E3_stationary_bootstrap.csv")
    add("E3_c571_sb_median", round(float(e3.c571_sb20.median()), 2), "E3_stationary_bootstrap.csv")
    add("E3_c60_iid_median", round(float(e3.c60_iid.median()), 2), "E3_stationary_bootstrap.csv")
    add("E3_c60_sb_median", round(float(e3.c60_sb20.median()), 2), "E3_stationary_bootstrap.csv")
    add("E3_reject_iid", ", ".join(e3[e3.reject_iid].ticker), "E3_stationary_bootstrap.csv reject_iid")
    add("E3_reject_sb", ", ".join(e3[e3.reject_sb20].ticker), "E3_stationary_bootstrap.csv reject_sb20")
    add("E3_reject_both", int((e3.reject_iid & e3.reject_sb20).sum()), "E3_stationary_bootstrap.csv")
    add("E3_rate_iid", round(float(e3.rate_test_w60_iid.mean()), 2), "E3 rate_test_w60_iid 평균")
    add("E3_rate_sb", round(float(e3.rate_test_w60_sb20.mean()), 2), "E3 rate_test_w60_sb20 평균")
    add("E3_c571_sb_153130", round(float(e3.set_index("ticker").loc["153130", "c571_sb20"]), 2), "E3 153130")

    e4 = json.loads((EXT / "E4_time_integrity.json").read_text())
    ident = {k: v for k, v in e4.items() if k.endswith("identical_before_t0")}
    add("E4_identical", f"{sum(ident.values())}/{len(ident)}", "extension/E4_time_integrity.json *_identical_before_t0")
    add("E4_t0", e4["t0_date"], "E4_time_integrity.json")
    add("E4_control", bool(e4["control_fit_perturbed_params_changed"] and e4["control_fit_perturbed_test_resid_changed"]),
        "E4_time_integrity.json control_*")

    e5 = pd.read_csv(EXT / "E5_policyB_rolling_w60.csv", dtype={"ticker": str})
    add("E5_rate_A", round(float(e5.rate_test_svrA.mean()), 2), "E5_policyB_rolling_w60.csv")
    add("E5_rate_B", round(float(e5.rate_test_svrB.mean()), 2), "E5_policyB_rolling_w60.csv")
    add("E5_zero_A", int((e5.episodes_test_svrA == 0).sum()), "E5_policyB_rolling_w60.csv")
    add("E5_zero_B", int((e5.episodes_test_svrB == 0).sum()), "E5_policyB_rolling_w60.csv")

    e6 = pd.read_csv(EXT / "E6_residual_dependence_etf.csv", dtype={"ticker": str})
    for (rt, zone), g in e6.groupby(["rtype", "zone"]):
        add(f"E6_{rt}_{zone}_lrv", round(float(g.lrv_over_tau2.median()), 2), "E6_residual_dependence_etf.csv 중앙값")
        add(f"E6_{rt}_{zone}_lt1", int((g.lrv_over_tau2 < 1).sum()), "E6_residual_dependence_etf.csv lrv < 1 개수")
        add(f"E6_{rt}_{zone}_acf", round(float(g.acf_sq_sum_lag1_5.median()), 2), "E6 acf lag1–5 합 중앙값")
    s6 = pd.read_csv(EXT / "E6_residual_dependence_sim.csv")
    for k in ("A", "B", "base"):
        add(f"E6_sim_{k}_lrv", round(float(s6[f"lrv_{k}_test"].median()), 2), "E6_residual_dependence_sim.csv 중앙값")
        add(f"E6_sim_{k}_lt1", int((s6[f"lrv_{k}_test"] < 1).sum()), "E6_residual_dependence_sim.csv lrv < 1 개수 (100회 중)")

    # 위치 확인용 파생값
    fs = pd.read_csv(HERE / "analysis" / "fullsample_recomputed.csv", dtype={"ticker": str})
    a = fs[fs.policy == "A"]
    add("fs_A_khat_2026_01", int(a.khat.str.startswith("2026-01").sum()), "fullsample_recomputed.csv 정책 A k̂ 2026-01", note="")
    add("fs_B_boot_list", ", ".join(fs[(fs.policy == "B") & fs.reject_boot_n].ticker), "fullsample_recomputed.csv", note="")
    add("fs_A_boot_list", ", ".join(a[a.reject_boot_n].ticker), "fullsample_recomputed.csv", note="")
    # 데이터 개관 (그림 fig11): 연율화 변동성 = 일간 100·Δlog 표준편차 × √252
    import os

    z = np.load(os.environ.get("T11_STATE", HERE.parents[1] / "outputs" / "cache" / "t11_state.npz"), allow_pickle=True)
    fitsum = pd.read_csv(HERE.parents[1] / "research" / "svr_garch_cusum_etf" / "results" / "fit_summary.csv", dtype={"ticker": str})
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    ratios = {}
    for t in [str(x) for x in z["tickers"]]:
        sp = int(idx.searchsorted(pd.Timestamp(fitsum.set_index("ticker").loc[t, "split_date"])))
        r = z[f"r__{t}"]
        vf, vt = np.nanstd(r[:sp]) * np.sqrt(252), np.nanstd(r[sp:]) * np.sqrt(252)
        ratios[t] = vt / vf
        if t == "069500":
            add("vol_069500_fit", round(float(vf), 1), "t11_state.npz r__069500 적합 구간 std×√252", note="%/년")
            add("vol_069500_test", round(float(vt), 1), "t11_state.npz r__069500 검정 구간 std×√252", note="%/년")
    add("vol_test_gt_fit", int(sum(v > 1 for v in ratios.values())), "t11_state.npz 검정 구간 변동성 > 적합 구간인 ETF 수", note="")
    add("vol_ratio_median", round(float(np.median(list(ratios.values()))), 2), "검정/적합 연율화 변동성 비 중앙값 (20종)", note="")
    out = HERE / "claims.json"
    out.write_text(json.dumps(claims, ensure_ascii=False, indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
    print(len(claims), "claims →", out)


if __name__ == "__main__":
    main()
