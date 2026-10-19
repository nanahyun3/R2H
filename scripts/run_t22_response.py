"""12B P03 — 정책 반응: 국면 행렬 · 연환산변동성 반응 · 선행후행 · 이벤트 정렬 · 연도별 안정성 · 충격 유형 (서술).

출력: results/{volatility_regime_policy_matrix, annualized_volatility_response, lead_lag_response, lead_lag_peak,
event_aligned_response(대표 정책), event_phase_summary, yearly_stability, shock_type_response}.csv
· outputs/t22/event_aligned_policy_daily.parquet (전체 정책 장형)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import response as P  # noqa: E402

OUT = ROOT / "outputs/t22"
RES = ROOT / "research/k200_cusum_overlay_12b/results"
REP = ["B1", "B0", "E2_w20", "E2_w30", "E2_w120", "E2_w252", "E3_page_up", "E3_page_down", "E3_page_two", "E3_raw_rolling_cos",
       "X1_page_up_sn", "X1_page_down_sn", "X1_page_two_sn", "E6_win252", "E6_win504", "E6_win756", "E6_win252_page_two",
       "E6_win504_page_two", "E6_win756_page_two", "E7_refit21", "E7_refit63", "E7_refit21_page_two", "E7_refit63_page_two"]


def main() -> int:
    t0 = time.time()
    mk = pd.read_parquet(OUT / "market_daily_master.parquet")
    al = pd.read_parquet(OUT / "policy_market_aligned.parquet")
    reg = pd.read_parquet(OUT / "volatility_regime_daily.parquet").sort_values(["anchor_w", "date"], kind="mergesort")
    for _, g in reg.groupby("anchor_w"):
        if not (g["date"].to_numpy() == mk["date"].to_numpy()).all():
            raise AssertionError("국면 날짜축 불일치")
    r20 = reg[reg["anchor_w"] == 20].reset_index(drop=True)
    ev = pd.read_csv(RES / "events_table.csv")
    meta, M = P.to_matrices(al, mk["date"])
    del al
    print(f"정책 {len(meta)} × 날짜 {len(mk)}")

    P.regime_matrix(meta, M, reg).to_csv(RES / "volatility_regime_policy_matrix.csv", index=False)
    vr = P.vol_response(meta, M, mk, r20)
    vr.to_csv(RES / "annualized_volatility_response.csv", index=False)
    L, PK = P.lead_lag_all(meta, M, mk)
    L.to_csv(RES / "lead_lag_response.csv", index=False)
    PK.to_csv(RES / "lead_lag_peak.csv", index=False)
    ea = P.event_aligned(meta, M, mk, ev)
    ea.to_parquet(OUT / "event_aligned_policy_daily.parquet", index=False)
    rep = [e for e in REP if e in set(meta["experiment_id"])]
    ea[ea["experiment_id"].isin(rep)].to_csv(RES / "event_aligned_response.csv", index=False)
    P.event_phase_summary(ea).to_csv(RES / "event_phase_summary.csv", index=False)
    st = P.shock_type_response(ea)
    st.to_csv(RES / "shock_type_response.csv", index=False)
    ys = P.yearly_stability(meta, M, mk, r20)
    ys.to_csv(RES / "yearly_stability.csv", index=False)

    # 짧은 요약
    k = vr.set_index("experiment_id")
    print("EXPANDING−STABLE 상위:", k["contrast_EXPANDING_minus_STABLE"].nlargest(5).round(3).to_dict())
    print("HIGH/EXT·STABLE − LOW/MID·STABLE 상위:", k["contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE"].nlargest(5).round(3).to_dict())
    print("CONTRACTING−STABLE 상위:", k["contrast_CONTRACTING_minus_STABLE"].nlargest(5).round(3).to_dict())
    pk = PK.set_index("experiment_id")
    print(pk.loc[[e for e in rep if e in pk.index], ["peak_lag", "rho_peak", "rho_lag0", "peak_lag_ex2020", "rho_peak_ex2020"]].round(3).to_string())
    b = k[["rho_vol20", "rho_vol20_ex2020"]].dropna()
    print("ρ(vol20) 부호 변경 (2020 제외):", int((np.sign(b.iloc[:, 0]) != np.sign(b.iloc[:, 1])).sum()), "/", len(b))
    print(f"소요 {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
