"""피처 저장소 (명세 §3.1·§3.2) — 원장 필드 보강 + 필수 데이터셋 8종 + 최소 필드 포함 검사.

로컬 ``outputs/t21/feature_store_n1/`` (Git 제외)에 Parquet 로 쓴다. 해당 없는 필드는 NA 와 사유를 함께 남긴다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import changepoints as CP
from . import core as C
from .observed import Observed
from .policies import ADAPTIVE_RULE, PRIMARY_RULE

REQUIRED_FIELDS = (
    "ticker", "date", "experiment_id", "policy_id", "detector_type", "window_w", "segment_id", "calendar_year",
    "feature_available_at", "information_cutoff", "model_fit_id", "model_fit_at", "model_training_start", "model_training_end",
    "return_log_pct", "return_abs", "return_sq", "realized_variance", "realized_volatility", "observed_variance_proxy",
    "predicted_variance", "predicted_volatility", "residual", "standardized_residual", "standardized_residual_sq",
    "cusum_raw_T", "cusum_normalized_T", "cusum_signed_direction", "cusum_upper_state", "cusum_lower_state",
    "cusum_critical_value", "cusum_T_over_critical", "cusum_tail_probability", "cusum_test_pvalue", "cusum_adjusted_pvalue",
    "cusum_alarm_flag", "cusum_statistic_valid", "cusum_null_valid", "cusum_calibration_id",
    "change_trigger_type", "change_score", "change_score_percentile", "change_detected_at", "reset_applied_at",
    "days_since_reset", "reset_count", "reset_reason", "svr_refit_at", "days_since_refit", "refit_reason",
    "significance_status", "computation_status", "model_validity_status", "feature_eligibility", "missing_reason",
    "numerical_precision", "source_hash",
)


def _fit_tables(ob: Observed) -> dict[str, pd.DataFrame]:
    """파이프라인별 평가일 → 적합 정보 (적합 시점·학습 구간·재적합 사유)."""
    out = {}
    m = ob.m
    for pl, p in ob.paths.items():
        sched = set(C.scheduled_positions(m, "annual"))
        fits = pd.DataFrame(p.fits)
        n = len(p.e)
        start = np.asarray(p.refit_pos)[p.fit_id]
        reason = []
        for k, s in enumerate(p.refit_pos):
            if s == 0:
                reason.append("INITIAL_FIT")
            elif pl in ("refit63", "refit21") or (s in sched and not pl.startswith(("refitV20", "adaptive"))):
                reason.append("SCHEDULED")
            elif s in sched:
                reason.append("SCHEDULED_ANNUAL")
            else:
                reason.append("CHANGE_POINT_TRIGGER_ADAPTIVE" if pl == "adaptiveV20" else "CHANGE_POINT_TRIGGER")
        fits["refit_reason"] = reason
        f = fits.set_index("fit_k").loc[p.fit_id].reset_index(drop=True)
        out[pl] = pd.DataFrame({
            "model_fit_at": pd.to_datetime(f["fit_at"]).to_numpy(), "model_training_start": pd.to_datetime(f["train_start"]).to_numpy(),
            "model_training_end": pd.to_datetime(f["train_end"]).to_numpy(), "svr_refit_at": pd.to_datetime(f["fit_at"]).to_numpy(),
            "days_since_refit": np.arange(n) - start, "refit_reason": f["refit_reason"].to_numpy(),
            "svr_C": f["C"].to_numpy(), "svr_gamma2": f["gamma2"].to_numpy(), "svr_eps": f["eps"].to_numpy(),
            "history_truncated": f["history_truncated"].to_numpy(),
        })
    return out


def _cp_strength(ob: Observed) -> dict[tuple[str, float], tuple[np.ndarray, np.ndarray]]:
    """(규칙, q) → (평가 구간 임계, 평가 구간 백분위)."""
    es = ob.m.eval_start
    out = {}
    for rid in CP.rule_ids():
        s = ob.scores[f"{rid}_strength"].to_numpy(float)
        thr, pct = CP.expanding_threshold(s, CP.QUANTILES)
        for q in CP.QUANTILES:
            out[(rid, q)] = (thr[q][es:], pct[es:])
    return out


def enrich_ledger(ob: Observed, ledger: pd.DataFrame) -> pd.DataFrame:
    """§3.1 최소 필드를 원장에 붙인다 (NA + 사유)."""
    ed = ob.m.eval_dates
    n = len(ed)
    es = ob.m.eval_start
    r_all = pd.Series(ob.m.r, index=ob.m.dates)
    rv20 = r_all.rolling(20).std(ddof=1).iloc[es:].to_numpy()
    proxy5 = (r_all**2).rolling(5).mean().iloc[es:].to_numpy()
    fits = _fit_tables(ob)
    strength = {rid: ob.scores[f"{rid}_strength"].to_numpy(float)[es:] for rid in CP.rule_ids()}
    pctl = _cp_strength(ob)
    parts = []
    for eid, g in ledger.groupby("experiment_id", sort=False):
        row = ob.reg.set_index("experiment_id").loc[eid]
        d = g.reset_index(drop=True).copy()
        r = d["return_log_pct"].to_numpy()
        d["return_abs"] = np.abs(r)
        d["return_sq"] = r**2
        d["realized_variance"] = r**2
        d["realized_volatility"] = rv20
        d["observed_variance_proxy"] = proxy5
        d["predicted_volatility"] = np.sqrt(np.where(d["predicted_variance"] > 0, d["predicted_variance"], np.nan))
        d["residual"] = r - 0.0  # 평균 0 가정 (정책 A 는 평균을 모형화하지 않음)
        d["standardized_residual"] = d["residual_std"]
        d["standardized_residual_sq"] = d["residual_std"] ** 2
        crit = d["cusum_critical_value_a05"]
        d["cusum_critical_value"] = crit
        d["cusum_T_over_critical"] = d["cusum_T_over_critical_a05"]
        d["cusum_normalized_T"] = d["cusum_T_over_critical_a05"]
        d["cusum_test_pvalue"] = d["confirmatory_p"]
        d["cusum_alarm_flag"] = d["cusum_alarm_a05"]
        # 방향: 이동 CoS 는 창 후반부 − 전반부 평균 e², Page 양방향은 우세한 쪽, 단측은 고정
        det = row["detector"]
        if det in ("rolling_cos", "raw_rolling_cos"):
            x = (d["residual_std"] if det == "rolling_cos" else pd.Series(r)) ** 2
            w = int(row["w"])
            h = w // 2
            late = x.rolling(h, min_periods=max(1, int(0.9 * h))).mean()
            early = late.shift(h)
            d["cusum_signed_direction"] = np.sign(late - early)
        elif det.startswith("page_two"):
            d["cusum_signed_direction"] = np.where(d["cusum_upper_state"].fillna(0) >= d["cusum_lower_state"].fillna(0), 1.0, -1.0)
        elif det.startswith("page_up"):
            d["cusum_signed_direction"] = 1.0
        elif det.startswith("page_down"):
            d["cusum_signed_direction"] = -1.0
        else:
            d["cusum_signed_direction"] = np.nan
        d["segment_id"] = d["reset_count"]
        # 초기화·변화점
        rs = sorted(set(ob.resets[eid]))
        reset_rule = row["reset"]
        seg_start = np.zeros(n, dtype=np.int64)
        for p_ in rs:
            seg_start[p_:] = p_
        d["reset_applied_at"] = np.where(d["reset_count"] > 0, ed[seg_start].to_numpy(), np.datetime64("NaT"))
        d["reset_reason"] = np.where(d["reset_count"] > 0, reset_rule, "SERIES_START")
        if str(reset_rule).startswith("cp:"):
            _, rid, q, _g = reset_rule.split(":")
            trig = np.clip(seg_start - 1, 0, n - 1)  # 효과일 t+1 의 확정일 t
            has = d["reset_count"].to_numpy() > 0
            d["change_trigger_type"] = "cp_" + rid
            d["change_detected_at"] = np.where(has, ed[trig].to_numpy(), np.datetime64("NaT"))
            d["change_score"] = np.where(has, strength[rid][trig], np.nan)
            d["change_score_percentile"] = np.where(has, pctl[(rid, float(q))][1][trig], np.nan)
        else:
            d["change_trigger_type"] = "NOT_APPLICABLE:calendar_or_none" if reset_rule not in ("none", "NA") else "NOT_APPLICABLE:no_reset"
            d["change_detected_at"] = np.datetime64("NaT")
            d["change_score"] = np.nan
            d["change_score_percentile"] = np.nan
        # SVR 적합
        pl = row["svr"]
        if pl in fits:
            for c in fits[pl].columns:
                d[c] = fits[pl][c].to_numpy()
        else:
            for c in ("model_fit_at", "model_training_start", "model_training_end", "svr_refit_at"):
                d[c] = np.datetime64("NaT")
            d["days_since_refit"] = -1
            d["refit_reason"] = "NOT_APPLICABLE:raw_return_detector"
        valid = d["cusum_statistic_valid"].to_numpy()
        d["computation_status"] = np.where(valid, "OK", np.where(d["significance_status"] == "INSUFFICIENT_HISTORY", "INSUFFICIENT_HISTORY", "WINDOW_NOT_AVAILABLE"))
        d["model_validity_status"] = np.where(d["cusum_null_valid"], "NULL_VALID_OR_NOT_APPLICABLE", "NULL_MODEL_INVALID")
        d["feature_eligibility"] = np.where(valid, "ELIGIBLE_REALTIME_CONTINUOUS", "NOT_ELIGIBLE_MISSING")
        d["missing_reason"] = np.where(valid, "", d["computation_status"])
        d["numerical_precision"] = "float64_cpu_numpy"
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def side_datasets(ob: Observed, ledger: pd.DataFrame, summ: pd.DataFrame, syn: pd.DataFrame | None,
                  catalog: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    ed = ob.m.eval_dates
    es = ob.m.eval_start
    r_all = pd.Series(ob.m.r, index=ob.m.dates)
    mk = pd.DataFrame({"ticker": "069500", "date": ed, "close": ob.m.close[es:], "return_log_pct": ob.m.r[es:]})
    mk["return_abs"] = mk["return_log_pct"].abs()
    mk["return_sq"] = mk["return_log_pct"] ** 2
    for L in (5, 20, 60, 120):
        mk[f"rv{L}"] = r_all.rolling(L).std(ddof=1).iloc[es:].to_numpy()
    mk["feature_available_at"] = ed
    svr = []
    ft = _fit_tables(ob)
    for pl, p in ob.paths.items():
        f = ft[pl]
        svr.append(pd.DataFrame({"ticker": "069500", "date": ed, "policy_id": pl, "predicted_variance": p.vhat,
                                 "predicted_volatility": np.sqrt(np.where(p.vhat > 0, p.vhat, np.nan)),
                                 "standardized_residual": p.e, "standardized_residual_sq": p.e**2, "model_fit_id": p.fit_id,
                                 "feature_available_at": ed}).join(f))
    cp = ob.scores.iloc[es:].reset_index(drop=True).copy()
    pctl = _cp_strength(ob)
    for (rid, q), (thr, pc) in pctl.items():
        cp[f"{rid}_thr_q{q}"] = thr
        cp[f"{rid}_pctile"] = pc
    cp.insert(0, "date", ed)
    cp.insert(0, "ticker", "069500")
    trig = ob.trig[ob.trig["in_eval"]].copy()
    trig["effect_date"] = ed[trig["effect_rel"].astype(int).to_numpy()]
    trig["detected_date"] = ed[np.clip(trig["effect_rel"].astype(int).to_numpy() - 1, 0, len(ed) - 1)]
    resets = []
    for eid, rs in ob.resets.items():
        rule = ob.reg.set_index("experiment_id").loc[eid, "reset"]
        for p_ in rs:
            resets.append({"experiment_id": eid, "reset_applied_at": ed[p_], "reset_rule": rule,
                           "reset_reason": "CHANGE_POINT" if str(rule).startswith("cp:") else "CALENDAR"})
    elig = ledger[["ticker", "date", "experiment_id", "feature_eligibility", "missing_reason", "computation_status",
                   "model_validity_status", "significance_status", "pvalue_status", "numerical_precision"]]
    out = {"daily_market_features": mk, "daily_svr_predictions": pd.concat(svr, ignore_index=True),
           "daily_change_point_features": cp, "daily_change_point_triggers": trig.reset_index(drop=True),
           "daily_reset_events": pd.DataFrame(resets), "daily_feature_eligibility": elig, "experiment_metrics": summ}
    if syn is not None:
        out["synthetic_validation"] = syn
    if catalog is not None:
        out["autoencoder_feature_catalog"] = catalog
    out["_primary_rules"] = pd.DataFrame([{"use": "E8/E9 refit + reset", "rule": PRIMARY_RULE}, {"use": "E10 adaptive", "rule": ADAPTIVE_RULE}]).astype(str)
    return out


def field_coverage(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    cols = set().union(*[set(d.columns) for d in datasets.values()])
    return pd.DataFrame([{"field": f, "present": f in cols,
                          "datasets": ";".join(sorted(k for k, d in datasets.items() if f in d.columns))} for f in REQUIRED_FIELDS])
