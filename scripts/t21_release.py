"""12번 인계·릴리스 산출물 — 등록부(지표 포함) · 정책/초기화 요약 · 피처 카탈로그·스키마 · 데이터 산출물 목록 · 입력 해시 · 릴리스 목록.

결과 CSV(results/)와 원장(outputs/t21/feature_store_n1/, Git 제외)을 읽기만 한다.
사용: R2H .venv/bin/python scripts/t21_release.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import registry as RG  # noqa: E402

BASE = ROOT / "research/k200_cusum_controlled_12"
RES = BASE / "results"
STORE = ROOT / "outputs/t21/feature_store_n1"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def w(df: pd.DataFrame, name: str) -> None:
    df.to_csv(RES / name, index=False, float_format="%.10g", lineterminator="\n")


# AE 피처 분류 (사전 규칙: 관측 가능 시점 · 중복 · 사후 전용)
FEATURE_META = {
    "ret": ("return", "close_t", "KEEP", "기본 입력"),
    "abs_ret": ("return", "close_t", "DROP_DUPLICATE", "e2_B1 과 Spearman 0.95"),
    "rv5": ("multi_horizon_vol", "close_t", "KEEP", "단기 변동성"),
    "rv20": ("multi_horizon_vol", "close_t", "KEEP", "기준 변동성 (증분 R² 기준선)"),
    "rv60": ("multi_horizon_vol", "close_t", "KEEP", "장기 변동성"),
    "rv_ratio_5_60": ("vol_expansion", "close_t", "OPTIONAL", "rv5·rv60 로 재구성 가능 (R² 0.89)"),
    "vhat_B1": ("svr_forecast", "close_t-1 (t 예측)", "KEEP", "SVR 정책 A 예측분산"),
    "e_B1": ("svr_residual", "close_t", "DROP_DUPLICATE", "ret 과 Spearman 0.99"),
    "e2_B1": ("svr_residual", "close_t", "KEEP", "잔차 크기 (척도 ≠ 1 주의)"),
    "dlog_vhat20_B1": ("svr_forecast_change", "close_t", "OPTIONAL", "X4 — 증분 정보 작음"),
    "cos_w20_B1": ("cusum_rolling", "close_t", "KEEP", "다른 피처와 중복 낮음 (R² 0.22)"),
    "cos_w30_B1": ("cusum_rolling", "close_t", "OPTIONAL", "w20 과 0.40"),
    "cos_w60_B1": ("cusum_rolling", "close_t", "KEEP", "기준 창"),
    "cos_w60_B0": ("cusum_rolling", "close_t", "DROP_DUPLICATE", "B1 과 유효일 동일 (연초 NA 만 다름)"),
    "cos_w120_B1": ("cusum_rolling", "close_t", "KEEP", "기억 채널 (X-D7)"),
    "cos_w252_B1": ("cusum_rolling", "close_t", "KEEP_WITH_CAVEAT", "최대 252일 이월 — 시점 피처 아님 (X-D7)"),
    "cos_raw_w60": ("cusum_raw", "close_t", "KEEP", "SVR 흡수 전 신호 (잔차 CoS 와 0.59)"),
    "cos_w60_refit21": ("cusum_rolling", "close_t", "DROP_DUPLICATE", "B1 과 0.89"),
    "page_up_B1": ("cusum_page", "close_t", "EXCLUDE_NONSTATIONARY", "2020 척도 누적 후 단조 감쇠 — 증분 R² 0.098 은 추세 대리 (X-D1)"),
    "page_dn_B1": ("cusum_page", "close_t", "KEEP", "분산 감소 채널 (S12 검출)"),
    "page_up_refit21": ("cusum_page", "close_t", "OPTIONAL", "재학습으로 누적 완화"),
    "P20_score": ("change_point_price", "close_t", "KEEP", "중복 낮음 (R² 0.30)"),
    "V5_two_score": ("change_point_vol", "close_t", "OPTIONAL", "rv_ratio 와 0.65"),
    "V20_two_score": ("change_point_vol", "close_t", "KEEP", "주 변화점 규칙의 점수"),
    "V60_two_score": ("change_point_vol", "close_t", "OPTIONAL", "rv60 과 0.50"),
    "M20_60_score": ("change_point_ma", "close_t", "KEEP", "중복 낮음 (R² 0.36), 증분 0.044"),
    "K60_score": ("change_point_kurt", "close_t", "KEEP", "꼬리 모양 채널"),
    "POSTHOC_future_rv20": ("label_posthoc", "close_t+20", "POSTHOC_ONLY", "평가 전용 — AE 입력 금지"),
}


def main() -> None:
    reg = RG.build()
    summ = pd.read_csv(RES / "experiment_summary.csv")
    size = pd.read_csv(RES / "size_holdout.csv", keep_default_na=False, na_values=[""])
    eff = pd.read_csv(RES / "synthetic_effects.csv", keep_default_na=False, na_values=[""])
    led = pd.read_parquet(STORE / "daily_cusum_features.parquet")

    # 입력 해시
    inp = {"069500.csv": sha(ROOT / "data/raw/069500.csv"), "events_11_intervals.csv": sha(ROOT / "research/etf_shock_bottomup_11/results/intervals.csv"),
           "config": sha(ROOT / "configs/t21_k200_cusum_controlled_v1.json"),
           "w3_individual_cusum_summary": sha(ROOT / "research/joint_cusum_w3/results/08/individual_cusum_summary.csv")}
    (BASE / "evidence/input_hashes.json").write_text(json.dumps(inp, indent=1) + "\n", encoding="utf-8")

    # 등록부 (계약 §10 필수 필드)
    fit = pd.read_csv(RES / "svr_fits.csv")
    model_hash = fit.groupby("pipeline")["model_hash"].apply(lambda s: hashlib.sha256("|".join(s).encode()).hexdigest()[:16]).to_dict()
    resid_hash = led.groupby("policy_id")["residual_std"].apply(lambda s: hashlib.sha256(s.to_numpy("<f8").tobytes()).hexdigest()[:16]).to_dict()
    s05 = size[(size["alpha"] == 0.05)].assign(w=lambda d: d["w"].fillna("NA").astype(str).str.replace(".0", "", regex=False), svr=lambda d: d["svr"].fillna("NA"))
    pw = pd.read_csv(RES / "synthetic_size_power.csv", keep_default_na=False, na_values=[""])
    pw = pw[(pw["alpha"] == 0.05) & (pw["scenario"] != "S00_null")].assign(w=lambda d: d["w"].fillna("NA").astype(str).str.replace(".0", "", regex=False), svr=lambda d: d["svr"].fillna("NA"))
    pw_key = pw.groupby(["svr", "detector", "w", "reset", "calibration"])
    keyed = {(r.svr, r.detector, str(r.w), r.reset, r.calibration): r for r in s05.itertuples()}
    raw_sha = json.loads((BASE / "evidence/input_hashes.json").read_text())["069500.csv"] if (BASE / "evidence/input_hashes.json").exists() else None
    rows = []
    for r in reg.merge(summ[["experiment_id", "valid_days", "alarm_days_a05", "alarm_days_a20", "event_alarm_days_a20", "crit_a05", "null_valid"]], on="experiment_id", how="left").itertuples():
        k = (r.svr, r.detector, str(r.w).replace(".0", ""), r.reset, r.calibration)
        sz = keyed.get(k)
        syn = eff[(eff["child"] == "|".join([r.svr, r.detector, str(r.w).replace(".0", ""), r.reset])) & (eff["alpha"] == 0.05)]
        rows.append({
            "experiment_id": r.experiment_id, "parent_experiment_id": r.parent_experiment_id, "family": r.family,
            "changed_variable": r.changed_variable, "value_before": r.value_before, "value_after": r.value_after,
            "ofat_check": r.ofat_check, "fixed_vars_hash": r.fixed_vars_hash, "config_hash": r.config_hash,
            "input_data_hash": raw_sha, "model_hash": model_hash.get(r.svr), "residual_path_hash": resid_hash.get(r.svr),
            "change_point_rule": r.reset if str(r.reset).startswith("cp:") else "none",
            "reset_rule": r.reset, "calibration_id": r.calibration,
            "computable_days": r.valid_days, "observed_alarm_days_a05": r.alarm_days_a05, "observed_alarm_days_a20": r.alarm_days_a20,
            "holdout_false_alarm_a05": getattr(sz, "holdout_rate", None), "holdout_size_ok_cluster": getattr(sz, "size_ok_cluster", None),
            "synthetic_effect_labels_a05": ";".join(f"{a}:{b}" for a, b in syn.groupby("label").size().items()) if len(syn) else "NOT_IN_SYNTHETIC",
            "synthetic_median_delay_child": float(syn["child_delay_median"].median()) if len(syn) else None,
            "synthetic_max_detection_a05": float(pw_key.get_group(k)["detection_rate"].max()) if k in pw_key.groups else None,
            "synthetic_best_scenario_a05": pw_key.get_group(k).sort_values("detection_rate").iloc[-1]["scenario"] if k in pw_key.groups else None,
            "observed_verdict": "NULL_MODEL_INVALID_DESCRIPTIVE" if r.null_valid is False else ("DESCRIPTIVE" if r.null_valid else "NOT_APPLICABLE"),
            "evidence": "results/experiment_summary.csv; results/synthetic_effects.csv",
        })
    regdf = pd.DataFrame(rows)
    regdf.to_csv(BASE / "EXPERIMENT_REGISTRY.csv", index=False, float_format="%.10g", lineterminator="\n")

    # 정책·초기화 요약
    w(summ[summ["family"].isin(["BASE", "E2_window", "E3_statistic", "E6_train_window", "E7_refit_freq", "E8_change_response", "E9_refit_grace", "E10_adaptive_window", "E11_calibration", "X_interaction", "EXPLORATORY_EXTENSION"])], "cusum_policy_summary.csv")
    w(summ[summ["family"].isin(["BASE", "E1_time_split", "E5_cp_reset"])], "reset_comparison.csv")

    # 피처 카탈로그·스키마
    wide = pd.read_parquet(STORE / "ae_candidate_wide.parquet")
    red = pd.read_csv(RES / "ae_redundancy.csv").set_index("feature")
    cat = []
    for f, (grp, avail, dec, why) in FEATURE_META.items():
        cov = float(wide[f].notna().mean()) if f in wide else None
        r = red.loc[f] if f in red.index else None
        cat.append({"feature": f, "group": grp, "available_at": avail, "decision": dec, "reason": why, "coverage_2020_2025": cov,
                    "first_valid": str(wide.loc[wide[f].notna(), "date"].min().date()) if f in wide and wide[f].notna().any() else None,
                    "r2_from_others": None if r is None else r["r2_from_others"],
                    "max_abs_spearman": None if r is None else r["max_abs_spearman"], "most_similar": None if r is None else r["most_similar"],
                    "incremental_r2_future_rv20": None if r is None else r["incremental_r2_future_rv20_over_rv20"]})
    w(pd.DataFrame(cat), "feature_catalog.csv")
    schema = {"daily_cusum_features": {c: str(t) for c, t in led.dtypes.items()},
              "ae_candidate_wide": {c: str(t) for c, t in wide.dtypes.items()},
              "primary_key": ["ticker", "date", "experiment_id"], "rows": len(led), "experiments": int(led["experiment_id"].nunique()),
              "days": int(led["date"].nunique()), "status_codes": sorted(led["significance_status"].unique().tolist()),
              "pvalue_status_codes": sorted(led["pvalue_status"].unique().tolist())}
    (BASE / "FEATURE_SCHEMA.json").write_text(json.dumps(schema, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 데이터 산출물 목록 (Git 제외 파일의 해시·위치·재생성법)
    arts = []
    for p in sorted((ROOT / "outputs/t21").rglob("*")):
        if p.is_file() and p.suffix in (".parquet", ".npy", ".pkl", ".csv") and "pilot" not in p.parts and "n0" not in str(p):
            arts.append({"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p),
                         "git": "EXCLUDED (outputs/)", "regenerate": "outputs/t21/run_mc_chain_n1.sh → scripts/run_t21_calibrate.py → scripts/run_t21_pipeline.py"})
    w(pd.DataFrame(arts), "data_artifact_manifest.csv")

    # 릴리스 목록
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name != "RELEASE_MANIFEST.json")
    man = {"study_id": "t21_k200_cusum_controlled_12", "protocol": "12-lock-2", "built_on_commit": head,
           "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
           "excluded_local_artifacts": "results/data_artifact_manifest.csv"}
    (BASE / "RELEASE_MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("등록부", len(regdf), "행 · 카탈로그", len(cat), "· 로컬 산출물", len(arts), "· 릴리스 파일", len(files))


if __name__ == "__main__":
    main()
