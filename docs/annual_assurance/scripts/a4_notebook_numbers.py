"""A-4 — 노트북(B `871dc62`) 서술 문장의 숫자를 결과표(seq_golden 사본)에서 A 가 독립적으로 다시 계산한다.

t12_figures.py 의 aggregates/derived_tables 를 쓰지 않는다. 결과표 CSV 만 읽는다.
실행: <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a4_notebook_numbers.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
R = ROOT / "research" / "t12_annual_expanding_v2" / "results"
rd = lambda n: pd.read_csv(R / f"{n}.csv", dtype={"ticker": str})  # noqa: E731
ph, cu, fc, fs = rd("annual_posthoc"), rd("annual_cusum_diagnostics"), rd("annual_forecast_diagnostics"), rd("fit_summary")
ab, pr, vol, syn = rd("annual_history_ablation"), rd("diagnostic_profile"), rd("annual_vol_diagnostics"), rd("null_dgp_validation")
B = lambda s: s.map({True: True, False: False, "True": True, "False": False}).fillna(False).astype(bool)  # noqa: E731
core = lambda d: d[d.year.between(2021, 2025)]  # noqa: E731
out = []


def chk(label, got, claim):
    out.append(f"{label}: 계산 {got} | 노트북 {claim}")


a = ph[ph.calibration_method == "asymptotic"].assign(r=lambda d: B(d.annual_reject))
chk("cell20 기각 asym 연도×정책", a.pivot_table(index="year", columns="policy", values="r", aggfunc="sum").to_dict(), "표")
chk("cell20/54 핵심 asym 기각 A/B/base", core(a).groupby("policy").r.sum().to_dict(), "0/12/6")
ii = ph[ph.calibration_method == "iid_insample"].assign(r=lambda d: B(d.annual_reject))
chk("cell20 핵심 iid_insample", core(ii).groupby("policy").r.sum().to_dict(), "2/12/12")
w = cu[(cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED") & (cu.calibration_method == "iid_insample")]
g = core(w).groupby("policy")[["rolling_episodes", "expected_null_episodes"]].sum()
chk("cell20/22 핵심 w60 관측/귀무", g.round(3).to_dict(), "A 26/132.22 · B 171/132.975 · base 346/135.675; 비 B≈1.3 base≈2.6")
chk("cell22 비율", (g.rolling_episodes / g.expected_null_episodes).round(2).to_dict(), "B 1.3 · base 2.6")
med = ph.groupby(["calibration_method"]).annual_critical.median().round(3).to_dict()
chk("cell36 연간 임계값 중앙값 (전체)", med, "1.3397 · normal≈1.31 · iid_insample≈1.27–1.28")
chk("cell36 block 중앙값 by policy", ph[ph.calibration_method == "block_insample"].groupby("policy").annual_critical.median().round(3).to_dict(), "A·B≈1.05 · base≈1.66")
chk("cell36 SENSITIVITY_CONFIRMED", pr[pr.sensitivity_status == "SENSITIVITY_CONFIRMED"].groupby("policy").size().to_dict(), "A104·B76·base34")
p = a.pivot_table(index=["year", "policy"], columns="ticker", values="annual_T")
d = (p["069500"] - p["102110"]).abs().groupby(level="policy").max().round(3).to_dict()
chk("cell38 |T(069500)−T(102110)| max", d, "A≈0.07 · B≈0.64")
m = a.merge(vol[["ticker", "year", "rv_ratio"]], on=["ticker", "year"])
for scope, dd in (("core", core(m)), ("all", m)):
    chk(f"cell40 Spearman T~rv_ratio {scope}", dd.groupby("policy").apply(lambda x: round(x[["annual_T", "rv_ratio"]].corr("spearman").iloc[0, 1], 3)).to_dict(), "core A−.183 B−.046 base−.083 / all .182 .232 .411")
cf = core(fc)
chk("cell42 핵심 mean e² 중앙값", cf.groupby("policy").mean_sq_standardized_residual.median().round(3).to_dict(), "A1.386 B.947 base1.111")
chk("cell42 mean e² ≥1.5 비율", cf.groupby("policy").mean_sq_standardized_residual.apply(lambda s: round((s >= 1.5).mean(), 2)).to_dict(), "A.28 B.07 base.04")
q = fc[fc.policy == "A"].set_index(["ticker", "year"]).oos_qlike - fc[fc.policy == "base"].set_index(["ticker", "year"]).oos_qlike
chk("cell42 QLIKE A−base 연도 중앙값", q.groupby(level="year").median().round(3).to_dict(), "2020 +.43 · 2022/2025 ≈+.1")
e = fs[fs.history_strategy == "expanding"]
chk("cell42/11.2 ε=0.1 비율", round(float((e.epsilon == 0.1).mean()), 3), "0.986")
c = ab[(ab.h_status == "COMPUTED") & (ab.history_strategy != "expanding")]
for s in ("frozen_2019", "trailing_2y"):
    x = c[(c.policy == "A") & (c.history_strategy == s)]
    chk(f"cell44 {s} A 악화 비율·Δ중앙값", (round(float((x.d_qlike_vs_expanding > 0).mean()), 3), round(float(x.d_qlike_vs_expanding.median()), 3)), "frozen .942/.157 · trailing .65")
ref = ab[ab.history_strategy == "expanding"].set_index(["ticker", "year", "policy"]).annual_reject_asymptotic
cc = c.set_index(["ticker", "year", "policy"])
flip = (B(cc.annual_reject_asymptotic) != B(ref.reindex(cc.index))).groupby(level="policy").agg(["sum", "size"])
chk("cell44 H 판정 차이 (A/B, /대조 수)", flip.to_dict(), "A 9/220 · B 46/220")
sig = pr[B(pr.signal_present)]
chk("cell45 신호·w60 단독", (sig.groupby("policy").size().to_dict(), sig[~B(sig.annual_reject_asym)].groupby("policy").size().to_dict()), "41/111/138 · 30/83/104")
chk("cell45 null_prob_any 평균·범위", (round(w.null_prob_any_episode.mean(), 3), w.null_prob_any_episode.min(), w.null_prob_any_episode.max()), "0.684 (0.49–0.81)")
chk("cell28 RV 2026 중앙값", round(float(vol[vol.year == 2026].rv_ann_pct.median()), 2), "≈50")
chk("cell28 RV 상위 3 ETF (2020–26 평균)", vol.groupby("ticker").rv_ann_pct.mean().sort_values().tail(3).round(1).to_dict(), "305540·122630·261220")
s = syn.set_index(["dgp_name", "test", "calibration"]).rate
chk("cell52 검출기 iid·t5 연간 size (asym, iid)", {k: (s[(k, "annual_posthoc", "asymptotic_1.3397")], s[(k, "annual_posthoc", "iid_history_bootstrap")]) for k in ("stable_low_variance_no_change", "stable_heavy_tail")}, "'0.04–0.06 (iid 보정 0.049·0.051)'")
print("\n".join(out))
