"""12B P01 — 시장 마스터 · 463 정책 전수 정렬 · 정렬 감사 (12B-lock-1 §3–§4, G1–G3·G7).

사용: PYTHONNOUSERSITE=1 PYTHONPATH=src <R2H .venv>/bin/python scripts/run_t22_align.py
출력: outputs/t22/{market_daily_master,policy_market_aligned}.parquet (git 제외) ·
      research/k200_cusum_overlay_12b/results/{market_daily_summary,policy_market_alignment_audit}.csv
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

OUT = ROOT / "outputs/t22"
RES = ROOT / "research/k200_cusum_overlay_12b/results"


def main() -> int:
    cfg = A.load_cfg()
    OUT.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    ma, _full = A.market_master(cfg)
    exp = cfg["expected"]
    # G1 날짜축
    assert len(ma) == exp["eval_days"] and not ma["date"].duplicated().any(), "G1"
    # G3 시장변수: 12번 Feature Store 와 대조
    dm = pd.read_parquet(A.fs_path(cfg, "daily_market_features"))
    g3 = {"close": float(np.max(np.abs(dm["close"].to_numpy() - ma["close"].to_numpy()))),
          "return": float(np.max(np.abs(dm["return_log_pct"].to_numpy() - ma["daily_log_return_pct"].to_numpy())))}
    for w in (5, 20, 60, 120):
        g3[f"rv{w}"] = float(np.nanmax(np.abs(dm[f"rv{w}"].to_numpy() - ma[f"rolling_vol_{w}"].to_numpy())))
        g3[f"rv{w}_na_equal"] = bool((dm[f"rv{w}"].isna() == ma[f"rolling_vol_{w}"].isna()).all())
    g3["annualization_identity"] = float(np.nanmax(np.abs(ma["annualized_vol_20"] - np.sqrt(252) * ma["rolling_vol_20"])))
    g3["rv252_na_days"] = int(ma["rolling_vol_252"].isna().sum())
    g3["predicted_nonpositive_days"] = int((ma["predicted_vol_status"] != "OK").sum())
    ma.to_parquet(OUT / "market_daily_master.parquet", index=False)
    # 시장 요약 (연도별)
    summ = ma.groupby("calendar_year").agg(
        days=("date", "size"), close_first=("close", "first"), close_last=("close", "last"),
        cum_log_return_end=("cumulative_log_return", "last"), ret_sd=("daily_log_return_pct", "std"),
        ret_min=("daily_log_return_pct", "min"), ret_max=("daily_log_return_pct", "max"),
        ann_vol20_mean=("annualized_vol_20", "mean"), ann_vol20_max=("annualized_vol_20", "max"),
        ann_vol60_mean=("annualized_vol_60", "mean"), ann_vol252_mean=("annualized_vol_252", "mean"),
        pred_ann_vol_B1_mean=("predicted_vol_annualized_B1", "mean"),
    ).reset_index()
    summ["realized_ann_vol_year"] = summ["ret_sd"] * np.sqrt(252)
    summ.to_csv(RES / "market_daily_summary.csv", index=False)
    # 정렬
    al = A.aligned(cfg, ma)
    hm = A.check_h_match(al)
    reg = pd.read_csv(ROOT / cfg["frozen_inputs"]["registry"], keep_default_na=False, dtype=str)
    ids = set(al["experiment_id"])
    posthoc = sorted(set(reg["experiment_id"]) - ids)
    led = pd.read_parquet(A.fs_path(cfg, "daily_cusum_features"), columns=["experiment_id", "date", "cusum_raw_T"])
    led = led.sort_values(["experiment_id", "date"], kind="mergesort").reset_index(drop=True)
    raw_equal = bool(np.array_equal(led["cusum_raw_T"].to_numpy(), al["cusum_raw_T"].to_numpy(), equal_nan=True))
    na_led = int(led["cusum_raw_T"].isna().sum())
    audit = [
        ("G1", "eval_days", len(ma), exp["eval_days"]),
        ("G1", "duplicate_dates", int(ma["date"].duplicated().sum()), 0),
        ("G2", "aligned_rows", len(al), exp["ledger_rows"]),
        ("G2", "daily_experiments", len(ids), exp["daily_experiments"]),
        ("G2", "registry_experiments", len(reg), exp["registry_experiments"]),
        ("G2", "posthoc_not_aligned", ";".join(posthoc), exp["posthoc_experiment"]),
        ("G2", "duplicate_date_experiment", int(al.duplicated(["date", "experiment_id"]).sum()), 0),
        ("G2", "rows_per_experiment_min", int(al.groupby("experiment_id").size().min()), exp["eval_days"]),
        ("G2", "rows_per_experiment_max", int(al.groupby("experiment_id").size().max()), exp["eval_days"]),
        ("G7", "raw_T_identical_to_ledger", raw_equal, True),
        ("G7", "raw_T_na_rows_ledger", na_led, na_led),
        ("G7", "raw_T_na_rows_aligned", int(al["cusum_raw_T"].isna().sum()), na_led),
        ("G7", "past_pct_nonnull_where_T_na", int((al["cusum_raw_T"].isna() & al["T_past_pct"].notna()).sum()), 0),
        ("B", "two_sided_ledger_h_equals_h_up", hm["max_abs_diff_two_sided_vs_h_up"], 0.0),
        ("B", "experiments_without_h", len(hm["experiments_without_h"]), 0),
    ] + [("G3", k, v, 0.0 if isinstance(v, float) and "na" not in k else v) for k, v in g3.items()]
    for k, v in al["T_past_status"].value_counts().items():
        audit.append(("D", f"T_past_status_{k}", int(v), ""))
    aud = pd.DataFrame(audit, columns=["gate", "check", "value", "expected"])
    aud["pass"] = [
        (str(v) == str(e)) if not isinstance(v, float) else (abs(v - float(e)) < 1e-9 if e != "" else True)
        for v, e in zip(aud["value"], aud["expected"], strict=True)
    ]
    aud.loc[aud["check"].isin(["rv252_na_days", "predicted_nonpositive_days"]), "pass"] = True
    aud.loc[aud["gate"] == "D", "pass"] = True
    aud.to_csv(RES / "policy_market_alignment_audit.csv", index=False)
    al.to_parquet(OUT / "policy_market_aligned.parquet", index=False)
    print(aud.to_string())
    print(json.dumps({"rows": len(al), "cols": al.shape[1], "all_pass": bool(aud["pass"].all())}, ensure_ascii=False))
    return 0 if aud["pass"].all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
