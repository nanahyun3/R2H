"""사전 계약 W1의 검출기·적합 포함 합성 실험.

T12의 난수 파생, GARCH DGP, SVR 적합, CUSUM 통계량을 직접 호출한다.
새 코드는 연간 최대값 보정·선택/평가 분리·알려진 변화의 event 지표만 담당한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.annual_expanding.config import rng_for
from r2h.annual_expanding.fit import baseline_variance, fit_annual, forecast_year, standardize
from r2h.annual_expanding.synthetic import DETECTOR_DGPS, Scenario, simulate_pipeline_returns, wilson
from r2h.svrgarch_etf.rolling import episodes, rolling_cusum


def load_cfg(root: Path) -> dict:
    """동결 JSON 설정만 읽는다. notebook마다 파라미터를 다시 정의하지 않는다."""
    return json.loads((root / "configs/t13_window_study_v1.json").read_text(encoding="utf-8"))


def _rng(cfg: dict, *key: object) -> np.random.Generator:
    return rng_for(cfg["study_id"], cfg["seed"], *key)


def _garch_alternative(cfg: dict, name: str, rng: np.random.Generator) -> Scenario:
    """원본 GARCH 귀무 경로에 사전 약정한 분산 배율만 적용한다."""
    nh, n, k = cfg["n_history_synthetic"], cfg["n_year_synthetic"], cfg["break_zero_based"]
    base = DETECTOR_DGPS["stable_garch_clustering"][0](rng, nh, n)
    test = base.test.copy()
    if name == "garch_up_x2":
        test[k:] *= np.sqrt(2.0)
    elif name == "garch_down_x0.5":
        test[k:] *= np.sqrt(0.5)
    elif name == "garch_transient_up_x2_40d":
        test[k : k + 40] *= np.sqrt(2.0)
    elif name == "garch_gradual_up_1to2":
        test[k:] *= np.sqrt(np.linspace(1.0, 2.0, n - k))
    else:
        raise ValueError(name)
    return Scenario(base.history, test, k)


def _stats(e: np.ndarray, cfg: dict) -> dict[int, np.ndarray]:
    """원 T12 이동창 함수로만 계산하고 모든 w에 같은 공통 시작일을 적용한다."""
    return {w: rolling_cusum(e, w) for w in cfg["windows_primary"]}


def _max_common(stat: np.ndarray, cfg: dict) -> float:
    common = stat[cfg["common_start_zero_based"] :]
    return float(np.nanmax(common)) if np.isfinite(common).any() else float("nan")


def _assess(stat: np.ndarray, crit: float, cfg: dict, break_pos: int | None = None) -> dict:
    """H0의 연중 경보 또는 H1의 사후 60거래일 첫 경보를 구별한다."""
    n = len(stat)
    ok = np.arange(n) >= cfg["common_start_zero_based"]
    valid = ok & np.isfinite(stat)
    alarm = valid & (stat >= crit)
    epsi = episodes(alarm, gap=cfg["episode_gap_non_alarm_days"])
    answer = {
        "n_valid_common": int(valid.sum()),
        "alarm_days": int(alarm.sum()),
        "episodes": len(epsi),
        "any_alarm": int(bool(epsi)),
        "delay": np.nan,
        "detected_60d": np.nan,
    }
    if break_pos is not None:
        horizon_end = min(n, break_pos + cfg["event_horizon_trading_days"])
        post = np.flatnonzero(alarm & (np.arange(n) >= break_pos) & (np.arange(n) < horizon_end))
        answer["detected_60d"] = int(post.size > 0)
        if post.size:
            answer["delay"] = int(post[0] - break_pos)
    return answer


def _summary(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """반복별 경보·검출을 Wilson 구간과 조건부 지연으로 요약한다."""
    rows: list[dict] = []
    for key, group in df.groupby(keys, sort=True, dropna=False):
        vals = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, vals, strict=True))
        n = len(group)
        k = int(group.any_alarm.sum())
        lo, hi = wilson(k, n)
        row.update(
            R=n,
            any_alarm=k / n,
            any_alarm_ci_low=lo,
            any_alarm_ci_high=hi,
            mean_episodes=float(group.episodes.mean()),
            n_not_estimable=int(group.n_valid_common.lt(100).sum()),
        )
        if group.detected_60d.notna().all():
            det = int(group.detected_60d.sum())
            dlo, dhi = wilson(det, n)
            delay = group.delay.dropna()
            row.update(
                detected_60d=det / n,
                detected_ci_low=dlo,
                detected_ci_high=dhi,
                n_detected=det,
                median_delay=float(delay.median()) if len(delay) else np.nan,
                q90_delay=float(delay.quantile(0.9)) if len(delay) else np.nan,
            )
        rows.append(row)
    return pd.DataFrame(rows)


def detector_experiment(cfg: dict, out: Path, *, smoke: bool = False) -> dict[str, pd.DataFrame]:
    """세 H0 보정/평가 및 네 GARCH H1을 독립 난수열로 full 실행한다."""
    out.mkdir(parents=True, exist_ok=True)
    nh, n = cfg["n_history_synthetic"], cfg["n_year_synthetic"]
    rcal = 8 if smoke else cfg["r_detector_cal_per_null"]
    reval = 8 if smoke else cfg["r_detector_eval_per_null"]
    rh1 = 8 if smoke else cfg["r_detector_h1_per_scenario"]
    cal_rows: list[dict] = []
    for name in cfg["null_dgps_detector"]:
        dgp = DETECTOR_DGPS[name][0]
        for rep in range(rcal):
            sc = dgp(_rng(cfg, "detector", "cal", name, rep), nh, n)
            for w, stat in _stats(sc.test, cfg).items():
                cal_rows.append({"dgp": name, "rep": rep, "w": w, "max_T": _max_common(stat, cfg)})
    cal = pd.DataFrame(cal_rows)
    q = cal.groupby(["dgp", "w"]).max_T.quantile(cfg["annual_max_quantile"]).unstack("dgp")
    thresholds = q.max(axis=1).rename("critical_annual_max").reset_index()
    thresholds["calibration_rule"] = "max_of_three_H0_q95_annual_max_common_days"
    crit = thresholds.set_index("w").critical_annual_max.to_dict()

    rows: list[dict] = []
    for name in cfg["null_dgps_detector"]:
        dgp = DETECTOR_DGPS[name][0]
        for rep in range(reval):
            sc = dgp(_rng(cfg, "detector", "eval", name, rep), nh, n)
            for w, stat in _stats(sc.test, cfg).items():
                rows.append({"stage": "H0", "dgp": name, "rep": rep, "w": w, **_assess(stat, crit[w], cfg)})
    for name in cfg["h1_dgps_detector"]:
        for rep in range(rh1):
            sc = _garch_alternative(cfg, name, _rng(cfg, "detector", "h1", name, rep))
            for w, stat in _stats(sc.test, cfg).items():
                rows.append(
                    {
                        "stage": "H1",
                        "dgp": name,
                        "rep": rep,
                        "w": w,
                        **_assess(stat, crit[w], cfg, sc.break_pos),
                    }
                )
    eval_df = pd.DataFrame(rows)
    summary = _summary(eval_df, ["stage", "dgp", "w"])
    files = {
        "detector_cal_max.csv": cal,
        "detector_thresholds.csv": thresholds,
        "detector_repetitions.csv": eval_df,
        "detector_summary.csv": summary,
    }
    for name, frame in files.items():
        frame.to_csv(out / name, index=False, float_format="%.10g")
    return files


def _pipeline_residuals(
    cfg: dict, kind: str, rep: int, stage: str
) -> tuple[dict[str, np.ndarray], int | None]:
    """한 모의에서 SVR을 한 번 적합하고 A/B/base의 검정연도 잔차를 만든다."""
    nh, n = cfg["n_history_synthetic"], cfg["n_year_synthetic"]
    r, break_pos = simulate_pipeline_returns(kind, _rng(cfg, "pipeline", stage, kind, rep), nh, n)
    history, test = r[:nh], r[nh:]
    fit = fit_annual(history, round(0.7 * nh))
    all_r = pd.Series(r)
    base_var = baseline_variance(all_r, 60, 40).to_numpy(float)[nh:]
    residuals = {
        "A": standardize(test, forecast_year(fit.fit, history, test, "A")),
        "B": standardize(test, forecast_year(fit.fit, history, test, "B")),
        "base": standardize(test, base_var),
    }
    return residuals, break_pos


def pipeline_experiment(cfg: dict, out: Path, *, smoke: bool = False) -> dict[str, pd.DataFrame]:
    """원 T12 27-grid 적합을 포함해 정책별 연중 max-T 임계값을 보정·평가한다."""
    out.mkdir(parents=True, exist_ok=True)
    rc = 2 if smoke else cfg["r_pipeline_cal"]
    re = 2 if smoke else cfg["r_pipeline_eval"]
    rh = 2 if smoke else cfg["r_pipeline_h1"]
    h0, h1 = cfg["null_dgp_pipeline"], cfg["h1_dgp_pipeline"]
    cal_rows: list[dict] = []
    for rep in range(rc):
        residuals, _ = _pipeline_residuals(cfg, h0, rep, "cal")
        for policy, e in residuals.items():
            for w, stat in _stats(e, cfg).items():
                cal_rows.append({"policy": policy, "rep": rep, "w": w, "max_T": _max_common(stat, cfg)})
    cal = pd.DataFrame(cal_rows)
    thresholds = (
        cal.groupby(["policy", "w"])
        .max_T.quantile(cfg["annual_max_quantile"])
        .rename("critical_annual_max")
        .reset_index()
    )
    thresholds["calibration_rule"] = "pipeline_garch_H0_q95_annual_max_common_days"
    crit = thresholds.set_index(["policy", "w"]).critical_annual_max.to_dict()

    rows: list[dict] = []
    for stage, kind, reps in (("H0", h0, re), ("H1", h1, rh)):
        for rep in range(reps):
            residuals, break_pos = _pipeline_residuals(cfg, kind, rep, stage)
            for policy, e in residuals.items():
                for w, stat in _stats(e, cfg).items():
                    rows.append(
                        {
                            "stage": stage,
                            "dgp": kind,
                            "policy": policy,
                            "rep": rep,
                            "w": w,
                            **_assess(stat, crit[policy, w], cfg, break_pos),
                        }
                    )
    eval_df = pd.DataFrame(rows)
    summary = _summary(eval_df, ["stage", "dgp", "policy", "w"])
    files = {
        "pipeline_cal_max.csv": cal,
        "pipeline_thresholds.csv": thresholds,
        "pipeline_repetitions.csv": eval_df,
        "pipeline_summary.csv": summary,
    }
    for name, frame in files.items():
        frame.to_csv(out / name, index=False, float_format="%.10g")
    return files


def select_windows(cfg: dict, detector: pd.DataFrame, pipeline: pd.DataFrame) -> pd.DataFrame:
    """W1 사전 적격성→파레토를 실제 ETF 결과와 무관하게 적용한다."""
    rows: list[dict] = []
    for w in cfg["windows_primary"]:
        dn = detector.query("stage == 'H0' and w == @w")
        dh = detector.query("stage == 'H1' and w == @w").set_index("dgp")
        pn = pipeline.query("stage == 'H0' and policy == 'A' and w == @w").iloc[0]
        ph = pipeline.query("stage == 'H1' and policy == 'A' and w == @w").iloc[0]
        important = dh.loc[["garch_up_x2", "garch_down_x0.5"]]
        dsize = bool(
            (
                dn.R.ge(cfg["r_detector_eval_per_null"])
                & dn.any_alarm_ci_high.le(cfg["primary_any_alarm_budget"])
                & dn.n_not_estimable.eq(0)
            ).all()
        )
        dpower = bool(
            (
                important.detected_ci_low.ge(cfg["min_h1_wilson_lower"])
                & important.n_detected.ge(cfg["min_detected_for_delay"])
                & important.median_delay.le(cfg["max_conditional_median_delay"])
                & important.q90_delay.le(cfg["max_conditional_q90_delay_detector"])
            ).all()
        )
        psize = bool(
            pn.R >= cfg["r_pipeline_eval"]
            and pn.any_alarm_ci_high <= cfg["primary_any_alarm_budget"]
            and pn.n_not_estimable == 0
        )
        ppower = bool(
            ph.R >= cfg["r_pipeline_h1"]
            and ph.detected_ci_low >= cfg["min_h1_wilson_lower"]
            and ph.n_detected >= cfg["min_detected_for_delay"]
            and ph.median_delay <= cfg["max_conditional_median_delay"]
            and ph.n_not_estimable == 0
        )
        insufficient = bool(
            dn.R.lt(cfg["r_detector_eval_per_null"]).any()
            or dn.n_not_estimable.gt(0).any()
            or pn.R < cfg["r_pipeline_eval"]
            or pn.n_not_estimable > 0
            or ph.R < cfg["r_pipeline_h1"]
            or ph.n_not_estimable > 0
        )
        reasons = [
            name
            for name, ok in (
                ("검출기 귀무 상한", dsize),
                ("검출기 검출/지연", dpower),
                ("적합 포함 귀무 상한", psize),
                ("적합 포함 검출/지연", ppower),
            )
            if not ok
        ]
        rows.append(
            {
                "w": w,
                "detector_size_ok": dsize,
                "detector_power_delay_ok": dpower,
                "pipeline_A_size_ok": psize,
                "pipeline_A_power_delay_ok": ppower,
                "eligible": not reasons,
                "insufficient_precision": insufficient,
                "failure_reason": "; ".join(reasons),
                "pipeline_A_power_lower": ph.detected_ci_low,
                "detector_min_power_lower": float(important.detected_ci_low.min()),
                "pipeline_A_median_delay": ph.median_delay,
            }
        )
    result = pd.DataFrame(rows)
    result["pareto"] = False
    eligible = result[result.eligible]
    for idx, row in eligible.iterrows():
        dominated = False
        for _, other in eligible.iterrows():
            better_or_equal = (
                other.pipeline_A_power_lower >= row.pipeline_A_power_lower
                and other.detector_min_power_lower >= row.detector_min_power_lower
                and other.pipeline_A_median_delay <= row.pipeline_A_median_delay
            )
            strictly = (
                other.pipeline_A_power_lower > row.pipeline_A_power_lower
                or other.detector_min_power_lower > row.detector_min_power_lower
                or other.pipeline_A_median_delay < row.pipeline_A_median_delay
            )
            dominated |= bool(better_or_equal and strictly)
        result.loc[idx, "pareto"] = not dominated
    result["pareto"] = result.pareto.astype(bool)
    n_pareto = int(result.pareto.sum())
    result["decision"] = np.where(
        ~result.eligible,
        np.where(result.insufficient_precision, "검증 불충분", "비적격"),
        np.where(result.pareto, "조건부 최적 후보" if n_pareto == 1 else "복수 후보", "적격·파레토 지배"),
    )
    return result
