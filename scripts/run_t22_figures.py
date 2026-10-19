"""12B P06 — 그림 생성 + G6 (그린 배열 = 정렬 원장 값) 검사. 캡션 수치는 results/figure_captions.json.

사용: PYTHONNOUSERSITE=1 PYTHONPATH=src <R2H .venv>/bin/python scripts/run_t22_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import figures as G  # noqa: E402

BASE = ROOT / "research/k200_cusum_overlay_12b"
RES = BASE / "results"
OUT = ROOT / "outputs/t22"
FS = ROOT / "outputs/t21/feature_store_n1"


def load() -> dict:
    ev = pd.read_csv(RES / "events_table.csv", parse_dates=["start", "end"])
    return {
        "master": pd.read_parquet(OUT / "market_daily_master.parquet"),
        "aligned": pd.read_parquet(OUT / "policy_market_aligned.parquet"),
        "events": ev,
        "triggers": pd.read_parquet(FS / "daily_change_point_triggers.parquet"),
        "resets": pd.read_parquet(FS / "daily_reset_events.parquet"),
        "svr": pd.read_parquet(FS / "daily_svr_predictions.parquet"),
        "ceiling": pd.read_parquet(OUT / "svr_forecast_ceiling_daily.parquet"),
        "regime": pd.read_parquet(OUT / "volatility_regime_daily.parquet"),
        "x1": pd.read_parquet(OUT / "x1_real_daily.parquet"),
        "x1_crit": json.loads((BASE / "evidence/x1_checks.json").read_text(encoding="utf-8"))["crit"],
        "window_exits": pd.read_csv(RES / "window_exits.csv", parse_dates=["shock_date", "exit_date"]),
        "regime_matrix": pd.read_csv(RES / "volatility_regime_policy_matrix.csv.gz"),
        "vol_response": pd.read_csv(RES / "annualized_volatility_response.csv"),
        "event_aligned": pd.read_csv(RES / "event_aligned_response.csv.gz"),
        "lead_lag": pd.read_csv(RES / "lead_lag_response.csv"),
        "lead_peak": pd.read_csv(RES / "lead_lag_peak.csv"),
        "clusters": pd.read_csv(RES / "agreement_clusters.csv"),
        "agreement": pd.read_csv(RES / "policy_agreement.csv.gz"),
        "ofat": pd.read_csv(RES / "ofat_pair_comparison.csv"),
        "refit_breaks": pd.read_csv(ROOT / "research/k200_cusum_controlled_12/results/refit_boundary_breaks.csv"),
        "shock_type": pd.read_csv(RES / "shock_type_response.csv"),
        "features": pd.read_csv(RES / "feature_incremental_information.csv"),
        "features_common": pd.read_csv(RES / "feature_incremental_information_common_days.csv"),
        "yearly": pd.read_csv(RES / "yearly_stability.csv"),
    }


def g6_check(f: G.Figures12B, al: pd.DataFrame) -> list[dict]:
    """그린 배열을 원장 정렬 테이블에서 다시 뽑아 비교."""
    rows = []
    for name, arrs in f.drawn.items():
        if name.startswith("G05_"):
            col = str(arrs["col"][0])
            for role in ("parent", "child"):
                eid = f.caps[name][role]
                ref = al.loc[al["experiment_id"] == eid].sort_values("date")[col].to_numpy(float)
                rows.append({"figure": name, "series": f"{role}:{eid}:{col}", "equal": bool(np.array_equal(ref, arrs[role], equal_nan=True))})
        elif name == "g01":
            for eid, y in arrs.items():
                ref = al.loc[al["experiment_id"] == eid].sort_values("date")["T_past_pct"].to_numpy(float)
                rows.append({"figure": "G01", "series": eid, "equal": bool(np.array_equal(ref, y, equal_nan=True))})
        elif name == "g02":
            for k, eid in (("X1_up", "X1_page_up_sn"), ("X1_down", "X1_page_down_sn")):
                # 경보 경로는 원장에 없는 파생값 → 원장 원시 상태와 경보일에서 같은 값이 나오는지(경보 전까지 동일) 확인
                raw = al.loc[al["experiment_id"] == eid].sort_values("date")
                first = np.flatnonzero(raw["cusum_alarm_a05"].to_numpy(bool))
                stop = first[0] + 1 if first.size else len(raw)
                rows.append({"figure": "G02", "series": f"{eid} 경보 전 경로", "equal": bool(np.array_equal(raw["cusum_raw_T"].to_numpy(float)[:stop], arrs[k][:stop], equal_nan=True))})
        elif name == "g11":
            order = f.d["clusters"].sort_values(["value_cluster", "family", "experiment_id"])["experiment_id"].tolist()
            ref = al.pivot(index="date", columns="experiment_id", values="T_past_pct")[order].to_numpy(float).T
            rows.append({"figure": "G11", "series": "463x1473", "equal": bool(np.array_equal(ref, arrs["matrix"], equal_nan=True))})
    return rows


def main() -> int:
    d = load()
    f = G.Figures12B(ROOT, d)
    f.g01_market_map()
    f.g02_x1_real()
    f.g03_x1_zoom()
    f.g04_forecast_ceiling()
    for i, (p, c, lab) in enumerate(G.PAIRS, start=1):
        f.g05_pair(p, c, lab, i)
    f.g06_yearly()
    f.g07_window_exit()
    f.g08_regime_heatmap()
    f.g09_event_aligned()
    f.g10_lead_lag()
    f.g11_all_policy_heatmap()
    f.g12_agreement()
    f.g13_reset_gaps()
    f.g14_svr_policies()
    f.g15_shock_type()
    f.g16_feature_value()
    f.g17_yearly_stability()
    chk = pd.DataFrame(g6_check(f, d["aligned"]))
    chk.to_csv(BASE / "evidence/g6_figure_ledger_check.csv", index=False)
    (RES / "figure_captions.json").write_text(json.dumps(f.caps, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(chk.to_string())
    print("그림", len(f.caps), "G6", bool(chk["equal"].all()))
    return 0 if chk["equal"].all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
