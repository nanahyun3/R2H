"""연환산변동성 국면 · 이벤트 (12B-lock-1 VOLATILITY_REGIME_DEFINITIONS.md). 모두 t 이전 정보만 쓰는 과거 전용 정의 + 사후 변형."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LEVELS = ("LOW", "MID", "HIGH", "EXTREME")
CHANGES = ("CONTRACTING", "STABLE", "EXPANDING")


def past_expanding_quantiles(x: np.ndarray, qs: tuple[float, ...], min_n: int) -> np.ndarray:
    """x[t] 마다 x[:t] 유효값의 분위 (t 자신 제외). 표본 < min_n 이면 NaN. 반환 (len(qs), n)."""
    n = x.size
    out = np.full((len(qs), n), np.nan)
    vals: list[float] = []
    for t in range(n):
        if len(vals) >= min_n:
            out[:, t] = np.quantile(np.asarray(vals), qs)
        if np.isfinite(x[t]):
            vals.append(float(x[t]))
    return out


def level_label(x: np.ndarray, q: np.ndarray) -> np.ndarray:
    lab = np.full(x.size, "NA", dtype=object)
    ok = np.isfinite(x) & np.isfinite(q).all(axis=0)
    k = (x[None, :] >= q).sum(axis=0)
    lab[ok] = np.asarray(LEVELS, dtype=object)[k[ok]]
    return lab


def regime_table(full: pd.DataFrame, eval_start_date: pd.Timestamp, cfg: dict, anchor_w: int = 20) -> pd.DataFrame:
    """전체(2019 포함) 시장표에서 과거 전용 국면을 계산 후 평가 구간으로 절단."""
    rg = cfg["regimes"]
    a = full[f"annualized_vol_{anchor_w}"].to_numpy(float)
    cuts = tuple(rg["level"]["cuts"])
    ql = past_expanding_quantiles(a, cuts, 252)
    la = np.log(a)
    d5 = la - np.r_[np.full(5, np.nan), la[:-5]]
    d20 = la - np.r_[np.full(20, np.nan), la[:-20]]
    qc = past_expanding_quantiles(d20, (0.2, 0.8), 252)
    q90 = ql[cuts.index(0.9)]
    ch = np.full(a.size, "NA", dtype=object)
    okc = np.isfinite(d20) & np.isfinite(qc).all(axis=0)
    ch[okc] = np.where(d20[okc] >= qc[1, okc], "EXPANDING", np.where(d20[okc] <= qc[0, okc], "CONTRACTING", "STABLE"))
    df = pd.DataFrame({"date": full["date"].to_numpy(), "anchor_w": anchor_w, "anchor": a, "d5": d5, "d20": d20,
                       "level_past": level_label(a, ql), "change_past": ch,
                       "q33_past": ql[0], "q67_past": ql[1], "q90_past": q90, "d20_q20_past": qc[0], "d20_q80_past": qc[1]})
    ev = df[df["date"] >= eval_start_date].reset_index(drop=True)
    # 사후 변형: 평가 구간 전체 분위
    qp = np.quantile(ev["anchor"].dropna(), cuts)
    ev["level_posthoc"] = level_label(ev["anchor"].to_numpy(), np.repeat(qp[:, None], len(ev), axis=1))
    dq = np.quantile(ev["d20"].dropna(), (0.2, 0.8))
    d = ev["d20"].to_numpy()
    ev["change_posthoc"] = np.where(~np.isfinite(d), "NA", np.where(d >= dq[1], "EXPANDING", np.where(d <= dq[0], "CONTRACTING", "STABLE")))
    ev["regime_past"] = np.where((ev["level_past"] == "NA") | (ev["change_past"] == "NA"), "NA", ev["level_past"] + "|" + ev["change_past"])
    # 이벤트 B: 과거 q0.90 아래 20일 이상 → 위로 교차 (전체 표에서 판정)
    above = np.isfinite(q90) & (a >= q90)
    valid = np.isfinite(q90) & np.isfinite(a)
    onset = np.zeros(a.size, bool)
    run = 0
    for t in range(a.size):
        if valid[t] and above[t] and run >= 20:
            onset[t] = True
        run = run + 1 if (valid[t] and not above[t]) else 0
    ev["vol_onset_B"] = onset[df["date"].to_numpy() >= np.datetime64(eval_start_date)]
    return ev


def events_A(path: Path, dates: pd.Series) -> pd.DataFrame:
    """11번 급변 구간 (CUSUM 과 독립 정의). 평가축 위치 i0·i1 을 날짜로 다시 대조."""
    e = pd.read_csv(path, parse_dates=["start", "end", "peak_date"])
    pos = {d: i for i, d in enumerate(pd.to_datetime(dates))}
    e["i_start"] = e["start"].map(pos)
    e["i_end"] = e["end"].map(pos)
    if (e["i_start"] != e["i0"]).any() or (e["i_end"] != e["i1"]).any():
        raise AssertionError("events_11 위치 불일치")
    e["event_set"] = "A_t20"
    return e


def events_B(reg: pd.DataFrame) -> pd.DataFrame:
    i = np.flatnonzero(reg["vol_onset_B"].to_numpy())
    return pd.DataFrame({"interval_id": [f"B_onset_{k:02d}" for k in range(len(i))], "start": reg["date"].iloc[i].to_numpy(),
                         "end": reg["date"].iloc[i].to_numpy(), "i_start": i, "i_end": i, "shock_type": "확대 시작점",
                         "period": np.where(reg["date"].iloc[i].dt.year.to_numpy() == 2020, "PILOT", "PRIMARY"), "event_set": "B_onset"})


def phase_of(rel: int, dur: int) -> str:
    """이벤트 시작 기준 상대일 → 단계 (pre/onset/during/normalization/outside)."""
    if -20 <= rel <= -1:
        return "pre"
    if 0 <= rel <= 5:
        return "onset"
    if 6 <= rel <= dur:
        return "during"
    if dur + 1 <= rel <= dur + 40 and rel > 5:
        return "normalization"
    return "outside"


def window_exits(master: pd.DataFrame, top: int = 10, ws: tuple[int, ...] = (20, 60, 120, 252)) -> pd.DataFrame:
    """|r| 상위 top 일의 이동창 이탈일 d+w (거래일)."""
    r = master["daily_log_return_pct"].to_numpy()
    idx = np.argsort(-np.abs(r), kind="mergesort")[:top]
    rows = []
    for i in sorted(idx):
        for w in ws:
            j = i + w
            rows.append({"shock_date": master["date"].iloc[i], "shock_return_pct": r[i], "w": w,
                         "exit_pos": j, "exit_date": master["date"].iloc[j] if j < len(master) else pd.NaT})
    return pd.DataFrame(rows)
