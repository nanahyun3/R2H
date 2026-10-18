"""감사 — 크기 검증 실패 분해 · 피처 원장 무결성 (사용자 감사 요청 1–3, 2026-10-19).

크기 실패(holdout 이 α 의 구간 밖)는 같은 DGP 의 보정·홀드아웃 사이 문제이므로 **보정 실패**다.
관측 자료가 귀무를 따르지 않는 것은 **귀무 부적합**(``null_validity``)이며 둘은 다른 축이다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def reset_family(r: str) -> str:
    if r in ("none", "NA"):
        return "none"
    if r.startswith("cp:"):
        return "cp_" + r.split(":")[1][0]
    if r == "placebo_random":
        return "placebo_random"
    return "calendar"


def size_decomposition(size: pd.DataFrame, invalid_pipelines: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """행 판정: OK / CALIBRATION_FAIL_WILSON_ONLY (군집 CI 로는 통과) / CALIBRATION_FAIL (둘 다 밖).
    귀무 부적합 여부는 별도 열 (관측 파이프라인 기준)."""
    s = size.copy()
    s["reset_family"] = s["reset"].map(reset_family)
    has_cluster = "size_ok_cluster" in s
    def verdict(r):
        if r["size_ok"]:
            return "OK"
        if has_cluster and r["size_ok_cluster"]:
            return "CALIBRATION_FAIL_WILSON_ONLY"
        return "CALIBRATION_FAIL"
    s["size_verdict"] = s.apply(verdict, axis=1)
    s["observed_null_invalid"] = s["svr"].isin(invalid_pipelines)
    s["direction"] = np.where(s["holdout_rate"] > s["alpha"], "OVER", "UNDER")
    keys = ["calibration", "detector", "w", "svr", "reset_family", "alpha"]
    agg = (
        s.groupby(keys, dropna=False)
        .agg(n=("size_ok", "size"), n_fail_wilson=("size_ok", lambda x: int((~x).sum())),
             n_fail_cluster=("size_verdict", lambda x: int((x == "CALIBRATION_FAIL").sum())),
             mean_holdout=("holdout_rate", "mean"), max_holdout=("holdout_rate", "max"),
             mean_icc=("block_icc", "mean") if "block_icc" in s else ("holdout_rate", "size"),
             observed_null_invalid=("observed_null_invalid", "max"))
        .reset_index()
    )
    return s, agg


def ledger_audit(ledger: pd.DataFrame, n_days: int, n_experiments: int) -> pd.DataFrame:
    """원장 행 수 · 상태별 행 수 · 원시 통계량 보존 · 0/1 대입 여부."""
    rows = [
        {"check": "rows_total", "value": len(ledger), "expected": n_days * n_experiments,
         "pass": len(ledger) == n_days * n_experiments},
        {"check": "experiments", "value": ledger["experiment_id"].nunique(), "expected": n_experiments,
         "pass": ledger["experiment_id"].nunique() == n_experiments},
    ]
    for st, n in ledger["significance_status"].value_counts().sort_index().items():
        rows.append({"check": f"status_{st}", "value": int(n), "expected": None, "pass": True})
    for st, n in ledger["pvalue_status"].value_counts().sort_index().items():
        rows.append({"check": f"pvalue_status_{st}", "value": int(n), "expected": None, "pass": True})
    valid = ledger["cusum_statistic_valid"]
    rows.append({"check": "raw_T_present_when_valid", "value": int(ledger.loc[valid, "cusum_raw_T"].isna().sum()),
                 "expected": 0, "pass": bool(ledger.loc[valid, "cusum_raw_T"].notna().all())})
    rows.append({"check": "raw_T_nan_only_when_invalid", "value": int(ledger.loc[~valid, "cusum_raw_T"].notna().sum()),
                 "expected": 0, "pass": bool(ledger.loc[~valid, "cusum_raw_T"].isna().all())})
    ns = ledger["significance_status"] == "NOT_SIGNIFICANT"
    rows.append({"check": "not_significant_rows_keep_T", "value": int(ledger.loc[ns, "cusum_raw_T"].notna().sum()),
                 "expected": int(ns.sum()), "pass": bool(ledger.loc[ns, "cusum_raw_T"].notna().all())})
    inv = ledger["significance_status"] == "NULL_MODEL_INVALID"
    rows.append({"check": "null_invalid_rows_keep_T", "value": int(ledger.loc[inv, "cusum_raw_T"].notna().sum()),
                 "expected": int(inv.sum()), "pass": bool(ledger.loc[inv, "cusum_raw_T"].notna().all())})
    rows.append({"check": "null_invalid_rows_confirmatory_p_is_NA",
                 "value": int(ledger.loc[~ledger["cusum_null_valid"], "confirmatory_p"].notna().sum()), "expected": 0,
                 "pass": bool(ledger.loc[~ledger["cusum_null_valid"], "confirmatory_p"].isna().all())})
    npc = ledger["pvalue_status"] == "P_VALUE_NOT_CALCULATED"
    rows.append({"check": "p_not_calculated_rows_p_is_NA_and_T_kept",
                 "value": int(ledger.loc[npc, "cusum_tail_probability"].notna().sum()), "expected": 0,
                 "pass": bool(ledger.loc[npc, "cusum_tail_probability"].isna().all() and ledger.loc[npc, "cusum_raw_T"].notna().all())})
    rows.append({"check": "no_p_equal_one_imputation_on_invalid_days",
                 "value": int((ledger.loc[~valid, "cusum_adjusted_pvalue"] == 1.0).sum()), "expected": 0,
                 "pass": bool((ledger.loc[~valid, "cusum_adjusted_pvalue"] == 1.0).sum() == 0)})
    rows.append({"check": "no_zero_imputation_on_invalid_days",
                 "value": int((ledger.loc[~valid, "cusum_raw_T"] == 0.0).sum()), "expected": 0,
                 "pass": bool((ledger.loc[~valid, "cusum_raw_T"] == 0.0).sum() == 0)})
    return pd.DataFrame(rows)
