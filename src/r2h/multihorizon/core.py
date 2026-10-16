"""일별 다중 기간 실현분산·로그분산비·mid-rank 과거 분위·신호·에피소드·공통 구간 (계약 §3–§4).

모든 함수는 순수 계산이며 파일을 읽지 않는다. 시점 규칙은 다음 한 줄로 요약된다:
날짜 t 의 값은 t 종가까지의 수익률만 쓰고, 분위의 기준집합은 t 보다 엄밀히 앞선 날짜의 유효값이다.
"""

from __future__ import annotations

import bisect
import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

D_STATUS = ("OK", "NUMERATOR_ZERO", "DENOMINATOR_ZERO", "BOTH_ZERO", "INSUFFICIENT_HISTORY", "NOT_DEFINED_Q1")
CHANNELS = ("HIGH_LEVEL", "LOW_LEVEL", "EXPANSION", "CONTRACTION")


def load_cfg(root: Path) -> dict:
    return json.loads((root / "configs/t14_multihorizon_w2_v1.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def year_status(year: int, cfg: dict) -> str:
    if year in cfg["core_years"]:
        return "PRIMARY"
    if year == cfg["pilot_year"]:
        return "PILOT"
    if year == cfg["partial_year"]:
        return "PARTIAL_NON_BLIND"
    return "REFERENCE_ONLY"


def percent_log_returns(close: pd.Series, scale: float = 100.0) -> pd.Series:
    """r_t = scale·log(P_t/P_{t−1}); 첫날은 NaN."""
    c = close.astype(float)
    if (c <= 0).any() or c.isna().any():
        raise ValueError("종가에 비양수·결측이 있습니다")
    return scale * np.log(c / c.shift(1))


def realized_variance(r: np.ndarray, q: int) -> np.ndarray:
    """V_t^{(q)} = q 개 r² 의 평균. 창 안에 결측이 하나라도 있으면 NaN."""
    s = pd.Series(np.asarray(r, float) ** 2)
    return s.rolling(q, min_periods=q).mean().to_numpy()


def log_variance_ratio(v: np.ndarray, q: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(D, dV, status). q=1 은 정의하지 않는다. 영분산은 epsilon 없이 NaN + 사유."""
    v = np.asarray(v, float)
    n = v.size
    prev = np.full(n, np.nan)
    prev[q:] = v[:-q]
    dv = v - prev
    status = np.full(n, "INSUFFICIENT_HISTORY", dtype=object)
    d = np.full(n, np.nan)
    if q == 1:
        status[:] = "NOT_DEFINED_Q1"
        return d, dv, status
    ok = np.isfinite(v) & np.isfinite(prev)
    num0 = ok & (v == 0)
    den0 = ok & (prev == 0)
    status[ok] = "OK"
    status[num0 & ~den0] = "NUMERATOR_ZERO"
    status[den0 & ~num0] = "DENOMINATOR_ZERO"
    status[num0 & den0] = "BOTH_ZERO"
    good = ok & ~num0 & ~den0
    if (v[ok] < 0).any() or (prev[ok] < 0).any():
        raise AssertionError("음의 분산")
    d[good] = np.log(v[good] / prev[good])
    return d, dv, status


def midrank_past(
    x: np.ndarray, min_ref: int, max_ref: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """U_t = (#{X<x_t} + 0.5·#{X=x_t}) / n, X = t 이전(엄밀히) 유효값 (max_ref 가 있으면 최근 max_ref 개).

    반환 (U, n_ref, ties). n_ref < min_ref 이거나 x_t 가 NaN 이면 U=NaN.
    """
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    nref = np.zeros(x.size, dtype=int)
    ties = np.zeros(x.size, dtype=int)
    ref: list[float] = []
    fifo: deque[float] = deque()
    for t, val in enumerate(x):
        n = len(ref)
        nref[t] = n
        if np.isfinite(val) and n >= min_ref:
            lo = bisect.bisect_left(ref, val)
            hi = bisect.bisect_right(ref, val)
            ties[t] = hi - lo
            out[t] = (lo + 0.5 * (hi - lo)) / n
        # 현재값은 평가가 끝난 뒤에야 다음 날의 기준집합에 들어간다 (누수 방지).
        if np.isfinite(val):
            bisect.insort(ref, float(val))
            if max_ref is not None:
                fifo.append(float(val))
                if len(fifo) > max_ref:
                    old = fifo.popleft()
                    del ref[bisect.bisect_left(ref, old)]
    return out, nref, ties


def ticker_features(dates: pd.DatetimeIndex, r: np.ndarray, cfg: dict) -> pd.DataFrame:
    """한 ETF 의 (date, q) 긴 표: V, RV, D, dV, D_status, U_V, U_D (확장형·고정길이) 와 기준 수·동점 수."""
    frames = []
    for q in cfg["q_variance"]:
        v = realized_variance(r, q)
        d, dv, st = log_variance_ratio(v, q)
        uv, nv, tv = midrank_past(v, cfg["min_reference_obs"])
        ud, nd, td = midrank_past(d, cfg["min_reference_obs"])
        uvf, _, _ = midrank_past(v, cfg["min_reference_obs"], cfg["fixed_reference_length_sensitivity"])
        udf, _, _ = midrank_past(d, cfg["min_reference_obs"], cfg["fixed_reference_length_sensitivity"])
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "q": q,
                    "V": v,
                    "RV": np.sqrt(v),
                    "D": d,
                    "dV": dv,
                    "D_status": st.astype(str),
                    "U_V": uv,
                    "U_D": ud,
                    "n_ref_V": nv,
                    "n_ref_D": nd,
                    "ties_V": tv,
                    "ties_D": td,
                    "U_V_fixed504": uvf,
                    "U_D_fixed504": udf,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def channel_signal(u: np.ndarray, channel: str, upper: float, lower: float) -> np.ndarray:
    """채널 신호 (bool). U 가 NaN 이면 False — NOT_ESTIMABLE 은 따로 센다."""
    u = np.asarray(u, float)
    with np.errstate(invalid="ignore"):
        if channel in ("HIGH_LEVEL", "EXPANSION", "DAILY_SHOCK"):
            return np.isfinite(u) & (u >= upper)
        if channel in ("LOW_LEVEL", "CONTRACTION"):
            return np.isfinite(u) & (u <= lower)
    raise ValueError(channel)


def channel_source(channel: str) -> str:
    return "U_D" if channel in ("EXPANSION", "CONTRACTION") else "U_V"


def runs(flag: np.ndarray) -> list[tuple[int, int]]:
    """연속 True 구간 (시작, 끝) — 비신호일 병합 없음 (계약 §4.3)."""
    f = np.asarray(flag, bool)
    if not f.any():
        return []
    padded = np.concatenate([[False], f, [False]])
    diff = np.diff(padded.astype(int))
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1) - 1
    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def _confirmed(dates: pd.DatetimeIndex, end: int) -> str:
    return str(dates[end + 1].date()) if end + 1 < len(dates) else "RIGHT_CENSORED"


def signal_matrix(
    feat: pd.DataFrame, cfg: dict, upper: float | None = None, lower: float | None = None, u_suffix: str = ""
) -> dict[str, pd.DataFrame]:
    """채널별 (date × q) bool 표와 NOT_ESTIMABLE 표. q=1 은 DAILY_SHOCK 만."""
    up = cfg["signal_upper"] if upper is None else upper
    lo = cfg["signal_lower"] if lower is None else lower
    out: dict[str, pd.DataFrame] = {}
    for ch in CHANNELS:
        col = channel_source(ch) + u_suffix
        wide = feat.pivot(index="date", columns="q", values=col)[cfg["q_main_overlap"]]
        out[ch] = pd.DataFrame(
            channel_signal(wide.to_numpy(), ch, up, lo), index=wide.index, columns=wide.columns
        )
        out[ch + "__estimable"] = wide.notna()
    w1 = feat[feat.q.eq(cfg["q_daily_shock"])].set_index("date")["U_V" + u_suffix]
    out["DAILY_SHOCK"] = pd.DataFrame(
        {1: channel_signal(w1.to_numpy(), "DAILY_SHOCK", up, lo)}, index=w1.index
    )
    out["DAILY_SHOCK__estimable"] = pd.DataFrame({1: w1.notna().to_numpy()}, index=w1.index)
    return out


def period_episodes(ticker: str, sig: dict[str, pd.DataFrame], feat: pd.DataFrame) -> pd.DataFrame:
    """ETF·q·채널별 연속일 에피소드."""
    rows = []
    for ch in (*CHANNELS, "DAILY_SHOCK"):
        mat = sig[ch]
        dates = pd.DatetimeIndex(mat.index)
        for q in mat.columns:
            sub = feat[feat.q.eq(q)].set_index("date").reindex(dates)
            src = sub[channel_source(ch)].to_numpy()
            for k, (s, e) in enumerate(runs(mat[q].to_numpy())):
                seg = src[s : e + 1]
                rows.append(
                    {
                        "ticker": ticker,
                        "channel": ch,
                        "q": int(q),
                        "episode_no": k + 1,
                        "episode_start": str(dates[s].date()),
                        "episode_end": str(dates[e].date()),
                        "duration_trading_days": e - s + 1,
                        "episode_confirmed_at": _confirmed(dates, e),
                        "estimated_change_at": "NOT_ESTIMATED",
                        "extreme_U": float(
                            np.nanmax(seg)
                            if ch in ("HIGH_LEVEL", "EXPANSION", "DAILY_SHOCK")
                            else np.nanmin(seg)
                        ),
                        "start_year": int(dates[s].year),
                    }
                )
    return pd.DataFrame(rows)


def overlap_intervals(
    ticker: str,
    sig: dict[str, pd.DataFrame],
    feat: pd.DataFrame,
    cfg: dict,
    cusum_alarm: dict[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(일별 중첩 수 표, 공통 구간 표). 공통 구간 = overlap_count ≥ 3 인 연속 거래일 (계약 §4.4).

    cusum_alarm: 이름 → (date × alarm_w{w}) 상태표. 'main' 은 접두사 없이, 나머지는 'cusum_{이름}_' 열로 붙인다.
    """
    groups = cfg["horizon_groups"]
    daily_rows = []
    rows = []
    shock = sig["DAILY_SHOCK"][1]
    uv = feat.pivot(index="date", columns="q", values="U_V")[cfg["q_main_overlap"]]
    ud = feat.pivot(index="date", columns="q", values="U_D")[cfg["q_main_overlap"]]
    dd = feat.pivot(index="date", columns="q", values="D")[cfg["q_main_overlap"]]
    for ch in CHANNELS:
        mat = sig[ch]
        dates = pd.DatetimeIndex(mat.index)
        cnt = mat.sum(axis=1).to_numpy()
        est = sig[ch + "__estimable"].sum(axis=1).to_numpy()
        cand = cnt >= cfg["overlap_min_count"]
        daily_rows.append(
            pd.DataFrame(
                {
                    "ticker": ticker,
                    "channel": ch,
                    "date": dates,
                    "overlap_count": cnt,
                    "n_estimable_q": est,
                    "overlap_candidate_day": cand,
                }
            )
        )
        for s, e in runs(cand):
            block = mat.iloc[s : e + 1]
            ever = [int(q) for q in block.columns if block[q].any()]
            atmax_row = block.iloc[int(np.argmax(cnt[s : e + 1]))]
            at_max = [int(q) for q in block.columns if atmax_row[q]]
            part = {g: any(q in ever for q in qs) for g, qs in groups.items()}
            row = {
                "ticker": ticker,
                "channel": ch,
                "interval_start": str(dates[s].date()),
                "interval_end": str(dates[e].date()),
                "duration_trading_days": e - s + 1,
                "max_overlap_count": int(cnt[s : e + 1].max()),
                "mean_overlap_count": float(cnt[s : e + 1].mean()),
                "active_q_ever": ",".join(map(str, ever)),
                "active_q_at_max": ",".join(map(str, at_max)),
                "short": part["short"],
                "mid": part["mid"],
                "long": part["long"],
                "n_horizon_groups": int(sum(part.values())),
                "max_U_V": float(np.nanmax(uv.iloc[s : e + 1].to_numpy())),
                "max_U_D": float(np.nanmax(ud.iloc[s : e + 1].to_numpy()))
                if np.isfinite(ud.iloc[s : e + 1].to_numpy()).any()
                else np.nan,
                "max_D": float(np.nanmax(dd.iloc[s : e + 1].to_numpy()))
                if np.isfinite(dd.iloc[s : e + 1].to_numpy()).any()
                else np.nan,
                "min_D": float(np.nanmin(dd.iloc[s : e + 1].to_numpy()))
                if np.isfinite(dd.iloc[s : e + 1].to_numpy()).any()
                else np.nan,
                "daily_shock_in_interval": bool(shock.iloc[s : e + 1].any()),
                "episode_confirmed_at": _confirmed(dates, e),
                "estimated_change_at": "NOT_ESTIMATED",
                "start_year": int(dates[s].year),
                "end_year": int(dates[e].year),
            }
            for vname, frame in (cusum_alarm or {}).items():
                row.update(
                    _cusum_overlap(
                        frame.reindex(dates[s : e + 1]), cfg, "" if vname == "main" else f"{vname}_"
                    )
                )
            rows.append(row)
    return pd.concat(daily_rows, ignore_index=True), pd.DataFrame(rows)


def _cusum_overlap(seg: pd.DataFrame, cfg: dict, prefix: str) -> dict:
    """구간 안 CUSUM 경보 창·계산 가능 창·계산 가능 일수 비율.

    일부만 덮인 구간이 '무경보' 로 읽히지 않게 커버리지를 함께 둔다.
    """
    ws = cfg["cusum_windows"]
    alarm_w = [int(w) for w in ws if (seg[f"alarm_w{w}"] == "ALARM").any()]
    avail_w = [int(w) for w in ws if seg[f"alarm_w{w}"].isin(["ALARM", "NO_ALARM"]).any()]
    avail_day = np.zeros(len(seg), bool)
    for w in ws:
        avail_day |= seg[f"alarm_w{w}"].isin(["ALARM", "NO_ALARM"]).to_numpy()
    first = [seg.index[seg[f"alarm_w{w}"].eq("ALARM").to_numpy()][0] for w in alarm_w]
    p = "cusum_" + prefix
    return {
        p + "alarm_w": ",".join(map(str, alarm_w)) if alarm_w else ("NONE" if avail_w else "NOT_AVAILABLE"),
        p + "available_w": ",".join(map(str, avail_w)),
        p + "available_days": int(avail_day.sum()),
        p + "coverage": float(avail_day.mean()) if len(seg) else np.nan,
        p + "first_alarm_in_interval": str(min(first).date()) if first else "",
    }


def rank_intervals(
    iv: pd.DataFrame, by: list[str], keys: tuple[str, str] = ("max_overlap_count", "duration_trading_days")
) -> pd.Series:
    """사전 순위 키 (내림차순 사전식) 의 공동 순위 (min). by 범위 안에서 매긴다."""
    if iv.empty:
        return pd.Series(dtype=int)
    k1, k2 = keys
    composite = iv[k1].astype(float) * 100000 + iv[k2].astype(float)
    if not by:
        return composite.rank(method="min", ascending=False).astype(int)
    return composite.groupby([iv[b] for b in by]).rank(method="min", ascending=False).astype(int)
