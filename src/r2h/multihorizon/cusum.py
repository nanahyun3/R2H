"""W1 CUSUM 의 일별 경보를 T12 잔차와 W1 동결 임계값으로 재계산하고 W1 집계표와 대조한다 (계약 §3-5).

연도별 적합 경계를 넘는 창은 만들지 않는다. 표본 마스크 밖 날짜는 ``NOT_AVAILABLE`` 이다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from r2h.svrgarch_etf.rolling import episodes, rolling_cusum
from r2h.window_study.empirical import _t12_critical


def load_daily_cache(source_root: Path, run_id: str, ticker: str) -> pd.DataFrame:
    path = source_root / "outputs/t12/work" / run_id / ticker / "daily.csv.gz"
    d = pd.read_csv(path, dtype={"ticker": str, "policy": str}, parse_dates=["date"])
    if not d.ticker.eq(ticker).all():
        raise AssertionError("daily cache ticker 불일치")
    return d


def residual_table(daily: pd.DataFrame) -> pd.DataFrame:
    """window==0 행: 날짜 × 정책의 r(%) · vhat(%²) · e."""
    base = daily[daily.window.eq(0)][["year", "policy", "date", "r", "vhat", "e"]]
    if base.duplicated(["policy", "date"]).any():
        raise AssertionError("잔차 날짜 중복")
    return base.sort_values(["policy", "date"]).reset_index(drop=True)


def daily_cusum(
    ticker: str,
    daily: pd.DataFrame,
    cfg_w1: dict,
    pipe_critical: dict[tuple[str, int], float],
    point_critical: dict[tuple[str, int, str, int], float],
    windows: list[int],
) -> pd.DataFrame:
    """(policy, date) 별 T_w 와 경보 상태. 상태: ALARM / NO_ALARM / NOT_AVAILABLE."""
    rows = []
    for (year, policy), group in daily.groupby(["year", "policy"], sort=True):
        base = group[group.window.eq(0)].sort_values("date")
        dates = pd.DatetimeIndex(base.date)
        e = base.e.to_numpy(float)
        n = len(e)
        stats = {w: rolling_cusum(e, w) for w in windows}
        idx = np.arange(n)
        common = idx >= cfg_w1["common_start_zero_based"]
        for w in windows:
            common &= np.isfinite(stats[w])
        frame = {"ticker": ticker, "year": int(year), "policy": policy, "date": dates}
        for w in windows:
            own = (idx >= w - 1) & np.isfinite(stats[w])
            frame[f"T_w{w}"] = np.where(idx >= w - 1, stats[w], np.nan)
            for ttype, crit in (
                ("pipe", pipe_critical[policy, w]),
                ("point", point_critical[ticker, int(year), policy, w]),
            ):
                for sname, mask in (("common", common), ("own", own)):
                    with np.errstate(invalid="ignore"):
                        hit = mask & (stats[w] >= crit)
                    lab = np.where(mask, np.where(hit, "ALARM", "NO_ALARM"), "NOT_AVAILABLE")
                    frame[f"{ttype}_{sname}_w{w}"] = lab
            frame[f"crit_pipe_w{w}"] = pipe_critical[policy, w]
            frame[f"crit_point_w{w}"] = point_critical[ticker, int(year), policy, w]
        rows.append(pd.DataFrame(frame))
    return pd.concat(rows, ignore_index=True)


def verify_against_w1(
    cus: pd.DataFrame, w1_metrics: pd.DataFrame, windows: list[int], gap: int
) -> pd.DataFrame:
    """재계산 일별 경보로 W1 alarm_metrics 의 alarm_days·episodes·first_alarm_at·n_valid_days 를 재현한다."""
    tmap = {"pipeline_garch_annual_max": "pipe", "t12_pointwise_iid_insample": "point"}
    smap = {"common": "common", "own_pure": "own"}
    out = []
    for (ticker, year, policy), g in cus.groupby(["ticker", "year", "policy"], sort=True):
        g = g.sort_values("date")
        for w in windows:
            for tname, tk in tmap.items():
                for sname, sk in smap.items():
                    lab = g[f"{tk}_{sk}_w{w}"].to_numpy()
                    alarm = lab == "ALARM"
                    ep = episodes(alarm, gap=gap)
                    out.append(
                        {
                            "ticker": ticker,
                            "year": int(year),
                            "policy": policy,
                            "w": w,
                            "threshold_type": tname,
                            "sample_type": sname,
                            "n_valid_days_re": int((lab != "NOT_AVAILABLE").sum()),
                            "alarm_days_re": int(alarm.sum()),
                            "episodes_re": len(ep),
                            "first_alarm_at_re": str(pd.Timestamp(g.date.iloc[ep[0][0]]).date())
                            if ep
                            else "",
                        }
                    )
    re = pd.DataFrame(out)
    m = w1_metrics.copy()
    m["ticker"] = m.ticker.astype(str).str.zfill(6)
    m["first_alarm_at"] = m.first_alarm_at.fillna("").astype(str)
    j = m.merge(
        re, on=["ticker", "year", "policy", "w", "threshold_type", "sample_type"], how="outer", indicator=True
    )
    j["match"] = (
        j._merge.eq("both")
        & j.n_valid_days.eq(j.n_valid_days_re)
        & j.alarm_days.eq(j.alarm_days_re)
        & j.episodes.eq(j.episodes_re)
        & j.first_alarm_at.eq(j.first_alarm_at_re)
    )
    return j


def critical_tables(source_root: Path, run_id: str, w1_root: Path) -> tuple[dict, dict]:
    """W1 동결 파이프라인 임계값 (policy, w) 과 T12 점별 임계값 (ticker, year, policy, w)."""
    pipe = pd.read_csv(
        w1_root / "research/window_study_w1/results/03_synthetic/pipeline/pipeline_thresholds.csv"
    )
    pipe_c = {
        (p, int(w)): float(c) for p, w, c in zip(pipe.policy, pipe.w, pipe.critical_annual_max, strict=True)
    }
    return pipe_c, _t12_critical(source_root, run_id)
