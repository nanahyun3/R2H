"""W4 파이프라인: 원자료 → σ → A·B → 17 그룹 → 17/17 → FINAL → 구간 → 진단·민감도·W2/W3 대조 (계약 W4-lock-1).

가격을 역산할 수 있는 일별 ETF 표(σ·L)는 ``outputs/t18/`` (Git 제외)에,
집계·구간·요약표는 ``research/peer_relative_shock_w4/results/`` 에 쓴다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.multihorizon.core import log_variance_ratio, midrank_past, realized_variance
from r2h.peer_shock.core import (
    and3,
    annualized_vol,
    etf_state_table,
    final_labels,
    global_states,
    group_states,
    intervals,
    pair_ratio_state,
    percent_log_returns_gap,
    verdict,
    year_status,
)

FLOAT = "%.10g"
GZ = {"method": "gzip", "mtime": 0}  # gzip 헤더 시각 0 → 바이트 재현


def load_cfg(root: Path) -> dict:
    return json.loads((root / "configs/t18_peer_shock_w4_v1.json").read_text(encoding="utf-8"))


def load_universe(root: Path, cfg: dict) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """평가 20종과 노출 그룹 17개 (W2 exposure_groups.csv 그대로)."""
    uni = pd.read_csv(root / cfg["exposure_groups"], dtype=str)
    groups: dict[str, list[str]] = {}
    for _, r in uni.iterrows():
        groups.setdefault(r["exposure_group"], []).append(r["ticker"])
    assert len(uni) == cfg["n_etf_expected"] and uni["ticker"].is_unique
    assert len(groups) == cfg["n_groups_expected"]
    return uni, groups


def load_mapping(root: Path, cfg: dict) -> tuple[pd.DataFrame, dict[str, list[str]], dict[str, int]]:
    """동결 Peer 매핑: 채택 Peer 목록과 날짜별 최소 유효 Peer 수 (Tier1 → 1, Tier2 → 2)."""
    m = pd.read_csv(root / cfg["peer_mapping"], dtype={"eval_ticker": str, "peer_ticker": str})
    ad = m[m["adopted"]]
    peers = {e: list(d["peer_ticker"]) for e, d in ad.groupby("eval_ticker", sort=False)}
    min_valid = {
        e: cfg["peer_min_tier1"] if (d["tier"] == 1).all() else cfg["peer_min_tier2"]
        for e, d in ad.groupby("eval_ticker", sort=False)
    }
    return m, peers, min_valid


def load_closes(root: Path, cfg: dict, tickers: list[str], eval_set: set[str]) -> pd.DataFrame:
    """평가 20종의 공통 거래일 달력에 맞춘 종가 표. Peer 의 빈 날은 결측 그대로."""
    def read(t: str) -> pd.Series:
        d = root / (cfg["eval_raw_dir"] if t in eval_set else cfg["peer_raw_dir"])
        f = pd.read_csv(d / f"{t}.csv", parse_dates=["Date"])
        return f.set_index("Date")["Close"].astype(float)

    ev = {t: read(t) for t in sorted(eval_set)}
    cal = None
    for s in ev.values():
        cal = s.index if cal is None else cal.intersection(s.index)
    cal = pd.DatetimeIndex(sorted(cal))
    out = {t: (ev[t] if t in ev else read(t)).reindex(cal) for t in tickers}
    return pd.DataFrame(out, index=cal)


def compute_sigma(closes: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict[str, dict[int, np.ndarray]]]:
    r = closes.apply(lambda c: percent_log_returns_gap(c, cfg["return_scale"]))
    sig = {t: {q: annualized_vol(r[t].to_numpy(), q, cfg["annualization"], cfg["std_ddof"]) for q in cfg["q_main"]}
           for t in closes.columns}
    return r, sig


def run_variant(dates, sig, uni, groups, peers, min_valid, cfg, p: dict, k200_mode: str = "core") -> dict:
    """한 설정(주 정의 또는 민감도)에서 ETF·그룹·전체·FINAL·구간을 모두 계산."""
    mult = {k: float(v) for k, v in cfg["multiplier"].items()}
    etf = pd.concat(
        [etf_state_table(dates, sig, t, peers[t], min_valid[t], mult, cfg["q_main"], p) for t in uni["ticker"]],
        ignore_index=True,
    )
    c1, c2 = cfg["kospi200_core_pair"]
    core = {q: pair_ratio_state(sig[c1][q], sig[c2][q], p) for q in cfg["q_main"]}
    gs = group_states(etf, groups, cfg["kospi200_group"], (c1, c2), core, cfg["q_main"], k200_mode,
                      tuple(cfg["kospi200_aux"]))
    gl = global_states(gs, cfg["n_groups_expected"])
    fin = final_labels(gl, cfg["q_main"])
    # 종료일 다음 날의 AB 그룹 수 (두 기간 중 큰 값) — ALL_GROUPS_NORMALIZED 판정용
    nab = gl.pivot(index="date", columns="q", values="n_AB").max(axis=1).reindex(fin["date"]).to_numpy()
    iv = intervals(fin["date"], fin["FINAL_SHOCK"].to_numpy(), nab)
    return {"etf": etf, "core": core, "groups": gs, "global": gl, "final": fin, "intervals": iv,
            "verdict": verdict(fin, cfg)}


def _period(dates: pd.Series, cfg: dict) -> pd.Series:
    return pd.to_datetime(dates).dt.year.map(lambda y: year_status(int(y), cfg))


def _rate(x: pd.Series) -> float:
    v = x.to_numpy(float)
    ok = np.isfinite(v)
    return float((v[ok] == 1).mean()) if ok.any() else float("nan")


def _mean_run(x: np.ndarray) -> tuple[int, float, int]:
    """1 연속 구간 수·평균 길이·최대 길이 (NA 는 끊김)."""
    runs, cur = [], 0
    for v in x:
        if v == 1:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return len(runs), (float(np.mean(runs)) if runs else 0.0), (max(runs) if runs else 0)


def etf_summaries(main: dict, uni: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """ETF 변동성 요약·상태 요약·영변동성 표 (주 분석기간 기준, 전체 기간 병기)."""
    e = main["etf"].copy()
    e["period"] = _period(e["date"], cfg)
    name = dict(zip(uni["ticker"], uni["name"]))
    vol, st, zero = [], [], []
    for (t, q), d in e.groupby(["ticker", "q"], sort=False):
        pr = d[d["period"] == "PRIMARY"]
        s = pr["sigma"].dropna()
        vol.append({"ticker": t, "name": name[t], "q": q, "n_primary_valid": int(s.size),
                    "sigma_mean": s.mean(), "sigma_median": s.median(), "sigma_p10": s.quantile(0.10),
                    "sigma_p90": s.quantile(0.90), "sigma_max": s.max(),
                    "sigma_max_date": pr.loc[pr["sigma"].idxmax(), "date"].date() if s.size else None,
                    "sigma_last": d["sigma"].iloc[-1], "U_A_last": d["U_A"].iloc[-1]})
        nr, mr, xr = _mean_run(pr["A"].to_numpy())
        bn, bmr, bxr = _mean_run(pr["B"].to_numpy())
        st.append({"ticker": t, "name": name[t], "q": q,
                   "A_rate_primary": _rate(pr["A"]), "B_rate_primary": _rate(pr["B"]),
                   "B_UP_rate_primary": _rate(pr["B_UP"]), "B_DOWN_rate_primary": _rate(pr["B_DOWN"]),
                   "AB_rate_primary": _rate(pr["AB"]),
                   "A_days_primary": int((pr["A"] == 1).sum()), "B_UP_days_primary": int((pr["B_UP"] == 1).sum()),
                   "B_DOWN_days_primary": int((pr["B_DOWN"] == 1).sum()), "AB_days_primary": int((pr["AB"] == 1).sum()),
                   "A_NA_share_primary": float(pr["A"].isna().mean()), "B_NA_share_primary": float(pr["B"].isna().mean()),
                   "A_runs": nr, "A_mean_run": mr, "A_max_run": xr, "B_runs": bn, "B_mean_run": bmr, "B_max_run": bxr,
                   "A_rate_all": _rate(d["A"]), "B_rate_all": _rate(d["B"]), "AB_rate_all": _rate(d["AB"]),
                   "L_median_primary": pr["L"].median(), "L_p05_primary": pr["L"].quantile(0.05),
                   "L_p95_primary": pr["L"].quantile(0.95)})
        vc = d["L_status"].value_counts()
        zero.append({"ticker": t, "name": name[t], "q": q,
                     **{k: int(vc.get(k, 0)) for k in ("OK", "ZERO_VOL_NUMERATOR", "ZERO_VOL_DENOMINATOR",
                                                       "PEER_INSUFFICIENT_ON_DATE", "VOL_MISSING")},
                     "sigma_zero_days": int((d["sigma"] == 0).sum())})
    return pd.DataFrame(vol), pd.DataFrame(st), pd.DataFrame(zero)


def group_summary(main: dict, cfg: dict) -> pd.DataFrame:
    g = main["groups"].copy()
    g["year"] = pd.to_datetime(g["date"]).dt.year
    g["period"] = _period(g["date"], cfg)
    rows = []
    for (grp, q), d in g.groupby(["group", "q"], sort=False):
        pr = d[d["period"] == "PRIMARY"]
        rec = {"group": grp, "q": q}
        for k in ("A", "B", "B_UP", "B_DOWN", "AB"):
            rec[f"{k}_rate_primary"] = _rate(pr[f"GROUP_{k}"])
            rec[f"{k}_days_primary"] = int((pr[f"GROUP_{k}"] == 1).sum())
        rec["AB_NA_share_primary"] = float(pr["GROUP_AB"].isna().mean())
        for y in range(2020, 2027):
            rec[f"AB_days_{y}"] = int((d.loc[d["year"] == y, "GROUP_AB"] == 1).sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def daily_counts(main: dict, cfg: dict) -> pd.DataFrame:
    gl = main["global"].copy()
    gl["period"] = _period(gl["date"], cfg)
    fin = main["final"].set_index("date")
    gl = gl.join(fin[["FINAL_SHOCK"]], on="date")
    gl["date"] = pd.to_datetime(gl["date"]).dt.date
    return gl


def global_by_period(main: dict, cfg: dict) -> pd.DataFrame:
    """기간 지위(2019 기준·2020 파일럿·2021–25 주분석·2026 부분)별 17/17 충족일·최대 참여·NA 일수."""
    g = main["global"].assign(period=_period(main["global"]["date"], cfg))
    f = main["final"].assign(period=_period(main["final"]["date"], cfg)).set_index("date")["FINAL_SHOCK"]
    rows = []
    for (per, q), d in g.groupby(["period", "q"], sort=False):
        rec = {"period": per, "q": q, "days": len(d), "first": pd.Timestamp(d["date"].min()).date(),
               "last": pd.Timestamp(d["date"].max()).date()}
        for k in ("A", "B", "AB"):
            rec[f"days17_{k}"] = int((d[f"GLOBAL_{k}"] == 1).sum())
            rec[f"na_{k}"] = int(d[f"GLOBAL_{k}"].isna().sum())
            rec[f"max_n_{k}"] = int(d[f"n_{k}"].max())
        ff = f.reindex(d["date"])
        rec["final_true"] = int((ff == 1).sum())
        rec["final_na"] = int(ff.isna().sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def max_participation(main: dict, cfg: dict) -> pd.DataFrame:
    """주분석 최대 참여 그룹 수에 도달한 날 전부와 연속 구간 (첫 도달일 하나만 보고하지 않기 위해)."""
    g = main["global"].assign(period=_period(main["global"]["date"], cfg))
    g = g[g["period"] == "PRIMARY"]
    cal = list(pd.DatetimeIndex(sorted(g["date"].unique())))
    pos = {d: i for i, d in enumerate(cal)}
    rows = []
    for q in cfg["q_main"]:
        x = g[g["q"] == q]
        for k in ("A", "B", "AB"):
            m = int(x[f"n_{k}"].max())
            days = sorted(pd.DatetimeIndex(x.loc[x[f"n_{k}"] == m, "date"]))
            spans, s0 = [], days[0]
            for a, b in zip(days[:-1], days[1:]):
                if pos[b] != pos[a] + 1:
                    spans.append(f"{s0.date()}~{a.date()}")
                    s0 = b
            spans.append(f"{s0.date()}~{days[-1].date()}")
            rows.append({"q": q, "state": k, "max_groups": m, "n_days_at_max": len(days),
                         "first_day": days[0].date(), "spans": ";".join(spans)})
    return pd.DataFrame(rows)


def peer_missing_days(closes: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """채택 Peer 의 평가 달력 기준 관측 현황: 첫 관측일, 그 이후 빈 거래일 수 (지시서 §3.1 누락 구간 기록)."""
    ad = mapping[mapping["adopted"]]
    rows = []
    for t in dict.fromkeys(ad["peer_ticker"]):
        c = closes[t]
        first = c.first_valid_index()
        after = c.loc[first:]
        miss = after.index[after.isna()]
        rows.append({"peer_ticker": t, "peer_name": ad.loc[ad["peer_ticker"] == t, "peer_name"].iloc[0],
                     "in_eval20": bool(ad.loc[ad["peer_ticker"] == t, "peer_in_eval20"].iloc[0]),
                     "first_on_calendar": first.date(), "calendar_days_after_first": len(after),
                     "missing_days_after_first": len(miss),
                     "missing_dates": ";".join(str(d.date()) for d in miss[:20])})
    return pd.DataFrame(rows)


def bottleneck(main: dict, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """병목: (1) 그룹별 '그날 AB 가 0 인' 비율과 최대 참여일에 빠진 그룹, (2) 한 그룹을 뺀 16/16 진단 일수.

    (2) 는 라벨이 아니라 '이 그룹이 없었다면' 을 보는 진단이다.
    """
    g = main["groups"].copy()
    g["period"] = _period(g["date"], cfg)
    g = g[g["period"] == "PRIMARY"]
    groups = list(dict.fromkeys(g["group"]))
    rows = []
    gl = main["global"].copy()
    gl["period"] = _period(gl["date"], cfg)
    gl = gl[gl["period"] == "PRIMARY"]
    for q in cfg["q_main"]:
        gq = g[g["q"] == q]
        piv = {k: gq.pivot(index="date", columns="group", values=f"GROUP_{k}") for k in ("A", "B", "AB")}
        glq = gl[gl["q"] == q].set_index("date")
        top = glq["n_AB"].max()
        top_days = glq.index[glq["n_AB"] == top]
        for grp in groups:
            rec = {"q": q, "group": grp}
            for k in ("A", "B", "AB"):
                v = piv[k][grp]
                rec[f"{k}_false_share"] = float((v == 0).mean())
                rec[f"{k}_na_share"] = float(v.isna().mean())
                others = piv[k].drop(columns=[grp])
                rest = and3(*[others[c].to_numpy() for c in others.columns])
                rec[f"loo_{k}_16of16_days"] = int((rest == 1).sum())
                # 나머지 16개가 모두 1 인데 이 그룹만 0 인 날 = 이 그룹이 유일한 병목
                rec[f"sole_blocker_{k}_days"] = int(((rest == 1) & (v.to_numpy() == 0)).sum())
            rec["max_AB_count"] = int(top)
            rec["missing_on_max_AB_days"] = int((piv["AB"].loc[top_days, grp] != 1).sum())
            rec["n_max_AB_days"] = int(len(top_days))
            rows.append(rec)
    bt = pd.DataFrame(rows)
    # 0–17 참여 그룹 수 분포
    dist = []
    for q in cfg["q_main"]:
        glq = gl[gl["q"] == q]
        for k in ("A", "B", "AB"):
            vc = glq[f"n_{k}"].value_counts()
            for c in range(cfg["n_groups_expected"] + 1):
                dist.append({"q": q, "state": k, "n_groups": c, "days_primary": int(vc.get(c, 0))})
    return bt, pd.DataFrame(dist)


def eligibility_audit(main: dict, cfg: dict) -> pd.DataFrame:
    g = main["groups"].copy()
    g["year"] = pd.to_datetime(g["date"]).dt.year
    rows = []
    for (grp, q, y), d in g.groupby(["group", "q", "year"], sort=True):
        rows.append({"group": grp, "q": q, "year": y, "year_status": year_status(int(y), cfg), "days": len(d),
                     "A_evaluable": int(d["GROUP_A"].notna().sum()), "B_evaluable": int(d["GROUP_B"].notna().sum()),
                     "AB_evaluable": int(d["GROUP_AB"].notna().sum())})
    a = pd.DataFrame(rows)
    gl = main["global"].copy()
    gl["year"] = pd.to_datetime(gl["date"]).dt.year
    fin = main["final"].copy()
    fin["year"] = pd.to_datetime(fin["date"]).dt.year
    tot = []
    for (q, y), d in gl.groupby(["q", "year"]):
        tot.append({"group": "__GLOBAL__", "q": q, "year": y, "year_status": year_status(int(y), cfg), "days": len(d),
                    "A_evaluable": int(d["GLOBAL_A"].notna().sum()), "B_evaluable": int(d["GLOBAL_B"].notna().sum()),
                    "AB_evaluable": int(d["GLOBAL_AB"].notna().sum())})
    for y, d in fin.groupby("year"):
        tot.append({"group": "__FINAL__", "q": 0, "year": y, "year_status": year_status(int(y), cfg), "days": len(d),
                    "A_evaluable": np.nan, "B_evaluable": np.nan, "AB_evaluable": int(d["FINAL_SHOCK"].notna().sum())})
    return pd.concat([a, pd.DataFrame(tot)], ignore_index=True)


def peer_quality(main: dict, mapping: pd.DataFrame, cfg: dict, sig: dict, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Peer 품질 사후 진단 (선정에는 쓰지 않음): 유효 Peer 일수·L 의 분산·σ 상관."""
    e = main["etf"]
    e = e.assign(period=_period(e["date"], cfg))
    rows = []
    ad = mapping[mapping["adopted"]]
    for t, d in ad.groupby("eval_ticker", sort=False):
        for q in cfg["q_main"]:
            x = e[(e["ticker"] == t) & (e["q"] == q) & (e["period"] == "PRIMARY")]
            own = pd.Series(sig[t][q], index=dates)
            med = x.set_index("date")["peer_median_adj"]
            ok = x["L"].notna()
            rows.append({"eval_ticker": t, "q": q, "status": d["eval_peer_status"].iloc[0],
                         "grade": d["quality_grade"].iloc[0], "n_adopted": len(d),
                         "peers": "|".join(d["peer_ticker"]), "tiers": "|".join(map(str, d["tier"])),
                         "primary_days": len(x), "L_valid_days": int(ok.sum()),
                         "min_peer_valid": int(x["n_peer_valid"].min()), "L_sd": x["L"].std(),
                         "L_abs_median": x["L"].abs().median(),
                         "sigma_spearman_with_peer_median": own.reindex(med.index).corr(med, method="spearman")})
    return pd.DataFrame(rows)


