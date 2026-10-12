"""ETF 한 종목의 T12 전 과정 — 연도 순차 (PROTOCOL_LOCK 전 항목). 병렬 단위 = 이 함수 1회.

출력: ``<out_dir>/<ticker>/*.csv`` (집계표) + ``daily.csv.gz`` (일별 수익률·예측분산·잔차 — 원시 시세 역산 가능,
공개 저장소 금지). 모든 쓰기는 tmp → rename 원자적. 결과는 처리 순서·worker 수와 무관해야 한다.
"""

from __future__ import annotations

import functools
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..svrgarch_etf.rolling import rolling_cusum
from .calibration import (
    critical_from_draws,
    draws_block,
    draws_iid,
    draws_normal,
    null_episode_rate,
    posthoc,
    rolling_with_context,
    summarize_alarms,
)
from .config import array_hash, config_hash, rng_for
from .diagnostics import ANN, annual_rv, forecast_metrics, prior_quantile, residual_stats
from .fit import AnnualFit, baseline_variance, fit_annual, forecast_year, insample_variance, standardize
from .folds import STRATEGIES, build_fold, training_mask, year_status

POLICIES: tuple[str, ...] = ("A", "B", "base")
METHODS: tuple[str, ...] = ("asymptotic", "iid_insample", "iid_prequential", "normal_mc", "block_insample")
FLOAT_FMT = "%.10g"


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def frame_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n", float_format=FLOAT_FMT)
    return buf.getvalue().encode("utf-8")


def _gzip_bytes(raw: bytes) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw)
    return out.getvalue()


def _calibration_status(method: str, policy: str, year: int, first_test: int) -> str:
    if method == "asymptotic":
        return "REFERENCE_ASYMPTOTIC"
    if method == "normal_mc":
        return "REFERENCE_NORMAL"
    if method == "block_insample":
        return "DIFFERENT_NULL_SENSITIVITY"
    if method == "iid_prequential":
        return "NOT_ESTIMABLE" if year == first_test else "PREQUENTIAL_OOS"
    if policy == "base":
        return "HISTORICAL_CAUSAL_RESIDUALS"
    return "IN_SAMPLE_RESIDUAL_CALIBRATION" + ("_POOL_POLICY_A" if policy == "B" else "")


@functools.lru_cache(maxsize=256)
def _normal_draws(study_id: str, n: int, reps: int, purpose: str) -> np.ndarray:
    """정규 iid 참조 표본 — 풀과 무관하므로 (n, reps, 용도) 만으로 seed 를 정한다 (C-11). 읽기 전용."""
    d = draws_normal(n, reps, rng_for(study_id, "normal_reference", n, reps, purpose))
    d.setflags(write=False)
    return d


@functools.lru_cache(maxsize=512)
def _normal_critical(study_id: str, n: int, reps: int, q: float, purpose: str) -> float:
    return critical_from_draws(_normal_draws(study_id, n, reps, purpose), q)


@functools.lru_cache(maxsize=2048)
def _normal_null(study_id: str, n: int, w: int, sims: int, crit: float, gap: int) -> tuple[float, float]:
    return null_episode_rate(_normal_draws(study_id, n, sims, "null"), w, crit, gap)


def _draws(
    method: str, pool: np.ndarray | None, n: int, reps: int, cfg: dict, key: tuple[Any, ...]
) -> np.ndarray | None:
    c = cfg["calibration"]
    if method in ("normal_mc", "asymptotic"):
        return _normal_draws(cfg["study_id"], n, reps, str(key[-1]))
    rng = rng_for(cfg["study_id"], *key, method)
    if method in ("iid_insample", "iid_prequential"):
        if pool is None or np.isfinite(pool).sum() < 50:
            return None
        return draws_iid(pool, n, reps, rng)
    if method == "block_insample":
        if pool is None or np.isfinite(pool).sum() < 50:
            return None
        return draws_block(pool, n, reps, c["block_length"], rng)
    raise ValueError(method)


def _reps(method: str, cfg: dict) -> int:
    c = cfg["calibration"]
    return {
        "iid_insample": c["iid_reps"],
        "iid_prequential": c["iid_reps"],
        "normal_mc": c["normal_reps"],
        "block_insample": c["block_reps"],
        "asymptotic": c["iid_reps"],
    }[method]


