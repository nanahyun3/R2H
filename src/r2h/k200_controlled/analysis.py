"""관측 단계 2 — 귀무 보정표를 관측 원시 통계량에 붙여 경보·p 값·상태 → 피처 원장 · 요약표 (계약 §6, §8, §9).

경보 판정은 이 R2H .venv (CPU float64) 에서 한다. 임계값은 ``outputs/t21/calib/null_calibration.pkl`` (백엔드 기록 포함).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from r2h.annual_expanding.diagnostics import arch_lm, ljung_box

from . import calib as K
from . import core as C
from . import nullcal as N
from .observed import Observed, event_mask, own_percentile

LAM = {"page_up": 2.0, "page_down": 0.5}
VALIDITY_STATS = ("mean_e2", "excess_kurtosis", "lb_e2_q10", "archlm5")


def year_diag(e: np.ndarray) -> dict[str, float]:
    x = np.asarray(e, float)
    x = x[np.isfinite(x)]
    if x.size < 30:
        return {k: np.nan for k in VALIDITY_STATS}
    return {
        "mean_e2": float(np.mean(x**2)),
        "excess_kurtosis": float(stats.kurtosis(x, fisher=True)),
        "lb_e2_q10": float(ljung_box(x**2, 10)[0]),
        "archlm5": float(arch_lm(x, 5)[0]),
    }


def null_validity(ob: Observed, hold_e: dict[str, np.ndarray]) -> pd.DataFrame:
    """파이프라인 × 연도: 관측 진단이 귀무 홀드아웃 중앙 99% 밖이면 위반. 하나라도 위반이면 그 파이프라인 NULL_MODEL_INVALID."""
    yr = ob.m.eval_dates.year.to_numpy()
    rows = []
    for pl, p in ob.paths.items():
        if pl not in hold_e:
            continue
        H = hold_e[pl]
        for y in sorted(set(yr)):
            msk = yr == y
            obs = year_diag(p.e[msk])
            null = pd.DataFrame([year_diag(H[i, msk]) for i in range(H.shape[0])])
            for s in VALIDITY_STATS:
                v = null[s].dropna().to_numpy()
                lo, hi = np.quantile(v, [0.005, 0.995])
                rows.append({"pipeline": pl, "year": int(y), "stat": s, "observed": obs[s], "null_q005": lo,
                             "null_q995": hi, "null_median": float(np.median(v)),
                             "outside": bool(obs[s] < lo or obs[s] > hi)})
    return pd.DataFrame(rows)


def key_of(row) -> tuple:
    return (row.svr, row.detector, str(row.w), row.reset)


def observed_alarms(ob: Observed, eid: str, row, crit) -> np.ndarray:
    """관측 경보 (rolling: T ≥ crit, page: 경보 후 재설정 경로)."""
    T = ob.raw[eid]["T"]
    if row.detector in ("rolling_cos", "raw_rolling_cos"):
        return np.nan_to_num(T, nan=-np.inf) >= crit
    e = ob.paths[row.svr].e
    rs = ob.resets[eid]
    if row.detector in LAM:
        return C.page_alarm(e, LAM[row.detector], crit, rs)[1]
    hu, hd = crit
    return C.page_alarm(e, 2.0, hu, rs)[1] | C.page_alarm(e, 0.5, hd, rs)[1]


def crit_for(cal: dict, row, alpha: float):
    if row.calibration != "garch_t_full_pipeline":
        return cal["alt"][row.calibration][alpha]
    return cal["res"][key_of(row)]["crit"][alpha]


def table_for(cal: dict, row) -> dict | None:
    if row.calibration != "garch_t_full_pipeline":
        return None
    return cal["res"][key_of(row)]["table"]


def build_ledger(ob: Observed, cal: dict, invalid_pipelines: set[str], source_hash: str) -> pd.DataFrame:
    """long-format 일별 원장: 실험 × 평가일. 비유의·결측도 상태 코드와 함께 전부 남긴다."""
    ed = ob.m.eval_dates
    n = len(ed)
    es = ob.m.eval_start
    r_eval = ob.m.r[es:]
    parts = []
    for row in ob.reg.itertuples(index=False):
        eid = row.experiment_id
        if eid not in ob.raw:
            continue
        T = ob.raw[eid]["T"]
        tab = table_for(cal, row)
        c05, c20 = crit_for(cal, row, 0.05), crit_for(cal, row, 0.20)
        a05 = observed_alarms(ob, eid, row, c05)
        a20 = observed_alarms(ob, eid, row, c20)
        is_page = row.detector.startswith("page")
        crit_scalar = (max(c05) if isinstance(c05, (tuple, list)) else c05)
        raw_p = N.tail_prob(T, tab["qtab"]) if tab is not None else np.full(n, np.nan)
        adj_p = N.bmax_prob(T, tab["bmax"]) if tab is not None else np.full(n, np.nan)
        pl = row.svr
        null_ok = pl == "NA" or pl not in invalid_pipelines
        valid = np.isfinite(T)
        since, count = C.days_since_reset(n, ob.resets[eid])
        p = ob.paths.get(pl)
        if is_page:
            sig = np.where(a05, "SIGNIFICANT", "NOT_SIGNIFICANT")
        else:
            sig = np.where(~valid, "WINDOW_NOT_AVAILABLE", np.where(a05, "SIGNIFICANT", "NOT_SIGNIFICANT"))
        if tab is None:
            pstat = np.where(valid, "P_VALUE_NOT_CALCULATED", "WINDOW_NOT_AVAILABLE")
        else:
            pstat = np.where(valid, "OK", "WINDOW_NOT_AVAILABLE")
        conf_p = np.where(null_ok, adj_p, np.nan)
        df = pd.DataFrame(
            {
                "ticker": "069500",
                "date": ed,
                "experiment_id": eid,
                "policy_id": pl,
                "detector_type": row.detector,
                "window_w": str(row.w),
                "reset_rule": row.reset,
                "calendar_year": ed.year,
                "feature_available_at": ed,  # t 종가 (모든 실시간 값)
                "information_cutoff": "close_t",
                "model_fit_id": p.fit_id if p is not None else -1,
                "return_log_pct": r_eval,
                "residual_std": p.e if p is not None else np.nan,
                "predicted_variance": p.vhat if p is not None else np.nan,
                "cusum_raw_T": T,
                "cusum_upper_state": ob.raw[eid].get("S_up", T if row.detector == "page_up" else np.nan),
                "cusum_lower_state": ob.raw[eid].get("S_dn", T if row.detector == "page_down" else np.nan),
                "cusum_critical_value_a05": crit_scalar,
                "cusum_T_over_critical_a05": T / crit_scalar if np.isfinite(crit_scalar) and crit_scalar > 0 else np.nan,
                "cusum_tail_probability": raw_p,
                "cusum_adjusted_pvalue": adj_p,
                "confirmatory_p": conf_p,
                "cusum_alarm_a05": a05,
                "cusum_alarm_a20": a20,
                "cusum_statistic_valid": valid,
                "cusum_null_valid": null_ok,
                "cusum_calibration_id": row.calibration,
                "significance_status": np.where(null_ok, sig, np.where(valid, "NULL_MODEL_INVALID", sig)),
                "pvalue_status": pstat,
                "days_since_reset": since,
                "reset_count": count,
                "page_state_code": ob.raw[eid].get("code", np.full(n, -1)),
                "source_hash": source_hash,
            }
        )
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def episodes_count(alarm: np.ndarray, gap: int = 5) -> int:
    from r2h.svrgarch_etf.rolling import episodes

    return len(episodes(alarm, gap=gap))


def experiment_summary(ob: Observed, ledger: pd.DataFrame, raw_sum: pd.DataFrame) -> pd.DataFrame:
    n = len(ob.m.eval_dates)
    evm = event_mask(ob.events, n)
    yr = ob.m.eval_dates.year.to_numpy()
    rows = []
    for eid, g in ledger.groupby("experiment_id", sort=False):
        a05 = g["cusum_alarm_a05"].to_numpy()
        a20 = g["cusum_alarm_a20"].to_numpy()
        rows.append(
            {
                "experiment_id": eid,
                "alarm_days_a05": int(a05.sum()),
                "alarm_days_a20": int(a20.sum()),
                "episodes_a05": episodes_count(a05),
                "episodes_a20": episodes_count(a20),
                "alarm_days_a05_2020": int(a05[yr == 2020].sum()),
                "alarm_days_a05_2021_2025": int(a05[yr >= 2021].sum()),
                "event_alarm_days_a05": int((a05 & evm).sum()),
                "event_alarm_days_a20": int((a20 & evm).sum()),
                "crit_a05": g["cusum_critical_value_a05"].iloc[0],
                "min_adjusted_p": float(np.nanmin(g["cusum_adjusted_pvalue"])) if g["cusum_adjusted_pvalue"].notna().any() else np.nan,
                "null_valid": bool(g["cusum_null_valid"].iloc[0]),
            }
        )
    out = ob.reg.merge(raw_sum, on="experiment_id", how="left").merge(pd.DataFrame(rows), on="experiment_id", how="left")
    return out
