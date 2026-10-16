"""T12 일별 잔차에서 03·04의 실제 창 경로와 유효일·경보 부담을 재계산한다.

일별 원자료·잔차는 Git에 넣지 않는다. T12 동결 cache를 읽고 PURE 구간을
원본 ``rolling_cusum``으로 재계산해 캐시 경로와 수치 일치까지 확인한다.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.svrgarch_etf.rolling import episodes, rolling_cusum, window_khat


def frozen_root(current_root: Path) -> Path:
    """옆 작업트리를 기본값으로 쓰되 환경변수로 고정 T12 위치를 교체할 수 있다."""
    return Path(os.environ.get("T12_FROZEN_ROOT", current_root.parent / "R2H_T12_Final")).resolve()


def verify_frozen(current_root: Path, source_root: Path, cfg: dict) -> dict:
    """원본 노트북 3개·원자료 22개와 run manifest를 해시로 대조한다."""
    m = json.loads(
        (current_root / "research/t12_annual_expanding_v2/FINAL_RELEASE_MANIFEST.json").read_text()
    )
    names = [p for p in m["files_sha256"] if p.startswith("data/raw/") or p.startswith("notebooks/0")]
    assert len([p for p in names if p.startswith("data/raw/")]) == 22
    assert len([p for p in names if p.startswith("notebooks/0")]) == 3
    for name in names:
        src = current_root / name
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest() != m["files_sha256"][name]:
            raise AssertionError(f"T12 동결 입력 변경: {name}")
    if m["run_id"] != cfg["base_t12_run_id"]:
        raise AssertionError("T12 run_id 불일치")
    run = source_root / "outputs/t12/notebook" / m["run_id"] / "results/run_manifest.json"
    manifest = json.loads(run.read_text())
    if manifest["data_version"] != "5f20e3e0073b521a" or not manifest["integrity_pass"]:
        raise AssertionError("T12 실행 manifest 미승인")
    daily = source_root / "outputs/t12/work" / m["run_id"]
    tickers = [p.name for p in daily.glob("*/daily.csv.gz")]
    if len(tickers) != 20:
        raise AssertionError(f"T12 일별 cache 20종 중 {len(tickers)}종만 존재")
    return {
        "run_id": m["run_id"],
        "data_version": manifest["data_version"],
        "notebook_count": 3,
        "raw_sha_count": 22,
        "daily_ticker_count": len(tickers),
        "source_root": str(source_root),
    }


def _table_for_ticker(source_root: Path, run_id: str, ticker: str) -> pd.DataFrame:
    path = source_root / "outputs/t12/work" / run_id / ticker / "daily.csv.gz"
    if not path.is_file():
        raise FileNotFoundError(path)
    d = pd.read_csv(path, dtype={"ticker": str, "policy": str}, parse_dates=["date"])
    if not d.ticker.eq(ticker).all():
        raise AssertionError("daily cache ticker 보존 실패")
    return d


def _t12_critical(source_root: Path, run_id: str) -> dict[tuple[str, int, str, int], float]:
    path = source_root / "outputs/t12/notebook" / run_id / "results/annual_cusum_diagnostics.csv"
    d = pd.read_csv(path, dtype={"ticker": str})
    d = d.query("calibration_method == 'iid_insample' and boundary_mode == 'YEAR_CONTAINED'")
    key = ["ticker", "year", "policy", "window"]
    if d.duplicated(key).any():
        raise AssertionError("T12 임계값 키 중복")
    return {
        tuple(k): float(c)
        for k, c in zip(d[key].itertuples(index=False, name=None), d.pointwise_null_quantile, strict=True)
    }


def _t12_episodes(source_root: Path, run_id: str) -> dict[tuple[str, int, str, int], int | None]:
    path = source_root / "outputs/t12/notebook" / run_id / "results/annual_cusum_diagnostics.csv"
    d = pd.read_csv(path, dtype={"ticker": str})
    d = d.query("calibration_method == 'iid_insample' and boundary_mode == 'YEAR_CONTAINED'")
    return {
        tuple(k): (None if pd.isna(v) else int(v))
        for k, v in zip(
            d[["ticker", "year", "policy", "window"]].itertuples(index=False, name=None),
            d.rolling_episodes,
            strict=True,
        )
    }


def _empirical_rows(
    ticker: str,
    daily: pd.DataFrame,
    cfg: dict,
    point_critical: dict,
    point_episodes: dict,
    pipe_critical: dict,
) -> tuple[list[dict], list[dict], list[dict], float]:
    valid_rows: list[dict] = []
    metric_rows: list[dict] = []
    candidate_rows: list[dict] = []
    max_cache_diff = 0.0
    all_w = cfg["windows_all"]
    main_w = cfg["windows_primary"]
    for (year, policy), group in daily.groupby(["year", "policy"], sort=True):
        base = group[group.window.eq(0)].sort_values("date")
        dates = pd.DatetimeIndex(base.date)
        e = base.e.to_numpy(float)
        n = len(e)
        if n == 0 or dates.has_duplicates:
            raise AssertionError("연도별 일별 잔차 인덱스 오류")
        stats: dict[int, np.ndarray] = {}
        for w in all_w:
            cache = group[group.window.eq(w)].sort_values("date")
            if not dates.equals(pd.DatetimeIndex(cache.date)):
                raise AssertionError(f"일별 캐시 정렬/날짜 차이: {ticker}/{year}/{policy}/{w}")
            recalc = rolling_cusum(e, w)
            pure = np.arange(n) >= w - 1
            old = cache["T"].to_numpy(float)
            if pure.any():
                if not np.allclose(recalc[pure], old[pure], equal_nan=True, rtol=1e-8, atol=1e-8):
                    raise AssertionError(f"T12 PURE 경로 불일치: {ticker}/{year}/{policy}/{w}")
                ok = pure & np.isfinite(recalc) & np.isfinite(old)
                if ok.any():
                    max_cache_diff = max(max_cache_diff, float(np.max(np.abs(recalc[ok] - old[ok]))))
            stats[w] = recalc
        common = np.arange(n) >= cfg["common_start_zero_based"]
        for w in main_w:
            common &= np.isfinite(stats[w])
        for w in all_w:
            pure = np.arange(n) >= w - 1
            possible = int(pure.sum())
            own = pure & np.isfinite(stats[w])
            validity = {
                "ticker": ticker,
                "year": int(year),
                "policy": policy,
                "w": w,
                "n_year_days": n,
                "n_pure_possible": possible,
                "n_pure_valid": int(own.sum()),
                "n_common_valid": int(common.sum()) if w in main_w else 0,
                "first_pure_valid": str(dates[np.flatnonzero(own)[0]].date()) if own.any() else "",
                "first_common_valid": str(dates[np.flatnonzero(common)[0]].date())
                if w in main_w and common.any()
                else "",
                "last_common_valid": str(dates[np.flatnonzero(common)[-1]].date())
                if w in main_w and common.any()
                else "",
                "year_status": (
                    "PRIMARY"
                    if year in cfg["core_years"]
                    else ("PILOT_SHORT_HISTORY" if year == 2020 else "PARTIAL_NON_BLIND")
                ),
                "status": (
                    "NO_FULL_WINDOW"
                    if possible == 0
                    else ("NO_VALID_COMMON_DAYS" if w in main_w and not common.any() else "EVALUABLE")
                ),
            }
            valid_rows.append(validity)
            if w not in main_w:
                continue
            for threshold_type, critical in (
                ("t12_pointwise_iid_insample", point_critical[ticker, year, policy, w]),
                ("pipeline_garch_annual_max", pipe_critical[policy, w]),
            ):
                for sample_type, mask in (("own_pure", own), ("common", common)):
                    alarm = mask & np.isfinite(stats[w]) & (stats[w] >= critical)
                    ep = episodes(alarm, gap=cfg["episode_gap_non_alarm_days"])
                    nd = int(mask.sum())
                    metric_rows.append(
                        {
                            "ticker": ticker,
                            "year": int(year),
                            "policy": policy,
                            "w": w,
                            "threshold_type": threshold_type,
                            "critical": critical,
                            "sample_type": sample_type,
                            "n_valid_days": nd,
                            "alarm_days": int(alarm.sum()),
                            "episodes": len(ep),
                            "any_alarm": int(bool(ep)),
                            "episodes_per_252_valid_days": len(ep) * 252 / nd if nd else np.nan,
                            "first_alarm_at": str(dates[ep[0][0]].date()) if ep else "",
                            "year_status": validity["year_status"],
                        }
                    )
                    if threshold_type == "pipeline_garch_annual_max" and sample_type == "common":
                        for start, end in ep:
                            khat = window_khat(e, start, w)
                            candidate_rows.append(
                                {
                                    "ticker": ticker,
                                    "year": int(year),
                                    "policy": policy,
                                    "w": w,
                                    "window_start": str(dates[start - w + 1].date()),
                                    "window_end": str(dates[start].date()),
                                    "alarm_at": str(dates[start].date()),
                                    "estimated_change_at": str(dates[khat].date())
                                    if khat is not None
                                    else "",
                                    "episode_last_alarm_at": str(dates[end].date()),
                                    "threshold": critical,
                                    "T_at_alarm": float(stats[w][start]),
                                    "boundary_mode": "PURE_OOS_WINDOW_COMMON",
                                    "available_at": str(dates[start].date()) + " close",
                                    "candidate_reason": "exploratory_first_episode_not_price_label",
                                }
                            )
                    if threshold_type == "t12_pointwise_iid_insample" and sample_type == "own_pure":
                        previous = point_episodes[ticker, year, policy, w]
                        if previous is not None and previous != len(ep):
                            raise AssertionError(f"T12 에피소드 수 불일치: {ticker}/{year}/{policy}/{w}")
    return valid_rows, metric_rows, candidate_rows, max_cache_diff


def empirical_experiment(
    current_root: Path,
    source_root: Path,
    cfg: dict,
    tickers: list[str],
    pipeline_thresholds: pd.DataFrame,
    out: Path,
) -> dict[str, pd.DataFrame]:
    """03·04 모두 같은 함수와 기준표를 써서 ETF subset 동등성을 보장한다."""
    out.mkdir(parents=True, exist_ok=True)
    run_id = cfg["base_t12_run_id"]
    point = _t12_critical(source_root, run_id)
    episode_truth = _t12_episodes(source_root, run_id)
    pipe = pipeline_thresholds.set_index(["policy", "w"]).critical_annual_max.to_dict()
    valid_rows: list[dict] = []
    metric_rows: list[dict] = []
    candidate_rows: list[dict] = []
    qa_rows: list[dict] = []
    for ticker in tickers:
        daily_path = source_root / "outputs/t12/work" / run_id / ticker / "daily.csv.gz"
        daily = _table_for_ticker(source_root, run_id, ticker)
        a, b, c, diff = _empirical_rows(ticker, daily, cfg, point, episode_truth, pipe)
        valid_rows += a
        metric_rows += b
        candidate_rows += c
        qa_rows.append(
            {
                "ticker": ticker,
                "daily_sha256": hashlib.sha256(daily_path.read_bytes()).hexdigest(),
                "max_abs_pure_T_diff_from_T12_cache": diff,
                "n_daily_rows": len(daily),
            }
        )
    files = {
        "validity.csv": pd.DataFrame(valid_rows),
        "alarm_metrics.csv": pd.DataFrame(metric_rows),
        "cnn_candidate_intervals.csv": pd.DataFrame(candidate_rows),
        "daily_cache_qa.csv": pd.DataFrame(qa_rows),
    }
    for name, frame in files.items():
        frame.to_csv(out / name, index=False, float_format="%.10g")
    return files


def category_exposure(current_root: Path) -> pd.DataFrame:
    """T11 공식 종목표의 category와 사전 고정 KOSPI200 중복 그룹을 연결한다."""
    path = current_root / "research/svr_garch_cusum_etf/reference_close_sha256.csv"
    d = pd.read_csv(path, dtype={"ticker": str})[["ticker", "name", "category"]]
    group = {x: "KOSPI200_동일노출" for x in ("069500", "102110", "122630", "114800")}
    d["exposure_group"] = d.ticker.map(group).fillna(d.ticker)
    return d