def run_ticker(
    ticker: str, r_common: pd.Series, cfg: dict, out_dir: str | Path, meta: dict[str, str]
) -> dict[str, Any]:
    """한 ETF 의 2020..2026 연도 순차 실행. r_common: 공통 거래일 index 의 100·Δlog 수익률 (DQ NaN 포함)."""
    out = Path(out_dir) / ticker
    out.mkdir(parents=True, exist_ok=True)
    cfg_h = config_hash(cfg)
    first_train = cfg["folds"]["initial_train_calendar_year"]
    years = cfg["folds"]["test_calendar_years"]
    first_test = years[0]
    windows = cfg["cusum"]["windows"]
    gap = cfg["cusum"]["episode_gap_trading_days"]
    qpt = cfg["calibration"]["pointwise_quantile"]
    asym = cfg["cusum"]["asymptotic_critical_5pct"]
    sid = cfg["study_id"]

    idx = pd.DatetimeIndex(r_common.index)
    rc = r_common.to_numpy(float)
    valid = r_common.dropna()
    vdates = pd.DatetimeIndex(valid.index)
    vvals = valid.to_numpy(float)
    bwin, bmin = cfg["models"]["baseline_window"], cfg["models"]["baseline_min_periods"]
    base_var = baseline_variance(r_common, bwin, bmin).to_numpy(float)
    base_e = standardize(rc, base_var)
    roll_vol = (r_common.rolling(bwin, min_periods=bmin).std(ddof=1) * ANN).to_numpy(float)

    T: dict[str, list[dict[str, Any]]] = {
        k: []
        for k in (
            "fold_manifest",
            "fit_summary",
            "annual_vol_diagnostics",
            "annual_forecast_diagnostics",
            "annual_residual_diagnostics",
            "annual_posthoc",
            "annual_cusum_diagnostics",
            "annual_history_ablation",
        )
    }
    daily: list[pd.DataFrame] = []
    oos_pool: dict[str, list[np.ndarray]] = {p: [] for p in POLICIES}
    fit2019: AnnualFit | None = None

    for y in years:
        ys, ye = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")
        tm = np.asarray((idx >= ys) & (idx < ye))
        pm = np.asarray(idx < ys)
        tdates_c = idx[tm]
        r_test = rc[tm]
        n_days = int(tm.sum())
        ystat = year_status(y, cfg)
        known_at = str(tdates_c[-1].date()) if n_days else None

        # ── V ── (사후 정보, known_at = 연도 마지막 관측 후)
        def rv_of(yy: int) -> float:
            return annual_rv(rc[np.asarray(idx.year == yy)])

        rv_y, rv_prev = rv_of(y), rv_of(y - 1)
        lo3 = max(first_train, y - 3)
        rv3 = annual_rv(rc[np.asarray((idx.year >= lo3) & (idx.year <= y - 1))])
        T["annual_vol_diagnostics"].append(
            {
                "ticker": ticker,
                "year": y,
                "n_obs": n_days,
                "n_returns": int(np.isfinite(r_test).sum()),
                "n_missing": int((~np.isfinite(r_test)).sum()),
                "rv_ann_pct": rv_y,
                "rv_prev_ann_pct": rv_prev,
                "rv_ratio": rv_y / rv_prev,
                "rv_delta_pctpoint": rv_y - rv_prev,
                "rv_log_ratio": float(np.log(rv_y / rv_prev)),
                "rv_3y_historical": rv3,
                "rv_3y_years": f"{lo3}-{y - 1}",
                "rv_2019_ann_pct": rv_of(first_train),
                "rv_prior_quantile": prior_quantile(rv_y, roll_vol[pm]),
                "partial_year": ystat == "PARTIAL_NON_BLIND",
                "year_status": ystat,
                "known_at": f"{known_at} close (ex-post)",
                "quality_flags": "DQ_NAN_PRESENT" if (~np.isfinite(r_test)).any() else "",
            }
        )

        # ── folds ──
        folds = {s: build_fold(ticker, r_common, y, s, cfg) for s in STRATEGIES}
        for s, f in folds.items():
            T["fold_manifest"].append(
                {
                    "ticker": ticker,
                    "year": y,
                    "history_strategy": s,
                    "train_start": f.train_start.date() if f.train_start is not None else None,
                    "train_end": f.train_end.date() if f.train_end is not None else None,
                    "n_train_history": f.n_history,
                    "n_inner_train": f.n_inner_train,
                    "n_inner_val": f.n_inner_val,
                    "test_start": f.test_start.date() if f.test_start is not None else None,
                    "test_end": f.test_end.date() if f.test_end is not None else None,
                    "n_test": f.n_test,
                    "fold_status": f.status,
                    "leak_check_train_end_lt_test_start": bool(
                        f.train_end is None or f.test_start is None or f.train_end < f.test_start
                    ),
                    "data_version": meta["data_version"],
                    "config_hash": cfg_h,
                    "git_sha": meta["git_sha"],
                }
            )
        fe = folds["expanding"]
        if fe.status in ("INSUFFICIENT_HISTORY", "NO_TEST_DATA"):
            continue  # 해당 fold 의 모든 진단 행은 병합 단계에서 NOT_ESTIMABLE 로 채운다

        vpre = np.asarray(vdates < ys)
        vtest = np.asarray((vdates >= ys) & (vdates < ye))
        ctx, tvals, tdates_v = vvals[vpre], vvals[vtest], vdates[vtest]
        if ctx.size == 0 or vdates[vpre][-1] >= tdates_v[0]:
            raise AssertionError("leakage: history must end before test")

        af = fit_annual(ctx, fe.n_inner_train)
        if y == first_train + 1:
            fit2019 = af
        T["fit_summary"].append(
            {
                "ticker": ticker,
                "year": y,
                "history_strategy": "expanding",
                "train_cutoff": str(vdates[vpre][-1].date()),
                "C": af.params[0],
                "gamma_squared": af.params[1],
                "epsilon": af.params[2],
                "val_mae": af.val_mae,
                "n_history": af.n_history,
                "fit_status": "OK",
                "history_hash": af.history_hash,
                "model_hash": af.model_hash,
            }
        )

        def to_common(
            values_v: np.ndarray, dates_v: pd.DatetimeIndex, target: pd.DatetimeIndex
        ) -> np.ndarray:
            return pd.Series(values_v, index=dates_v).reindex(target).to_numpy(float)

        var = {
            "A": to_common(forecast_year(af.fit, ctx, tvals, "A"), tdates_v, tdates_c),
            "B": to_common(forecast_year(af.fit, ctx, tvals, "B"), tdates_v, tdates_c),
            "base": base_var[tm],
        }
        e_test = {p: standardize(r_test, var[p]) for p in POLICIES}
        ins_v = insample_variance(af.fit, ctx)
        pre_a = to_common(standardize(ctx, ins_v), vdates[vpre], idx[pm])
        pre_e = {"A": pre_a, "B": pre_a, "base": base_e[pm]}

        # ── M ──
        ok = {p: np.isfinite(r_test) & np.isfinite(var[p]) & (var[p] > 0) for p in POLICIES}
        inter = ok["A"] & ok["B"] & ok["base"]
        n_ret = int(np.isfinite(r_test).sum())
        for p in POLICIES:
            m = forecast_metrics(r_test[inter], var[p][inter])
            own = forecast_metrics(r_test[ok[p]], var[p][ok[p]])
            T["annual_forecast_diagnostics"].append(
                {
                    "ticker": ticker,
                    "year": y,
                    "policy": p,
                    "history_strategy": "expanding" if p != "base" else "none",
                    "eligible_set": "INTERSECTION_A_B_BASE",
                    **m,
                    "val_mae": af.val_mae if p != "base" else np.nan,
                    "own_n_eligible": own["n_eligible"],
                    "own_oos_qlike": own["oos_qlike"],
                    "own_mean_sq_standardized_residual": own["mean_sq_standardized_residual"],
                    "coverage": own["n_eligible"] / n_ret if n_ret else np.nan,
                    "nonpos_var": int(np.sum(np.isfinite(var[p]) & (var[p] <= 0))),
                    "missing_prediction": int(np.sum(~np.isfinite(var[p]) & np.isfinite(r_test))),
                    "fit_status": "OK",
                    "year_status": ystat,
                }
            )

        # ── N ──
        for p in POLICIES:
            st = residual_stats(e_test[p], cfg)
            T["annual_residual_diagnostics"].append(
                {
                    "ticker": ticker,
                    "year": y,
                    "policy": p,
                    "history_strategy": "expanding" if p != "base" else "none",
                    **st,
                    "year_status": ystat,
                }
            )

        # ── C ── 연간 사후 + 이동창 (방법별 임계값)
        for p in POLICIES:
            hist = "expanding" if p != "base" else "none"
            pools: dict[str, np.ndarray | None] = {
                "iid_insample": pre_e[p],
                "block_insample": pre_e[p],
                "iid_prequential": np.concatenate(oos_pool[p]) if oos_pool[p] else None,
                "normal_mc": None,
                "asymptotic": None,
            }
            ph = posthoc(e_test[p])
            n_post = int(ph["n_test_residuals"])
            khat = ph["khat_pos"]
            annual_crit: dict[str, float] = {}
            for meth in METHODS:
                if meth == "asymptotic":
                    annual_crit[meth] = asym
                    continue
                if meth == "normal_mc":
                    annual_crit[meth] = _normal_critical(sid, n_post, _reps(meth, cfg), qpt, "annual")
                    continue
                d = _draws(meth, pools[meth], n_post, _reps(meth, cfg), cfg, (ticker, y, p, hist, "annual"))
                annual_crit[meth] = critical_from_draws(d, qpt) if d is not None else np.nan
            for meth in METHODS:
                c = annual_crit[meth]
                status = _calibration_status(meth, p, y, first_test)
                T["annual_posthoc"].append(
                    {
                        "ticker": ticker,
                        "year": y,
                        "policy": p,
                        "history_strategy": hist,
                        "calibration_method": meth,
                        "n_test_residuals": n_post,
                        "annual_T": ph["annual_T"],
                        "annual_critical": c,
                        "annual_reject": bool(ph["annual_T"] >= c) if np.isfinite(c) else None,
                        "T_over_critical": ph["annual_T"] / c if np.isfinite(c) else np.nan,
                        "khat_argmax_date": str(tdates_c[khat].date()) if khat is not None else None,
                        "khat_label": "argmax_location_only",
                        "available_at": f"{known_at} close",
                        "calibration_status": status if np.isfinite(c) else "NOT_ESTIMABLE",
                        "calibration_cutoff": str(idx[pm][-1].date()),
                        "year_status": ystat,
                    }
                )

            for w in windows:
                stat_c = rolling_with_context(pre_e[p], e_test[p], w)
                stat_yc = rolling_cusum(e_test[p], w)
                pure = np.arange(n_days) >= w - 1
                if pure.any() and not np.allclose(
                    stat_c[pure], stat_yc[pure], equal_nan=True, rtol=0, atol=0
                ):
                    raise AssertionError("YEAR_CONTAINED must equal CARRY on PURE_OOS_WINDOW days")
                for meth in METHODS:
                    if meth == "asymptotic":
                        crit = asym
                    elif meth == "normal_mc":
                        crit = _normal_critical(sid, w, _reps(meth, cfg), qpt, "window")
                    else:
                        d = _draws(
                            meth, pools[meth], w, _reps(meth, cfg), cfg, (ticker, y, p, hist, w, "window")
                        )
                        crit = critical_from_draws(d, qpt) if d is not None else np.nan
                    status = (
                        _calibration_status(meth, p, y, first_test) if np.isfinite(crit) else "NOT_ESTIMABLE"
                    )
                    # 귀무 기대 에피소드: 같은 생성 방식, 길이 n_days, PURE 창만 (asymptotic 은 정규 iid)
                    sims = cfg["calibration"]["null_sims"]
                    if meth in ("asymptotic", "normal_mc"):
                        null_mean, null_any = _normal_null(sid, n_days, w, sims, crit, gap)
                    else:
                        nd = (
                            _draws(meth, pools[meth], n_days, sims, cfg, (ticker, y, p, hist, w, "null"))
                            if np.isfinite(crit)
                            else None
                        )
                        null_mean, null_any = (
                            null_episode_rate(nd, w, crit, gap) if nd is not None else (np.nan, np.nan)
                        )
                    for mode in ("CARRY", "YEAR_CONTAINED"):
                        mask = np.ones(n_days, bool) if mode == "CARRY" else pure
                        sm = (
                            summarize_alarms(stat_c, mask, crit, gap)
                            if np.isfinite(crit)
                            else {
                                "n_valid_stat_days": int(np.isfinite(np.where(mask, stat_c, np.nan)).sum()),
                                "rolling_peak_T": float(np.nanmax(np.where(mask, stat_c, np.nan)))
                                if np.isfinite(np.where(mask, stat_c, np.nan)).any()
                                else np.nan,
                                "rolling_alarm_days": None,
                                "rolling_episodes": None,
                                "first_alarm_pos": None,
                            }
                        )
                        n_pure = int(pure.sum())
                        interp = []
                        if mode == "YEAR_CONTAINED" and n_pure == 0:
                            interp.append("NO_FULL_WINDOW")
                        if mode == "CARRY":
                            interp.append("INCLUDES_CROSS_BOUNDARY_WARM_PREYEAR_RESTANDARDIZED")
                        if ystat != "PRIMARY":
                            interp.append(ystat)
                        interp.append("alarm_frequency_not_ground_truth_false_positive")
                        fa = sm["first_alarm_pos"]
                        eps = sm["rolling_episodes"]
                        span = int(mask.sum())
                        T["annual_cusum_diagnostics"].append(
                            {
                                "ticker": ticker,
                                "year": y,
                                "policy": p,
                                "history_strategy": hist,
                                "window": w,
                                "boundary_mode": mode,
                                "calibration_method": meth,
                                "n_pure_oos_days": n_pure,
                                "n_cross_boundary_days": int(n_days - n_pure),
                                "n_mask_days": span,
                                "n_valid_stat_days": sm["n_valid_stat_days"],
                                "annual_T": ph["annual_T"],
                                "annual_critical": annual_crit[meth],
                                "annual_reject": bool(ph["annual_T"] >= annual_crit[meth])
                                if np.isfinite(annual_crit[meth])
                                else None,
                                "annual_khat_argmax": str(tdates_c[khat].date())
                                if khat is not None
                                else None,
                                "rolling_peak_T": sm["rolling_peak_T"],
                                "pointwise_null_quantile": crit,
                                "peak_T_over_critical": sm["rolling_peak_T"] / crit
                                if np.isfinite(crit) and np.isfinite(sm["rolling_peak_T"])
                                else np.nan,
                                "rolling_alarm_days": sm["rolling_alarm_days"],
                                "rolling_episodes": eps,
                                "episodes_per_252_days": eps * 252 / span
                                if eps is not None and span
                                else np.nan,
                                "first_alarm_date": str(tdates_c[int(fa)].date()) if fa is not None else None,
                                "expected_null_episodes": null_mean,
                                "null_prob_any_episode": null_any,
                                "calibration_cutoff": str(idx[pm][-1].date()),
                                "calibration_status": status,
                                "interpretation_status": ";".join(interp),
                                "year_status": ystat,
                            }
                        )
                daily.append(
                    pd.DataFrame(
                        {
                            "ticker": ticker,
                            "year": y,
                            "policy": p,
                            "window": w,
                            "date": tdates_c.date,
                            "pure_oos_window": pure,
                            "T": stat_c,
                        }
                    )
                )
            daily.append(
                pd.DataFrame(
                    {
                        "ticker": ticker,
                        "year": y,
                        "policy": p,
                        "window": 0,
                        "date": tdates_c.date,
                        "pure_oos_window": True,
                        "T": np.nan,
                        "r": r_test,
                        "vhat": var[p],
                        "e": e_test[p],
                    }
                )
            )
            oos_pool[p].append(e_test[p][np.isfinite(e_test[p])])

        # ── H ── 동일 연도·동일 날짜, 학습 이력만 다른 SVR (A, B)
        h_fits: dict[str, AnnualFit | None] = {"expanding": af}
        h_train: dict[str, np.ndarray] = {"expanding": ctx}
        for s in ("trailing_2y", "frozen_2019"):
            f = folds[s]
            if f.status in ("IDENTICAL_TO_EXPANDING",) or f.status.startswith("SKIP"):
                h_fits[s] = None
                continue
            if f.status == "INSUFFICIENT_HISTORY":
                h_fits[s] = None
                continue
            trm = training_mask(vdates, y, s, cfg)
            h_train[s] = vvals[trm]
            if s == "frozen_2019":
                if fit2019 is None:
                    raise AssertionError("frozen_2019 requires the 2020 fold model")
                h_fits[s] = fit2019
            else:
                h_fits[s] = fit_annual(vvals[trm], f.n_inner_train)
            hf = h_fits[s]
            assert hf is not None
            T["fit_summary"].append(
                {
                    "ticker": ticker,
                    "year": y,
                    "history_strategy": s,
                    "train_cutoff": str(vdates[trm][-1].date()),
                    "C": hf.params[0],
                    "gamma_squared": hf.params[1],
                    "epsilon": hf.params[2],
                    "val_mae": hf.val_mae,
                    "n_history": hf.n_history,
                    "fit_status": "OK",
                    "history_hash": hf.history_hash,
                    "model_hash": hf.model_hash,
                }
            )
        for p in ("A", "B"):
            hv: dict[str, np.ndarray] = {}
            for s, hf in h_fits.items():
                if hf is None:
                    continue
                hv[s] = (
                    var[p]
                    if s == "expanding"
                    else to_common(forecast_year(hf.fit, ctx, tvals, p), tdates_v, tdates_c)
                )
            paired = np.isfinite(r_test).copy()
            for v in hv.values():
                paired &= np.isfinite(v) & (v > 0)
            base_row: dict[str, Any] = {}
            for s in STRATEGIES:
                f = folds[s]
                hf = h_fits.get(s)
                row: dict[str, Any] = {
                    "ticker": ticker,
                    "year": y,
                    "policy": p,
                    "history_strategy": s,
                    "train_start": f.train_start.date() if f.train_start is not None else None,
                    "train_end": f.train_end.date() if f.train_end is not None else None,
                    "n_history": f.n_history,
                    "h_status": f.status if hf is None else "COMPUTED",
                    "year_status": ystat,
                    "protocol_version": cfg["protocol_version"],
                }
                if hf is None:
                    T["annual_history_ablation"].append(row)
                    continue
                e_s = standardize(r_test, hv[s])
                ph_s = posthoc(e_s)
                pool_s = standardize(h_train[s], insample_variance(hf.fit, h_train[s]))
                n_s = int(ph_s["n_test_residuals"])
                d_ann = _draws(
                    "iid_insample",
                    pool_s,
                    n_s,
                    cfg["calibration"]["iid_reps"],
                    cfg,
                    (ticker, y, p, s, "annual_h"),
                )
                c_ann = critical_from_draws(d_ann, qpt) if d_ann is not None else np.nan
                d_w = _draws(
                    "iid_insample",
                    pool_s,
                    60,
                    cfg["calibration"]["iid_reps"],
                    cfg,
                    (ticker, y, p, s, 60, "window_h"),
                )
                c_w = critical_from_draws(d_w, qpt) if d_w is not None else np.nan
                pre_s = to_common(standardize(ctx, insample_variance(hf.fit, ctx)), vdates[vpre], idx[pm])
                stat60 = rolling_with_context(pre_s, e_s, 60)
                pure60 = np.arange(n_days) >= 59
                sw = (
                    summarize_alarms(stat60, pure60, c_w, gap)
                    if np.isfinite(c_w)
                    else {"rolling_episodes": None}
                )
                fm = forecast_metrics(r_test[paired], hv[s][paired])
                row.update(
                    {
                        "C": hf.params[0],
                        "gamma_squared": hf.params[1],
                        "epsilon": hf.params[2],
                        "val_mae": hf.val_mae,
                        "n_paired_days": int(paired.sum()),
                        "oos_qlike": fm["oos_qlike"],
                        "mean_sq_standardized_residual": fm["mean_sq_standardized_residual"],
                        "annual_T": ph_s["annual_T"],
                        "annual_reject_asymptotic": bool(ph_s["annual_T"] >= asym),
                        "annual_critical_iid_own_insample": c_ann,
                        "annual_reject_iid_own_insample": bool(ph_s["annual_T"] >= c_ann)
                        if np.isfinite(c_ann)
                        else None,
                        "w60_critical_iid_own_insample": c_w,
                        "n_rolling_episodes_w60_pure": sw["rolling_episodes"],
                        "model_hash": hf.model_hash,
                    }
                )
                if s == "expanding":
                    base_row = row
                    row["relative_to_expanding"] = "REFERENCE"
                else:
                    row["relative_to_expanding"] = "COMPARED"
                    row["d_qlike_vs_expanding"] = fm["oos_qlike"] - base_row["oos_qlike"]
                    row["d_annual_T_vs_expanding"] = ph_s["annual_T"] - base_row["annual_T"]
                T["annual_history_ablation"].append(row)

    files: dict[str, str] = {}
    for name, rows in T.items():
        data = frame_bytes(pd.DataFrame(rows))
        _write_atomic(out / f"{name}.csv", data)
        files[f"{name}.csv"] = hashlib.sha256(data).hexdigest()
    dd = pd.concat(daily, ignore_index=True) if daily else pd.DataFrame()
    _write_atomic(out / "daily.csv.gz", _gzip_bytes(frame_bytes(dd)))
    done = {
        "ticker": ticker,
        "config_hash": cfg_h,
        "data_version": meta["data_version"],
        "code_sha": meta["code_sha"],
        "input_sha": array_hash(rc),
        "files": files,
    }
    _write_atomic(out / "DONE.json", (json.dumps(done, indent=1, sort_keys=True) + "\n").encode())
    return done
