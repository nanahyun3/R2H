"""06 단계: 05 의 ETF 별 공통 구간 후보일을 노출 군집·20종 전체로 확장한다 (계약 §4.7 [A-7]–[A-9], H4).

군집 동시성은 탐색적 공통성이다. 자산 간 의존을 보존한 귀무보정은 하지 않는다.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.multihorizon.core import CHANNELS, rank_intervals, runs, sha256, year_status

FLOAT = "%.10g"


def verify_handoff(root: Path, name: str) -> dict:
    """앞 단계 인계 JSON 의 결과·작업 파일 SHA256 을 대조한다."""
    h = json.loads((root / "research/multihorizon_w2/results" / name).read_text(encoding="utf-8"))
    base = root / "research/multihorizon_w2"
    for rel, digest in h["results"].items():
        if sha256(base / rel) != digest:
            raise AssertionError(f"인계 결과 해시 불일치: {rel}")
    for rel, digest in h.get("work_files", {}).items():
        if sha256(root / rel) != digest:
            raise AssertionError(f"인계 작업 파일 해시 불일치: {rel}")
    return h


def exposure_table(universe: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """주 노출 그룹 (KOSPI200 4종 묶음, 나머지 단독 = 17개) 과 미국 주식 2종 묶음 민감도 (16개)."""
    d = universe[["ticker", "name", "category", "exposure_group"]].copy()
    k = set(cfg["exposure_kospi200"])
    if set(d[d.exposure_group.eq("KOSPI200_동일노출")].ticker) != k:
        raise AssertionError("W1 KOSPI200 그룹과 W2 설정 불일치")
    us = set(cfg["exposure_sensitivity_us_equity"])
    d["exposure_group_us"] = np.where(d.ticker.isin(us), "미국주식_2종", d.exposure_group)
    d["nominal_multiplier"] = d.ticker.map(
        {t: float(m) for t, m in cfg["nominal_multiplier"].items()}
    ).fillna(1.0)
    return d


def cross_daily(overlap: pd.DataFrame, expo: pd.DataFrame) -> pd.DataFrame:
    """날짜 × 채널: 후보일 ETF 수, 노출 그룹 수 (그룹 안 1종 이상이면 1), 미국 묶음 민감도, 자산유형 수, 구성원 목록."""
    m = overlap.merge(expo[["ticker", "exposure_group", "exposure_group_us", "category"]], on="ticker")
    c = m[m.overlap_candidate_day]
    g = c.groupby(["channel", "date"])
    out = pd.DataFrame(
        {
            "n_etf": g.ticker.nunique(),
            "n_group": g.exposure_group.nunique(),
            "n_group_us": g.exposure_group_us.nunique(),
            "n_category": g.category.nunique(),
            "members": g.ticker.agg(lambda s: ",".join(sorted(s))),
            "groups": g.exposure_group.agg(lambda s: ",".join(sorted(set(s)))),
        }
    ).reset_index()
    full = overlap[["channel", "date"]].drop_duplicates()
    out = full.merge(out, on=["channel", "date"], how="left")
    for col in ("n_etf", "n_group", "n_group_us", "n_category"):
        out[col] = out[col].fillna(0).astype(int)
    out[["members", "groups"]] = out[["members", "groups"]].fillna("")
    return out.sort_values(["channel", "date"]).reset_index(drop=True)


def cross_intervals(daily: pd.DataFrame, count_col: str, min_count: int, cfg: dict) -> pd.DataFrame:
    """count_col ≥ min_count 인 연속 거래일 = 교차 공통 구간. 순위 = (최대 count, 지속일), 채널 범위, 공동 min."""
    rows = []
    for ch, g in daily.groupby("channel"):
        g = g.sort_values("date").reset_index(drop=True)
        flag = g[count_col].to_numpy() >= min_count
        for s, e in runs(flag):
            seg = g.iloc[s : e + 1]
            members = sorted(set(",".join(seg.members).split(",")) - {""})
            groups = sorted(set(",".join(seg.groups).split(",")) - {""})
            rows.append(
                {
                    "channel": ch,
                    "basis": count_col,
                    "interval_start": str(seg.date.iloc[0].date()),
                    "interval_end": str(seg.date.iloc[-1].date()),
                    "duration_trading_days": e - s + 1,
                    "max_count": int(seg[count_col].max()),
                    "max_n_etf": int(seg.n_etf.max()),
                    "max_n_group": int(seg.n_group.max()),
                    "max_n_category": int(seg.n_category.max()),
                    "members_ever": ",".join(members),
                    "groups_ever": ",".join(groups),
                    "episode_confirmed_at": str(g.date.iloc[e + 1].date())
                    if e + 1 < len(g)
                    else "RIGHT_CENSORED",
                    "start_year": int(seg.date.iloc[0].year),
                }
            )
    iv = pd.DataFrame(rows)
    if iv.empty:
        return iv
    iv["year_status"] = [year_status(y, cfg) for y in iv.start_year]
    iv["rank_in_channel"] = rank_intervals(iv, ["channel"], ("max_count", "duration_trading_days"))
    return iv.sort_values(["channel", "rank_in_channel", "interval_start"]).reset_index(drop=True)


def group_internal(overlap: pd.DataFrame, expo: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """[A-9] 그룹 내부: 같은 그룹 ≥2종 동시 후보일의 연속 구간과, ETF 쌍 후보일 Jaccard (2021–2025)."""
    multi = expo.groupby("exposure_group").ticker.apply(list)
    multi = multi[multi.str.len() >= 2]
    iv_rows, jac_rows = [], []
    core = overlap[overlap.date.dt.year.isin(cfg["core_years"])]
    for grp, members in multi.items():
        sub = overlap[overlap.ticker.isin(members) & overlap.overlap_candidate_day]
        for ch in CHANNELS:
            cnt = sub[sub.channel.eq(ch)].groupby("date").ticker.nunique()
            dates = pd.DatetimeIndex(sorted(overlap.date.unique()))
            cnt = cnt.reindex(dates, fill_value=0)
            for s, e in runs(cnt.to_numpy() >= 2):
                seg = cnt.iloc[s : e + 1]
                mem = sub[sub.channel.eq(ch) & sub.date.isin(seg.index)].ticker.unique()
                iv_rows.append(
                    {
                        "exposure_group": grp,
                        "channel": ch,
                        "interval_start": str(seg.index[0].date()),
                        "interval_end": str(seg.index[-1].date()),
                        "duration_trading_days": e - s + 1,
                        "max_members": int(seg.max()),
                        "members_ever": ",".join(sorted(mem)),
                        "start_year": int(seg.index[0].year),
                        "year_status": year_status(int(seg.index[0].year), cfg),
                    }
                )
            cc = core[core.channel.eq(ch)]
            sets = {t: set(cc[cc.ticker.eq(t) & cc.overlap_candidate_day].date) for t in members}
            for a, b in combinations(sorted(members), 2):
                u = sets[a] | sets[b]
                jac_rows.append(
                    {
                        "exposure_group": grp,
                        "channel": ch,
                        "ticker_a": a,
                        "ticker_b": b,
                        "n_a": len(sets[a]),
                        "n_b": len(sets[b]),
                        "n_both": len(sets[a] & sets[b]),
                        "jaccard": len(sets[a] & sets[b]) / len(u) if u else np.nan,
                    }
                )
    return pd.DataFrame(iv_rows), pd.DataFrame(jac_rows)


def cross_group_jaccard(overlap: pd.DataFrame, expo: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """노출이 다른 ETF 쌍의 후보일 Jaccard (2021–2025) 분포 — 그룹 내부 Jaccard 와 비교용."""
    core = overlap[overlap.date.dt.year.isin(cfg["core_years"]) & overlap.overlap_candidate_day]
    grp = expo.set_index("ticker").exposure_group
    cat = expo.set_index("ticker").category
    rows = []
    for ch in CHANNELS:
        cc = core[core.channel.eq(ch)]
        sets = {t: set(cc[cc.ticker.eq(t)].date) for t in expo.ticker}
        for a, b in combinations(sorted(expo.ticker), 2):
            u = sets[a] | sets[b]
            rows.append(
                {
                    "channel": ch,
                    "ticker_a": a,
                    "ticker_b": b,
                    "same_group": grp[a] == grp[b],
                    "same_category": cat[a] == cat[b],
                    "n_both": len(sets[a] & sets[b]),
                    "jaccard": len(sets[a] & sets[b]) / len(u) if u else np.nan,
                }
            )
    return pd.DataFrame(rows)


def yearly_summary(overlap: pd.DataFrame, expo: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """연도 × 채널: ETF 등가중 후보일 비율과 노출 그룹 등가중 비율 (그룹은 구성원 1종 이상 후보면 후보), 자산유형별 비율."""
    m = overlap.merge(expo[["ticker", "exposure_group", "category"]], on="ticker")
    m["year"] = m.date.dt.year
    etf = (
        m.groupby(["year", "channel", "ticker"])
        .overlap_candidate_day.mean()
        .groupby(["year", "channel"])
        .mean()
    )
    g = m.groupby(["year", "channel", "exposure_group", "date"]).overlap_candidate_day.any()
    grp = g.groupby(["year", "channel", "exposure_group"]).mean().groupby(["year", "channel"]).mean()
    out = pd.DataFrame({"etf_equal_share": etf, "group_equal_share": grp}).reset_index()
    cats = (
        m.groupby(["year", "channel", "category"])
        .overlap_candidate_day.mean()
        .unstack("category")
        .add_prefix("cat_")
    )
    out = out.merge(cats.reset_index(), on=["year", "channel"])
    out["year_status"] = [year_status(int(y), cfg) for y in out.year]
    return out


def global_rank(iv05: pd.DataFrame) -> pd.DataFrame:
    """20종 전체 순위: 05 공통 구간을 채널별로 합쳐 같은 키로 다시 매긴다 (ETF 범위 순위는 보존)."""
    g = iv05.copy()
    g["rank_global_channel"] = rank_intervals(g, ["channel"])
    return g.sort_values(["channel", "rank_global_channel", "interval_start"]).reset_index(drop=True)


def annotate_cross(iv05: pd.DataFrame, cross: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """각 ETF 공통 구간이 그룹 기준 교차 공통 구간과 날짜가 겹치는지, 구간 중 최대 n_group·n_etf."""
    out = iv05.copy()
    flags, ng, ne, cid = [], [], [], []
    by_ch = {ch: g.set_index("date") for ch, g in daily.groupby("channel")}
    for r in out.itertuples(index=False):
        d = by_ch[r.channel].loc[r.interval_start : r.interval_end]
        ng.append(int(d.n_group.max()))
        ne.append(int(d.n_etf.max()))
        c = cross[
            cross.channel.eq(r.channel)
            & (cross.interval_start <= r.interval_end)
            & (cross.interval_end >= r.interval_start)
        ]
        flags.append(bool(len(c)))
        cid.append(";".join(f"{a}~{b}" for a, b in zip(c.interval_start, c.interval_end, strict=True)))
    out["max_n_group_during"] = ng
    out["max_n_etf_during"] = ne
    out["overlaps_cross_group_interval"] = flags
    out["cross_group_intervals"] = cid
    return out


def run_stage06(root: Path, cfg: dict) -> dict:
    h = verify_handoff(root, "05_to_06.json")
    res = root / "research/multihorizon_w2/results/06"
    res.mkdir(parents=True, exist_ok=True)
    base = root / "research/multihorizon_w2/results/05"
    iv05 = pd.read_csv(base / "overlap_intervals.csv", dtype={"ticker": str, "exposure_group": str})
    overlap = pd.read_csv(
        root / "outputs/t14/05/daily_overlap.csv.gz", dtype={"ticker": str}, parse_dates=["date"]
    )
    from r2h.multihorizon.stage05 import load_universe

    expo = exposure_table(load_universe(root), cfg)
    daily = cross_daily(overlap, expo)
    cross_g = cross_intervals(daily, "n_group", cfg["cross_common_min_groups"], cfg)
    cross_e = cross_intervals(daily, "n_etf", cfg["cross_common_min_etfs"], cfg)
    cross_us = cross_intervals(daily, "n_group_us", cfg["cross_common_min_groups"], cfg)
    within_iv, within_jac = group_internal(overlap, expo, cfg)
    pair_jac = cross_group_jaccard(overlap, expo, cfg)
    yearly = yearly_summary(overlap, expo, cfg)
    glob = annotate_cross(global_rank(iv05), cross_g, daily)
    files = {
        "exposure_groups.csv": expo,
        "cross_daily_counts.csv": daily,
        "cross_intervals_group.csv": cross_g,
        "cross_intervals_etf.csv": cross_e,
        "cross_intervals_group_us_sensitivity.csv": cross_us,
        "within_group_intervals.csv": within_iv,
        "within_group_pair_jaccard.csv": within_jac,
        "all_pair_jaccard.csv": pair_jac,
        "yearly_summary.csv": yearly,
        "global_interval_rank.csv": glob,
    }
    for name, frame in files.items():
        frame.to_csv(res / name, index=False, float_format=FLOAT)
    manifest = {
        "stage": "06",
        "upstream_05": h["results"],
        "files_sha256": {f"results/06/{k}": sha256(res / k) for k in files},
    }
    (res / "06_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        **{k.removesuffix(".csv"): v for k, v in files.items()},
        "overlap": overlap,
        "iv05": iv05,
        "handoff05": h,
        "manifest": manifest,
    }