def w2_reference(dates: pd.DatetimeIndex, r: pd.DataFrame, uni: pd.DataFrame, cfg: dict, w2: dict) -> pd.DataFrame:
    """W2 정의(V = mean r², D = log(V_t/V_{t−q}))로 같은 원자료에서 HIGH_LEVEL·EXPANSION 을 다시 계산 (q=20·60)."""
    out = []
    for t in uni["ticker"]:
        x = r[t].to_numpy()
        for q in cfg["q_main"]:
            v = realized_variance(x, q)
            dd, _, _ = log_variance_ratio(v, q)
            uv, _, _ = midrank_past(v, w2["min_reference_obs"])
            ud, _, _ = midrank_past(dd, w2["min_reference_obs"])
            out.append(pd.DataFrame({"date": dates, "ticker": t, "q": q, "RV_w2_ann": np.sqrt(252 * v),
                                     "U_V_w2": uv, "HIGH_LEVEL_w2": np.where(np.isfinite(uv), (uv >= 0.90) * 1.0, np.nan),
                                     "EXPANSION_w2": np.where(np.isfinite(ud), (ud >= 0.90) * 1.0, np.nan)}))
    return pd.concat(out, ignore_index=True)


def compare_w2_w3(root: Path, main: dict, w2ref: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """계산 정의 차이(σ vs √(252·mean r²), A vs HIGH_LEVEL)와 구간 정의 차이(W2 교차 일별 그룹 수 vs W4 17/17), W3 경보."""
    rows = []
    e = main["etf"].merge(w2ref, on=["date", "ticker", "q"])
    e["period"] = _period(e["date"], cfg)
    pr = e[e["period"] == "PRIMARY"]
    for (t, q), d in pr.groupby(["ticker", "q"], sort=False):
        ok = d["A"].notna() & d["HIGH_LEVEL_w2"].notna()
        a, h = d.loc[ok, "A"] == 1, d.loc[ok, "HIGH_LEVEL_w2"] == 1
        inter, union = int((a & h).sum()), int((a | h).sum())
        rows.append({"block": "calc_definition", "ticker": t, "q": q,
                     "sigma_vs_rv_spearman": d["sigma"].corr(d["RV_w2_ann"], method="spearman"),
                     "sigma_over_rv_median": (d["sigma"] / d["RV_w2_ann"]).median(),
                     "A_days": int(a.sum()), "w2_high_days": int(h.sum()), "both_days": inter,
                     "jaccard_A_vs_w2_high": inter / union if union else np.nan,
                     "agreement_rate": float((a == h).mean())})
    # 구간 정의: W2 HIGH_LEVEL·EXPANSION 교차 일별 n_group (공개표) vs W4 n_A·n_AB
    cd = pd.read_csv(root / "research/multihorizon_w2/results/06/cross_daily_counts.csv", parse_dates=["date"])
    gl = main["global"]
    for ch in ("HIGH_LEVEL", "EXPANSION"):
        c = cd[cd["channel"] == ch].set_index("date")["n_group"]
        for q in cfg["q_main"]:
            g = gl[gl["q"] == q].set_index("date")
            j = g.join(c.rename("w2_n_group"), how="inner")
            j = j[_period(pd.Series(j.index), cfg).to_numpy() == "PRIMARY"]
            rows.append({"block": "interval_definition", "ticker": f"W2_{ch}_n_group", "q": q,
                         "w2_days_ge3_groups": int((j["w2_n_group"] >= 3).sum()),
                         "w2_max_groups": int(j["w2_n_group"].max()),
                         "w4_days_A_17": int((j["GLOBAL_A"] == 1).sum()), "w4_days_AB_17": int((j["GLOBAL_AB"] == 1).sum()),
                         "w4_max_n_A": int(j["n_A"].max()), "w4_max_n_AB": int(j["n_AB"].max()),
                         "spearman_w2_n_vs_w4_n_A": j["w2_n_group"].corr(j["n_A"], method="spearman")})
    # W3: 순차 경보 에피소드·공동 에피소드 기간 동안 W4 상태
    w3 = root / "research/joint_cusum_w3/results/08"
    fin = main["final"].set_index("date")
    for f, s_col, e_col, lab in (("sequential_alarm_episodes.csv", "alarm_start", "alarm_end", "ticker"),
                                 ("joint_episodes.csv", "episode_start_at", "episode_end_at", "subset")):
        ep = pd.read_csv(w3 / f, dtype=str)
        for _, x in ep.iterrows():
            s, en = pd.Timestamp(x[s_col]), pd.Timestamp(x[e_col])
            for q in cfg["q_main"]:
                g = gl[(gl["q"] == q) & (gl["date"] >= s) & (gl["date"] <= en)]
                rows.append({"block": "w3_" + f.split(".")[0], "ticker": x[lab], "q": q, "w3_start": s.date(),
                             "w3_end": en.date(), "w3_status": x.get("day_level_status", "INDIVIDUAL_ALARM"),
                             "w4_max_n_A": int(g["n_A"].max()), "w4_max_n_B": int(g["n_B"].max()),
                             "w4_max_n_AB": int(g["n_AB"].max()),
                             "w4_final_days": int((fin.loc[s:en, "FINAL_SHOCK"] == 1).sum())})
    return pd.DataFrame(rows)


def event_cases(main: dict, w2ref: pd.DataFrame, uni: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    e = main["etf"].merge(w2ref, on=["date", "ticker", "q"])
    gs, gl, fin = main["groups"], main["global"], main["final"]
    grp_of = dict(zip(uni["ticker"], uni["exposure_group"]))
    for ev, spec in cfg["events"].items():
        s, en = map(pd.Timestamp, spec["window"])
        for q in cfg["q_main"]:
            x = e[(e["q"] == q) & (e["date"] >= s) & (e["date"] <= en)]
            for t, d in x.groupby("ticker", sort=False):
                gd = gs[(gs["q"] == q) & (gs["group"] == grp_of[t]) & (gs["date"] >= s) & (gs["date"] <= en)]
                rows.append({"event": ev, "level": "etf", "ticker": t, "group": grp_of[t], "q": q,
                             "sigma_max": d["sigma"].max(), "sigma_max_date": d.loc[d["sigma"].idxmax(), "date"].date(),
                             "U_A_max": d["U_A"].max(), "A_days": int((d["A"] == 1).sum()),
                             "L_min": d["L"].min(), "L_max": d["L"].max(),
                             "B_UP_days": int((d["B_UP"] == 1).sum()), "B_DOWN_days": int((d["B_DOWN"] == 1).sum()),
                             "AB_days": int((d["AB"] == 1).sum()), "group_AB_days": int((gd["GROUP_AB"] == 1).sum()),
                             "w2_high_days": int((d["HIGH_LEVEL_w2"] == 1).sum()),
                             "w2_expansion_days": int((d["EXPANSION_w2"] == 1).sum()), "days": len(d)})
            g = gl[(gl["q"] == q) & (gl["date"] >= s) & (gl["date"] <= en)]
            f = fin[(fin["date"] >= s) & (fin["date"] <= en)]
            rows.append({"event": ev, "level": "global", "ticker": "__ALL__", "group": "__17__", "q": q,
                         "A_days": int((g["GLOBAL_A"] == 1).sum()), "AB_days": int((g["GLOBAL_AB"] == 1).sum()),
                         "max_n_A": int(g["n_A"].max()), "max_n_B": int(g["n_B"].max()), "max_n_AB": int(g["n_AB"].max()),
                         "max_n_A_date": g.loc[g["n_A"].idxmax(), "date"].date(),
                         "final_days": int((f["FINAL_SHOCK"] == 1).sum()), "days": len(g)})
    return pd.DataFrame(rows)


def kospi_aux_table(main: dict, cfg: dict) -> pd.DataFrame:
    """§7.1 레버리지·인버스 보조 진단: 배율 정규화 σ 대 Core Pair 중앙값 비율, A·B 일치도, 4종 상대 변동성 범위."""
    e = main["etf"].assign(period=_period(main["etf"]["date"], cfg))
    e = e[e["period"] == "PRIMARY"]
    c1, c2 = cfg["kospi200_core_pair"]
    rows = []
    for q in cfg["q_main"]:
        x = {t: e[(e["ticker"] == t) & (e["q"] == q)].reset_index(drop=True) for t in [c1, c2, *cfg["kospi200_aux"]]}
        core = main["core"][q].assign(date=main["etf"]["date"].unique())
        core = core[_period(core["date"], cfg) == "PRIMARY"].reset_index(drop=True)
        core_a = and3(x[c1]["A"].to_numpy(), x[c2]["A"].to_numpy())
        adj = np.column_stack([x[t]["sigma_adj"].to_numpy() for t in x])
        rng = adj.max(axis=1) / adj.min(axis=1)
        for t in cfg["kospi200_aux"]:
            a, b = x[t]["A"].to_numpy(), x[t]["B"].to_numpy()
            ok_a = np.isfinite(a) & np.isfinite(core_a)
            ok_b = np.isfinite(b) & np.isfinite(core["B"].to_numpy())
            cb = core["B"].to_numpy()
            ia, ua = ((a == 1) & (core_a == 1) & ok_a).sum(), (((a == 1) | (core_a == 1)) & ok_a).sum()
            ib, ub = ((b == 1) & (cb == 1) & ok_b).sum(), (((b == 1) | (cb == 1)) & ok_b).sum()
            ratio = np.exp(x[t]["L"])
            rows.append({"q": q, "ticker": t, "multiplier": cfg["multiplier"][t],
                         "adj_ratio_to_core_median": float(np.nanmedian(ratio)),
                         "adj_ratio_p05": float(np.nanquantile(ratio, 0.05)), "adj_ratio_p95": float(np.nanquantile(ratio, 0.95)),
                         "A_days": int((a == 1).sum()), "core_A_days": int((core_a == 1).sum()),
                         "A_agreement": float((a[ok_a] == core_a[ok_a]).mean()), "A_jaccard": ia / ua if ua else np.nan,
                         "B_days": int((b == 1).sum()), "core_B_days": int((cb == 1).sum()),
                         "B_UP_days": int((x[t]["B_UP"] == 1).sum()), "B_DOWN_days": int((x[t]["B_DOWN"] == 1).sum()),
                         "B_agreement": float((b[ok_b] == cb[ok_b]).mean()), "B_jaccard": ib / ub if ub else np.nan,
                         "four_range_median": float(np.nanmedian(rng)), "four_range_p95": float(np.nanquantile(rng, 0.95)),
                         "four_range_max": float(np.nanmax(rng))})
    return pd.DataFrame(rows)


def threshold_proximity(main: dict, cfg: dict, band: float = 0.01) -> pd.DataFrame:
    e = main["etf"].assign(period=_period(main["etf"]["date"], cfg))
    e = e[e["period"] == "PRIMARY"]
    rows = []
    for q, d in e.groupby("q"):
        ua, ub = d["U_A"].dropna(), d["U_B"].dropna()
        rows.append({"q": q, "A_near_share": float((ua.sub(cfg["A_upper"]).abs() <= band).mean()),
                     "B_up_near_share": float((ub.sub(cfg["B_upper"]).abs() <= band).mean()),
                     "B_down_near_share": float((ub.sub(cfg["B_lower"]).abs() <= band).mean()), "band": band})
    return pd.DataFrame(rows)


def sensitivity(dates, sig, uni, groups, peers, min_valid, cfg, base: dict) -> tuple[pd.DataFrame, dict]:
    s = cfg["sensitivity"]
    variants = {
        "MAIN": (base, "core"),
        "FIXED_504": ({**base, "max_ref": s["fixed_reference_length"]}, "core"),
        "A_095": ({**base, "A_upper": s["A_upper_alt"]}, "core"),
        "B_2.5": ({**base, "B_lower": s["B_tails_alt"][0], "B_upper": s["B_tails_alt"][1]}, "core"),
        "K200_FOUR": (base, "four"),
    }
    rows, res = [], {}
    for name, (p, mode) in variants.items():
        v = run_variant(dates, sig, uni, groups, peers, min_valid, cfg, p, mode)
        res[name] = v
        gl = v["global"].assign(period=_period(v["global"]["date"], cfg))
        gp = gl[gl["period"] == "PRIMARY"]
        rec = {"variant": name, **{k: v["verdict"][k] for k in v["verdict"]}, "n_intervals": len(v["intervals"])}
        for q in cfg["q_main"]:
            g = gp[gp["q"] == q]
            for k in ("A", "B", "AB"):
                rec[f"q{q}_max_n_{k}"] = int(g[f"n_{k}"].max())
                rec[f"q{q}_days17_{k}"] = int((g[f"GLOBAL_{k}"] == 1).sum())
            rec[f"q{q}_days16plus_AB"] = int((g["n_AB"] >= 16).sum())
            rec[f"q{q}_days15plus_AB"] = int((g["n_AB"] >= 15).sum())
        rows.append(rec)
    return pd.DataFrame(rows), res


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format=FLOAT, lineterminator="\n")


def run(root: Path) -> dict:
    cfg = load_cfg(root)
    w2 = json.loads((root / cfg["w2_config"]).read_text(encoding="utf-8"))
    uni, groups = load_universe(root, cfg)
    mapping, peers, min_valid = load_mapping(root, cfg)
    eval_set = set(uni["ticker"])
    tickers = list(dict.fromkeys(list(uni["ticker"]) + [p for v in peers.values() for p in v]))
    closes = load_closes(root, cfg, tickers, eval_set)
    dates = closes.index
    r, sig = compute_sigma(closes, cfg)
    base = {"A_upper": cfg["A_upper"], "B_lower": cfg["B_lower"], "B_upper": cfg["B_upper"],
            "min_ref": cfg["min_reference_obs"], "max_ref": None}
    sens, res = sensitivity(dates, sig, uni, groups, peers, min_valid, cfg, base)
    main = res["MAIN"]
    w2ref = w2_reference(dates, r, uni, cfg, w2)

    out = root / "research/peer_relative_shock_w4/results"
    priv = root / "outputs/t18"
    priv.mkdir(parents=True, exist_ok=True)
    # 비공개(가격 역산 가능) 일별 표
    main["etf"].to_csv(priv / "daily_etf_states.csv.gz", index=False, float_format=FLOAT, compression=GZ)
    w2ref.to_csv(priv / "daily_w2_reference.csv.gz", index=False, float_format=FLOAT, compression=GZ)
    pd.DataFrame({t: sig[t][q] for t in tickers for q in [20]}, index=dates).to_csv(
        priv / "sigma20_all.csv.gz", float_format=FLOAT, compression=GZ)
    pd.DataFrame({t: sig[t][q] for t in tickers for q in [60]}, index=dates).to_csv(
        priv / "sigma60_all.csv.gz", float_format=FLOAT, compression=GZ)
    closes.to_csv(priv / "closes_aligned.csv.gz", float_format=FLOAT, compression=GZ)
    core_tab = pd.concat([d.assign(date=dates, q=q) for q, d in main["core"].items()], ignore_index=True)
    core_tab.to_csv(priv / "kospi200_core_pair.csv.gz", index=False, float_format=FLOAT, compression=GZ)
    for name, v in res.items():
        if name != "MAIN":
            v["global"].to_csv(priv / f"global_{name}.csv.gz", index=False, float_format=FLOAT, compression=GZ)

    # 공개 집계표 (상태 0/1/NA 와 집계 수치 — 가격 역산 불가)
    vol, st, zero = etf_summaries(main, uni, cfg)
    write_csv(vol, out / "etf_volatility_summary.csv")
    write_csv(st, out / "etf_state_summary.csv")
    write_csv(zero, out / "zero_volatility_audit.csv")
    write_csv(group_summary(main, cfg), out / "group_state_summary.csv")
    gstate = main["groups"].assign(date=lambda d: pd.to_datetime(d["date"]).dt.date)
    write_csv(gstate, out / "group_daily_states.csv")
    write_csv(daily_counts(main, cfg), out / "global_daily_counts.csv")
    fl = main["final"].copy()
    # t 종가로 계산한 라벨은 다음 거래일 장 시작부터만 쓸 수 있다 (마지막 날은 다음 거래일 미상)
    fl["available_from"] = list(pd.to_datetime(fl["date"]).dt.date.astype(str).iloc[1:]) + ["NEXT_TRADING_DAY_UNKNOWN"]
    fl["date"] = pd.to_datetime(fl["date"]).dt.date
    write_csv(fl, out / "final_daily_labels.csv")
    write_csv(kospi_aux_table(main, cfg), out / "kospi200_aux_diagnostics.csv")
    write_csv(main["intervals"], out / "shock_intervals.csv")
    gbp = global_by_period(main, cfg)
    write_csv(gbp, out / "global_by_period.csv")
    write_csv(max_participation(main, cfg), out / "max_participation_days.csv")
    write_csv(peer_missing_days(closes, mapping), out / "peer_missing_days.csv")
    bt, dist = bottleneck(main, cfg)
    write_csv(bt, out / "bottleneck_groups.csv")
    write_csv(dist, out / "participation_distribution.csv")
    write_csv(eligibility_audit(main, cfg), out / "eligibility_audit.csv")
    write_csv(peer_quality(main, mapping, cfg, sig, dates), out / "peer_mapping_quality.csv")
    write_csv(event_cases(main, w2ref, uni, cfg), out / "event_case_studies.csv")
    write_csv(compare_w2_w3(root, main, w2ref, cfg), out / "comparison_w2_w3.csv")
    write_csv(sens, out / "sensitivity_summary.csv")
    write_csv(threshold_proximity(main, cfg), out / "threshold_proximity.csv")
    gp = main["global"][_period(main["global"]["date"], cfg) == "PRIMARY"]
    full = {f"q{q}": {"days": int((gp["q"] == q).sum()),
                      "all17_A_and_B_non_NA_days": int(((gp["q"] == q) & (gp["n_eval_A"] == 17) & (gp["n_eval_B"] == 17)).sum())}
            for q in cfg["q_main"]}
    pil = gbp[gbp["period"] == "PILOT"].set_index("q")
    final = {"verdict": main["verdict"], "primary_fully_evaluable": full,
             "pilot_2020_days17": {f"q{q}": {k: int(pil.loc[q, f"days17_{k}"]) for k in ("A", "B", "AB")} for q in cfg["q_main"]}, "n_intervals": len(main["intervals"]),
             "sensitivity_verdicts": dict(zip(sens["variant"], sens["verdict"])),
             "calendar": [str(dates[0].date()), str(dates[-1].date()), len(dates)],
             "n_peer_tickers": len(tickers) - len(eval_set)}
    (out / "w4_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"cfg": cfg, "main": main, "res": res, "sens": sens, "final": final, "closes": closes, "sig": sig,
            "w2ref": w2ref, "uni": uni, "groups": groups, "mapping": mapping, "peers": peers, "dates": dates}


def results_digest(root: Path) -> dict[str, str]:
    out = root / "research/peer_relative_shock_w4/results"
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*")) if p.is_file()}


if __name__ == "__main__":  # pragma: no cover
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
    res = run(root)
    print(json.dumps(res["final"], ensure_ascii=False, indent=2))
