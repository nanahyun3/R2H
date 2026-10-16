"""H3 — 실현분산 특징과 W1 CUSUM 의 기술적 관계 (계약 §4.6 [A-6]). 같은 수익률에서 나온 값들이라 정확도 검증이 아니다."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def joined(
    features: pd.DataFrame,
    cusum: pd.DataFrame,
    cfg: dict,
    policy: str = "A",
    ttype: str = "pipe",
    sample: str = "common",
) -> pd.DataFrame:
    """(ticker, date) 에서 주 q 의 U_V·D 와 정책별 T_w·경보 상태를 붙인 넓은 표 (주 해석 연도만)."""
    f = features[features.q.isin(cfg["q_variance"])]
    uv = f.pivot_table(index=["ticker", "date"], columns="q", values="U_V").add_prefix("U_V_q")
    dd = f.pivot_table(index=["ticker", "date"], columns="q", values="D").add_prefix("D_q")
    c = cusum[cusum.policy.eq(policy)].set_index(["ticker", "date"])
    t_cols = [f"T_w{w}" for w in cfg["cusum_windows"]]
    lab = c[[f"{ttype}_{sample}_w{w}" for w in cfg["cusum_windows"]]]
    lab.columns = [f"alarm_w{w}" for w in cfg["cusum_windows"]]
    j = uv.join(dd, how="left").join(c[[*t_cols, "year"]].join(lab), how="inner")
    return j[j.year.isin(cfg["core_years"])]


def spearman_matrix(j: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """공통일(정책 A 주 표본) 에서 ETF 별 Spearman ρ(U_V⁽q⁾, T_w), ρ(D⁽q⁾, T_w) 의 긴 표."""
    rows = []
    for ticker, g in j.groupby(level=0):
        for w in cfg["cusum_windows"]:
            ok = g[f"alarm_w{w}"].ne("NOT_AVAILABLE")
            for q in cfg["q_variance"]:
                for var in ("U_V", "D"):
                    col = f"{var}_q{q}"
                    if var == "D" and q == 1:
                        continue
                    x, y = g.loc[ok, col], g.loc[ok, f"T_w{w}"]
                    m = x.notna() & y.notna()
                    rho = spearmanr(x[m], y[m]).statistic if m.sum() >= 30 else np.nan
                    rows.append(
                        {
                            "ticker": ticker,
                            "w": w,
                            "q": q,
                            "variable": var,
                            "n_days": int(m.sum()),
                            "spearman": float(rho),
                        }
                    )
    return pd.DataFrame(rows)


def alarm_contrast(j: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """정책 A 주 임계값 경보일 대 비경보일의 U_V⁽q=w⁾ 분포 (공통일, 2021–2025, 20종 합산 — 날짜 의존 무시한 기술 통계)."""
    rows = []
    for w in cfg["cusum_windows"]:
        lab = j[f"alarm_w{w}"]
        for q in cfg["q_variance"]:
            u = j[f"U_V_q{q}"]
            for state in ("ALARM", "NO_ALARM"):
                x = u[lab.eq(state) & u.notna()]
                rows.append(
                    {
                        "w": w,
                        "q": q,
                        "state": state,
                        "n_days": int(x.size),
                        "n_etf": int(x.index.get_level_values(0).nunique()) if x.size else 0,
                        "median_U_V": float(x.median()) if x.size else np.nan,
                        "share_U_V_ge_090": float((x >= cfg["signal_upper"]).mean()) if x.size else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def event_study(
    features: pd.DataFrame, cusum: pd.DataFrame, cfg: dict, gap: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """정책 A 주 임계값·공통일 CUSUM 에피소드의 첫 경보일 기준 ±K 거래일 U_V·D 평균 궤적 (q=w)."""
    from r2h.svrgarch_etf.rolling import episodes

    k = cfg["event_study_window"]
    events = []
    for (ticker, year), g in cusum[cusum.policy.eq("A")].groupby(["ticker", "year"]):
        g = g.sort_values("date")
        for w in cfg["cusum_windows"]:
            ep = episodes(g[f"pipe_common_w{w}"].eq("ALARM").to_numpy(), gap=gap)
            for s, _ in ep:
                events.append({"ticker": ticker, "year": int(year), "w": w, "alarm_at": g.date.iloc[s]})
    ev = pd.DataFrame(events)
    rows = []
    for t, f in features.groupby("ticker"):
        f = f.sort_values(["q", "date"])
        for _, e in ev[ev.ticker.eq(t)].iterrows():
            fq = f[f.q.eq(e.w)].reset_index(drop=True)
            pos = int(np.flatnonzero(fq.date.eq(e.alarm_at).to_numpy())[0])
            for rel in range(-k, k + 1):
                p = pos + rel
                if 0 <= p < len(fq):
                    rows.append(
                        {
                            "ticker": t,
                            "year": e.year,
                            "w": e.w,
                            "alarm_at": e.alarm_at,
                            "rel_day": rel,
                            "U_V": fq.U_V.iloc[p],
                            "D": fq.D.iloc[p],
                        }
                    )
    return ev, pd.DataFrame(rows)


def level_change_jaccard(overlap_daily: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """ETF 별 고변동성 수준 후보일과 변동성 확대 후보일의 Jaccard (2021–2025) — '수준과 변화가 다른 구간을 강조하는가'."""
    d = overlap_daily[overlap_daily.date.dt.year.isin(cfg["core_years"])]
    rows = []
    for t, g in d.groupby("ticker"):
        a = set(g[g.channel.eq("HIGH_LEVEL") & g.overlap_candidate_day].date)
        b = set(g[g.channel.eq("EXPANSION") & g.overlap_candidate_day].date)
        u = a | b
        rows.append(
            {
                "ticker": t,
                "n_high_days": len(a),
                "n_expansion_days": len(b),
                "n_both": len(a & b),
                "jaccard": len(a & b) / len(u) if u else np.nan,
            }
        )
    return pd.DataFrame(rows)
