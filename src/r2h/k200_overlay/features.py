"""증분 정보 (12B-lock-1 incremental_information) — 원시 변동성으로 설명되지 않는 CUSUM 정보.

목표 = ln SD(r_{t+1..t+20}) (미래, POSTHOC 목표). 기준 = ln 연환산변동성 5·20·60·120 + ln 예측변동성 B1.
연도 제외 교차검증 (시험연도 2021..2025, 시험연도 양쪽 20일 엠바고), 공통 유효일만. 서술용 (목표가 겹친다).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASE_COLS = ("annualized_vol_5", "annualized_vol_20", "annualized_vol_60", "annualized_vol_120", "predicted_vol_annualized_B1")
TEST_YEARS = (2021, 2022, 2023, 2024, 2025)


def future_target(r: np.ndarray, h: int = 20) -> np.ndarray:
    """ln SD(r_{t+1..t+h}, ddof=1). 끝 h 일은 NaN."""
    s = pd.Series(r).rolling(h).std(ddof=1).shift(-h).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(s)


def base_matrix(master: pd.DataFrame) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.column_stack([np.log(master[c].to_numpy(float)) for c in BASE_COLS])


def _ols_pred(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(Xtr)), Xtr])
    beta, *_ = np.linalg.lstsq(A, ytr, rcond=None)
    return np.column_stack([np.ones(len(Xte)), Xte]) @ beta


def _r2(y: np.ndarray, p: np.ndarray) -> float:
    ss = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / ss) if ss > 0 else np.nan


def loyo_gain(y: np.ndarray, B: np.ndarray, f: np.ndarray, years: np.ndarray, exclude_2020: bool, embargo: int = 20) -> dict:
    """후보 f 를 더한 모형 vs 기준 모형의 시험연도 R² 차이 (연도별 + 합동)."""
    ok = np.isfinite(y) & np.isfinite(B).all(axis=1) & np.isfinite(f)
    pos = np.arange(y.size)
    res = {"n_common": int(ok.sum())}
    py_b, py_f, yy = [], [], []
    for ty in TEST_YEARS:
        te = ok & (years == ty)
        if te.sum() < 40:
            res[f"gain_{ty}"] = np.nan
            continue
        lo, hi = pos[te].min(), pos[te].max()
        tr = ok & (years != ty) & ((pos < lo - embargo) | (pos > hi + embargo))
        if exclude_2020:
            tr &= years != 2020
        if tr.sum() < 100:
            res[f"gain_{ty}"] = np.nan
            continue
        pb = _ols_pred(B[tr], y[tr], B[te])
        pf = _ols_pred(np.column_stack([B[tr], f[tr]]), y[tr], np.column_stack([B[te], f[te]]))
        res[f"gain_{ty}"] = _r2(y[te], pf) - _r2(y[te], pb)
        py_b.append(pb)
        py_f.append(pf)
        yy.append(y[te])
    if yy:
        Y, PB, PF = np.concatenate(yy), np.concatenate(py_b), np.concatenate(py_f)
        res["r2_base_pooled"] = _r2(Y, PB)
        res["r2_with_pooled"] = _r2(Y, PF)
        res["gain_pooled"] = res["r2_with_pooled"] - res["r2_base_pooled"]
        # 보조 지표: 분모와 무관한 표본외 상대 MSE 개선 1 − MSE(기준+후보)/MSE(기준)
        res["rel_mse_gain_pooled"] = float(1 - np.mean((Y - PF) ** 2) / np.mean((Y - PB) ** 2))
        g = np.array([res[f"gain_{t}"] for t in TEST_YEARS], float)
        res["years_positive"] = int(np.sum(g > 0))
        res["years_evaluated"] = int(np.isfinite(g).sum())
        res["n_test_pooled"] = int(Y.size)
    ev = res.get("years_evaluated", 0)
    res["coverage_status"] = "OK" if (ev == len(TEST_YEARS) and res["n_common"] >= 750) else "LIMITED_COVERAGE"
    return res


def common_day_variant(y: np.ndarray, B: np.ndarray, feats: dict[str, np.ndarray], years: np.ndarray) -> pd.DataFrame:
    """대표 후보 전체가 유효한 날의 교집합에서 같은 평가 (공통 유효일 비교, G9)."""
    ok = np.isfinite(y) & np.isfinite(B).all(axis=1)
    for f in feats.values():
        ok &= np.isfinite(f)
    rows = []
    for name, f in feats.items():
        for ex in (False, True):
            ff = np.where(ok, f, np.nan)
            rows.append({"feature": name, "exclude_2020_train": ex, **loyo_gain(y, B, ff, years, ex)})
    return pd.DataFrame(rows)


def run_all(aligned: pd.DataFrame, master: pd.DataFrame, extra: dict[str, np.ndarray]) -> pd.DataFrame:
    """463 정책 (과거 전용 백분위 · 대표군은 원시 T 도) + 추가 시계열 (X1w 등) 의 증분 정보."""
    y = future_target(master["daily_log_return_pct"].to_numpy(float))
    B = base_matrix(master)
    years = master["date"].dt.year.to_numpy()
    rows = []
    for eid, g in aligned.groupby("experiment_id", sort=True):
        g = g.sort_values("date")
        meta = {"experiment_id": eid, "family": g["family"].iloc[0], "detector_type": g["detector_type"].iloc[0],
                "window_w": g["window_w"].iloc[0], "policy_id": g["policy_id"].iloc[0], "reset_rule": g["reset_rule"].iloc[0]}
        for scale, col in (("past_pct", "T_past_pct"), ("raw", "cusum_raw_T")):
            f = g[col].to_numpy(float)
            for ex in (False, True):
                rows.append({**meta, "scale": scale, "exclude_2020_train": ex, **loyo_gain(y, B, f, years, ex)})
    for name, f in extra.items():
        for ex in (False, True):
            rows.append({"experiment_id": name, "family": "12B_EXTRA", "detector_type": name, "window_w": "NA", "policy_id": "B1",
                         "reset_rule": "none", "scale": "raw" if name.endswith("_raw") else "past_pct", "exclude_2020_train": ex,
                         **loyo_gain(y, B, f, years, ex)})
    out = pd.DataFrame(rows)
    out["label"] = "DESCRIPTIVE_OVERLAPPING_TARGET"
    return out
