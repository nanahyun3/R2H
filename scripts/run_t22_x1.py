"""12B P02 — X1 자기정규화 Page 실데이터 해부 + SVR 예측 상한 고정 진단 (D-03).

출력: results/{x1_real_daily,x1_event_table,x1_alarm_days,svr_forecast_ceiling_summary}.csv · evidence/x1_checks.json ·
      outputs/t22/svr_forecast_ceiling_daily.parquet
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import align as A  # noqa: E402
from r2h.k200_overlay import x1 as X  # noqa: E402

BASE = ROOT / "research/k200_cusum_overlay_12b"
OUT = ROOT / "outputs/t22"


def main() -> int:
    cfg = A.load_cfg()
    al = pd.read_parquet(OUT / "policy_market_aligned.parquet")
    df, chk = X.build(cfg, al)
    ma = pd.read_parquet(OUT / "market_daily_master.parquet")
    df = df.merge(ma[["date", "close", "daily_log_return_pct", "annualized_vol_20", "annualized_vol_60", "predicted_variance_B1"]], on="date", how="left", validate="1:1")
    df.to_csv(BASE / "results/x1_real_daily.csv", index=False)
    ev = pd.read_csv(BASE / "results/events_table.csv", parse_dates=["start", "end"])
    X.event_table(df, ev, chk["crit"]).to_csv(BASE / "results/x1_event_table.csv", index=False)
    rows = []
    for c in [c for c in df.columns if "_alarm_" in c]:
        for d in df.loc[df[c], "date"]:
            rows.append({"series": c, "date": d, "reference_only": c.endswith("_REFERENCE")})
    pd.DataFrame(rows).to_csv(BASE / "results/x1_alarm_days.csv", index=False)
    # SVR 예측 상한 고정
    svr = pd.read_parquet(A.fs_path(cfg, "daily_svr_predictions"))
    fc = X.forecast_ceiling(svr)
    fc = fc.merge(ma[["date", "daily_log_return_pct", "rolling_vol_20"]], on="date", how="left")
    fc.to_parquet(OUT / "svr_forecast_ceiling_daily.parquet", index=False)
    s = fc[fc["forecast_ceiling"]].groupby(["policy_id", "model_fit_id"]).agg(
        ceiling_value=("predicted_variance", "first"), days=("date", "size"), first=("date", "min"), last=("date", "max"),
        mean_abs_return=("daily_log_return_pct", lambda x: float(np.mean(np.abs(x)))), mean_rv20=("rolling_vol_20", "mean")).reset_index()
    s.to_csv(BASE / "results/svr_forecast_ceiling_summary.csv", index=False)
    chk["forecast_ceiling_days_by_policy"] = fc.groupby("policy_id")["forecast_ceiling"].sum().astype(int).to_dict()
    chk["crit"] = {k: {str(a): (list(v) if isinstance(v, tuple) else v) for a, v in d.items()} for k, d in chk["crit"].items()}
    (BASE / "evidence/x1_checks.json").write_text(json.dumps(chk, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    ok = all(v for k, v in chk.items() if k.endswith("_equal"))
    print(json.dumps({k: v for k, v in chk.items() if k != "crit"}, ensure_ascii=False, default=str))
    print(s.to_string())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
