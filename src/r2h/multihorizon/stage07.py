"""07 단계: 공통 구간의 가격 반응, 같은 날짜 ETF 상대 움직임, CUSUM–가격 시점 관계, CNN 후보 인계 (계약 §3-4, §4.8–§4.9, H5).

시점 규칙:
- 과거 h 일 값(`C`, `Z_*`, `U_C`)은 t 종가까지의 수익률만 쓴다 → t 종가 이후 이용 가능.
- 미래 h 일 값(`fwd_*`)은 t+1…t+h 수익률을 쓴다 → t+h 종가 이후에만 알 수 있는 사후 결과.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.multihorizon.core import midrank_past, sha256
from r2h.multihorizon.cusum import load_daily_cache
from r2h.multihorizon.stage05 import load_prices, load_universe
from r2h.multihorizon.stage06 import verify_handoff

FLOAT = "%.10g"
GZ = {"method": "gzip", "mtime": 0}  # gzip 헤더 시각을 0 으로 고정 (바이트 재현)


def trailing_sum(x: np.ndarray, h: int) -> np.ndarray:
    """Σ_{s=t−h+1}^{t} x_s (h 개 모두 유한해야 함)."""
    return pd.Series(np.asarray(x, float)).rolling(h, min_periods=h).sum().to_numpy()


def forward_sum(x: np.ndarray, h: int) -> np.ndarray:
    """Σ_{s=t+1}^{t+h} x_s (자료 끝을 넘으면 NaN)."""
    tr = trailing_sum(x, h)
    out = np.full(len(tr), np.nan)
    out[: len(tr) - h] = tr[h:]
    return out


def price_features(
    dates: pd.DatetimeIndex, r: np.ndarray, vhat: dict[str, np.ndarray], cfg: dict
) -> pd.DataFrame:
    """(date, h) 긴 표: 과거 C·Z(정책 3종)·U_C, 미래 R·고정분산 대용 Z·사후 Z (정책 A)."""
    frames = []
    pos = {p: np.where(np.isfinite(v) & (v > 0), v, np.nan) for p, v in vhat.items()}
    for h in cfg["h_price"]:
        c = trailing_sum(r, h)
        frame = {"date": dates, "h": h, "C": c}
        for p, v in pos.items():
            frame[f"Z_{p}"] = c / np.sqrt(trailing_sum(v, h))
        u, n, _ = midrank_past(c, cfg["min_reference_obs"])
        frame["U_C"] = u
        frame["n_ref_C"] = n
        fwd = forward_sum(r, h)
        frame["fwd_R"] = fwd
        frame["fwd_Zfix_A"] = fwd / np.sqrt(h * pos["A"])
        frame["fwd_Zpost_A"] = fwd / np.sqrt(forward_sum(pos["A"], h))
        idx = np.arange(len(dates)) + h
        frame["fwd_available_at"] = [
            str(dates[i].date()) if i < len(dates) else "NOT_AVAILABLE_DATA_END" for i in idx
        ]
        frames.append(pd.DataFrame(frame))
    return pd.concat(frames, ignore_index=True)


def relative_moves(pf: pd.DataFrame, expo: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """같은 날짜·같은 h 의 상대 움직임 4종 + 자산유형 상대 ([A-11]·[A-12])."""
    mult = expo.set_index("ticker").nominal_multiplier.to_dict()
    cat = expo.set_index("ticker").category.to_dict()
    out = []
    for h, g in pf.groupby("h"):
        c = g.pivot(index="date", columns="ticker", values="C")
        z = g.pivot(index="date", columns="ticker", values="Z_A")
        adj = c.div(pd.Series(mult)[c.columns], axis=1)
        tick = list(c.columns)
        for t in tick:
            others = [x for x in tick if x != t]
            other_cat = [x for x in tick if cat[x] != cat[t]]
            frame = pd.DataFrame(
                {
                    "ticker": t,
                    "date": c.index,
                    "h": h,
                    "rel_simple": c[t] - c[others].median(axis=1),
                    "rel_std": z[t] - z[others].median(axis=1),
                    "rel_exposure_adj": adj[t] - adj[others].median(axis=1),
                    "rel_cross_asset": c[t] - c[other_cat].median(axis=1),
                }
            )
            if t in cfg["exposure_kospi200"]:
                if t == "069500":
                    frame["rel_same_exposure"] = (c["102110"] - c["069500"]).to_numpy()
                else:
                    frame["rel_same_exposure"] = (c[t] - mult[t] * c["069500"]).to_numpy()
            else:
                frame["rel_same_exposure"] = np.nan
            out.append(frame.reset_index(drop=True))
    return pd.concat(out, ignore_index=True)


def interval_reactions(
    iv: pd.DataFrame, r_wide: pd.DataFrame, vhat_a: pd.DataFrame, expo: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """구간별 사전(시작 전날까지 h 일) · 구간 중 · 사후(끝 다음날부터 h 일) 누적 로그수익률과 상대값."""
    dates = r_wide.index
    cols = list(r_wide.columns)
    mult = expo.set_index("ticker").nominal_multiplier.reindex(cols).to_numpy()
    cat = expo.set_index("ticker").category.reindex(cols).to_numpy()
    cum = r_wide.cumsum().to_numpy()  # cum[t] − cum[s] = Σ_{s+1..t} r
    va = vhat_a.reindex(columns=cols).to_numpy()
    rows = []
    for row in iv.itertuples(index=False):
        j = cols.index(row.ticker)
        oth = np.arange(len(cols)) != j
        oc = cat != cat[j]
        s = dates.get_loc(pd.Timestamp(row.interval_start))
        e = dates.get_loc(pd.Timestamp(row.interval_end))
        rec = {
            "interval_id": row.interval_id,
            "ticker": row.ticker,
            "channel": row.channel,
            "interval_start": row.interval_start,
            "interval_end": row.interval_end,
            "year_status": row.year_status,
        }
        if s >= 1:
            dur = cum[e] - cum[s - 1]
            rec["during_C"] = float(dur[j])
            rec["during_rel_simple"] = float(dur[j] - np.median(dur[oth]))
            rec["during_rel_exposure_adj"] = float(dur[j] / mult[j] - np.median(dur[oth] / mult[oth]))
            rec["during_rel_cross_asset"] = float(dur[j] - np.median(dur[oc]))
        for h in cfg["h_price"]:
            if s - h >= 1:
                pre = cum[s - 1] - cum[s - 1 - h]
                rec[f"pre_C_h{h}"] = float(pre[j])
                rec[f"pre_rel_h{h}"] = float(pre[j] - np.median(pre[oth]))
            if e + h < len(dates):
                post = cum[e + h] - cum[e]
                rec[f"post_R_h{h}"] = float(post[j])
                rec[f"post_rel_h{h}"] = float(post[j] - np.median(post[oth]))
                v_e = va[e, j]
                vf = va[e + 1 : e + h + 1, j]
                rec[f"post_Zfix_A_h{h}"] = (
                    float(post[j] / np.sqrt(h * v_e)) if np.isfinite(v_e) and v_e > 0 else np.nan
                )
                rec[f"post_Zpost_A_h{h}"] = (
                    float(post[j] / np.sqrt(vf.sum())) if np.isfinite(vf).all() and (vf > 0).all() else np.nan
                )
                rec[f"post_available_at_h{h}"] = str(dates[e + h].date())
            else:
                rec[f"post_available_at_h{h}"] = "NOT_AVAILABLE_DATA_END"
        rows.append(rec)
    return pd.DataFrame(rows)


def path_panel(iv: pd.DataFrame, r_wide: pd.DataFrame, k: int = 60) -> pd.DataFrame:
    """구간 시작일 기준 −k…+k 거래일 누적 로그수익률 경로 (시작 전날 종가 = 0) 와 같은 날 나머지 19종 중앙값 대비."""
    dates = r_wide.index
    cols = list(r_wide.columns)
    cum = r_wide.cumsum().to_numpy()
    rows = []
    for row in iv.itertuples(index=False):
        s = dates.get_loc(pd.Timestamp(row.interval_start))
        if s - 1 - k < 0:
            continue
        j = cols.index(row.ticker)
        hi = min(s + k, len(dates) - 1)
        seg = cum[s - 1 - k : hi + 1] - cum[s - 1]
        others = np.delete(seg, j, axis=1)
        rows.append(
            pd.DataFrame(
                {
                    "interval_id": row.interval_id,
                    "channel": row.channel,
                    "rel_day": np.arange(-k, -k + len(seg)),
                    "path": seg[:, j],
                    "path_rel": seg[:, j] - np.median(others, axis=1),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def cusum_price(cus: pd.DataFrame, pf: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """정책 A 주 CUSUM 계산 가능일의 과거 20일 C·Z 와 미래 20일 R (사후), 에피소드 첫 경보 표시."""
    from r2h.svrgarch_etf.rolling import episodes

    p20 = pf[pf.h.eq(20)][["ticker", "date", "C", "Z_A", "fwd_R"]].rename(
        columns={"C": "C20", "Z_A": "Z20_A", "fwd_R": "fwd_R20"}
    )
    parts = []
    for (t, y), g in cus[cus.policy.eq("A")].groupby(["ticker", "year"]):
        g = g.sort_values("date").reset_index(drop=True)
        for w in cfg["cusum_windows"]:
            lab = g[f"pipe_common_w{w}"]
            first = np.zeros(len(g), bool)
            for st, _ in episodes(lab.eq("ALARM").to_numpy(), gap=cfg["cusum_episode_gap_non_alarm_days"]):
                first[st] = True
            ok = lab.ne("NOT_AVAILABLE").to_numpy()
            parts.append(
                pd.DataFrame(
                    {
                        "ticker": t,
                        "year": int(y),
                        "w": w,
                        "date": g.date[ok].to_numpy(),
                        "is_first_alarm": first[ok],
                        "is_alarm_day": lab.eq("ALARM").to_numpy()[ok],
                    }
                )
            )
    return pd.concat(parts, ignore_index=True).merge(p20, on=["ticker", "date"], how="left")


def cnn_candidates(
    iv: pd.DataFrame, react: pd.DataFrame, feat_start: pd.DataFrame, cfg: dict, source_commits: str
) -> pd.DataFrame:
    """사용자 §10 필수 22개 필드를 담은 CNN 특징학습 후보 구간 표. 정답 라벨 열은 만들지 않는다."""
    m = iv.merge(
        react,
        on=["interval_id", "ticker", "channel", "interval_start", "interval_end", "year_status"],
        how="left",
    )
    m = m.merge(feat_start, on=["ticker", "interval_start"], how="left")
    out = pd.DataFrame(
        {
            "candidate_id": m.interval_id,
            "ticker": m.ticker,
            "exposure_group": m.exposure_group,
            "episode_state": m.channel,
            "episode_start": m.interval_start,
            "episode_end": m.interval_end,
            "available_at": m.interval_start + " close",
            "episode_confirmed_at": m.episode_confirmed_at,
            "estimated_change_at": m.estimated_change_at,
            "active_q": m.active_q_ever,
            "max_overlap_count": m.max_overlap_count,
            "duration_trading_days": m.duration_trading_days,
            "rv_max_U_V": m.max_U_V,
            "rv_max_U_D": m.max_U_D,
            "rv_max_D": m.max_D,
            "rv_min_D": m.min_D,
            "rv_n_horizon_groups": m.n_horizon_groups,
            "rv_short_mid_long": m.short.astype(int).astype(str)
            + m.mid.astype(int).astype(str)
            + m["long"].astype(int).astype(str),
            "rv_daily_shock_in_interval": m.daily_shock_in_interval,
            "rel_max_n_group_during": m.max_n_group_during,
            "rel_max_n_etf_during": m.max_n_etf_during,
            "rel_overlaps_cross_group_interval": m.overlaps_cross_group_interval,
            "rel_U_V20_minus_cross_median_at_start": m.rel_U_V20_at_start,
            "px_pre_C_h20": m.get("pre_C_h20"),
            "px_pre_rel_h20": m.get("pre_rel_h20"),
            "px_during_C": m.during_C,
            "px_during_rel_simple": m.during_rel_simple,
            "px_during_rel_exposure_adj": m.during_rel_exposure_adj,
            "px_post_R_h20_POSTHOC": m.get("post_R_h20"),
            "px_post_available_at_h20": m.get("post_available_at_h20"),
            "cusum_w": m.cusum_alarm_w,
            "cusum_coverage": m.cusum_coverage,
            "cusum_alarm_at": m.cusum_first_alarm_in_interval.fillna(""),
            "cusum_statistic": m.cusum_T_first,
            "cusum_statistic_w": m.cusum_T_first_w,
            "cusum_threshold_type": "pipeline_garch_annual_max",
            "cusum_policy_sample": "A·common",
            "is_exploratory_candidate": True,
            "source_commit": source_commits,
            "protocol_version": cfg["protocol_version"],
            "year_status": m.year_status,
        }
    )
    return out


def run_stage07(root: Path, source_root: Path, cfg: dict, source_commits: str) -> dict:
    h = verify_handoff(root, "06_to_07.json")
    res = root / "research/multihorizon_w2/results/07"
    work = root / "outputs/t14/07"
    res.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    uni = load_universe(root)
    expo = pd.read_csv(
        root / "research/multihorizon_w2/results/06/exposure_groups.csv", dtype={"ticker": str}
    )
    iv = pd.read_csv(
        root / "research/multihorizon_w2/results/06/global_interval_rank.csv", dtype={"ticker": str}
    )
    prices = load_prices(root, uni)
    pf_all, r_cols, v_cols = [], {}, {}
    for t in uni.ticker:
        p = prices[t]
        dates = pd.DatetimeIndex(p.Date)
        r = (cfg["return_scale"] * np.log(p.Close / p.Close.shift(1))).to_numpy()
        daily = load_daily_cache(source_root, cfg["t12_run_id"], t)
        base = daily[daily.window.eq(0)]
        vh = {
            pol: base[base.policy.eq(pol)].set_index("date").vhat.reindex(dates).to_numpy()
            for pol in ("A", "B", "base")
        }
        f = price_features(dates, r, vh, cfg)
        f.insert(0, "ticker", t)
        pf_all.append(f)
        r_cols[t] = pd.Series(r, index=dates)
        v_cols[t] = pd.Series(vh["A"], index=dates)
    pf = pd.concat(pf_all, ignore_index=True)
    r_wide = pd.DataFrame(r_cols)
    vhat_a = pd.DataFrame(v_cols)
    rel = relative_moves(pf, expo, cfg)
    react = interval_reactions(iv, r_wide, vhat_a, expo, cfg)
    paths = path_panel(iv, r_wide)
    cus = pd.read_csv(root / "outputs/t14/05/daily_cusum.csv.gz", dtype={"ticker": str}, parse_dates=["date"])
    cp = cusum_price(cus, pf, cfg)
    # CNN 인계용: 시작일의 U_V(q=20) 횡단면 상대값, 첫 경보일의 T
    feat = pd.read_csv(
        root / "outputs/t14/05/daily_features.csv.gz", dtype={"ticker": str}, parse_dates=["date"]
    )
    u20 = feat[feat.q.eq(20)].pivot(index="date", columns="ticker", values="U_V")
    relu = u20.sub(u20.median(axis=1), axis=0)
    fs = pd.DataFrame(
        {
            "ticker": iv.ticker,
            "interval_start": iv.interval_start,
            "rel_U_V20_at_start": [
                relu.loc[pd.Timestamp(s), t] for t, s in zip(iv.ticker, iv.interval_start, strict=True)
            ],
        }
    )
    fs = fs.drop_duplicates(["ticker", "interval_start"])
    ca = cus[cus.policy.eq("A")].set_index(["ticker", "date"])
    tf, tw = [], []
    for r_ in iv.itertuples(index=False):
        if isinstance(r_.cusum_first_alarm_in_interval, str) and r_.cusum_first_alarm_in_interval:
            x = ca.loc[(r_.ticker, pd.Timestamp(r_.cusum_first_alarm_in_interval))]
            ws = [w for w in cfg["cusum_windows"] if x[f"pipe_common_w{w}"] == "ALARM"]
            tf.append(float(x[f"T_w{ws[0]}"]))
            tw.append(int(ws[0]))
        else:
            tf.append(np.nan)
            tw.append(np.nan)
    iv2 = iv.assign(cusum_T_first=tf, cusum_T_first_w=tw)
    cnn = cnn_candidates(iv2, react, fs, cfg, source_commits)
    # 가격을 역산할 수 있는 일별 20일 누적수익률은 Git 제외 폴더에만 두고, 결과 폴더에는 요약만 쓴다.
    cp_core = cp[cp.year.isin(cfg["core_years"])]
    cp_sum = (
        cp_core.assign(
            group=np.where(
                cp_core.is_first_alarm,
                "first_alarm",
                np.where(cp_core.is_alarm_day, "alarm_other", "no_alarm"),
            )
        )
        .groupby(["w", "group"])
        .agg(
            n=("C20", "size"),
            n_etf=("ticker", "nunique"),
            median_C20=("C20", "median"),
            share_C20_neg=("C20", lambda x: float((x < 0).mean())),
            median_absZ20_A=("Z20_A", lambda x: float(x.abs().median())),
            median_fwd_R20=("fwd_R20", "median"),
            n_fwd=("fwd_R20", lambda x: int(x.notna().sum())),
        )
        .reset_index()
    )
    # h=1·3 의 구간 전후 값은 특정 날짜의 일별 수익률과 같아 Git 제외 폴더에만 둔다.
    short_cols = [c for c in react.columns if re.search(r"_h(1|3)$", c)]
    react.to_csv(
        work / "interval_price_reaction_full.csv.gz", index=False, compression=GZ, float_format=FLOAT
    )
    files = {
        "interval_price_reaction.csv": react.drop(columns=short_cols),
        "interval_path_mean.csv": paths.merge(iv[["interval_id", "year_status"]], on="interval_id")
        .query("year_status == 'PRIMARY'")
        .groupby(["channel", "rel_day"])[["path", "path_rel"]]
        .agg(["mean", "median", "count"]),
        "cusum_alarm_price_summary.csv": cp_sum,
        "cnn_candidate_intervals_w2.csv": cnn,
    }
    for name, frame in files.items():
        frame.to_csv(res / name, index=name == "interval_path_mean.csv", float_format=FLOAT)
    pf.to_csv(work / "daily_price_features.csv.gz", index=False, compression=GZ, float_format=FLOAT)
    rel.to_csv(work / "daily_relative_moves.csv.gz", index=False, compression=GZ, float_format=FLOAT)
    cp.to_csv(work / "cusum_alarm_price_daily.csv.gz", index=False, compression=GZ, float_format=FLOAT)
    manifest = {
        "stage": "07",
        "upstream": h["results"],
        "files_sha256": {f"results/07/{k}": sha256(res / k) for k in files},
        "work_sha256": {
            f"outputs/t14/07/{k}": sha256(work / k)
            for k in (
                "daily_price_features.csv.gz",
                "daily_relative_moves.csv.gz",
                "cusum_alarm_price_daily.csv.gz",
                "interval_price_reaction_full.csv.gz",
            )
        },
    }
    (res / "07_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "price": pf,
        "relative": rel,
        "reaction": react,
        "paths": paths,
        "cusum_price": cp,
        "cnn": cnn,
        "intervals": iv,
        "expo": expo,
        "handoff06": h,
        "manifest": manifest,
        "r_wide": r_wide,
    }


def regime_relative_table(
    overlap: pd.DataFrame, rel: pd.DataFrame, pf: pd.DataFrame, cfg: dict, h: int = 20
) -> pd.DataFrame:
    """2021–2025, 채널 × (후보일/비후보일) 의 과거 h 일 가격·상대 움직임 중앙값 (ETF·날짜 합산 기술 통계)."""
    core = overlap[overlap.date.dt.year.isin(cfg["core_years"])][
        ["ticker", "channel", "date", "overlap_candidate_day"]
    ]
    x = rel[rel.h.eq(h)].merge(
        pf[pf.h.eq(h)][["ticker", "date", "C", "Z_A", "U_C", "fwd_R"]], on=["ticker", "date"]
    )
    m = core.merge(x, on=["ticker", "date"], how="left")
    cols = ["C", "Z_A", "U_C", "rel_simple", "rel_std", "rel_exposure_adj", "rel_cross_asset", "fwd_R"]
    g = m.groupby(["channel", "overlap_candidate_day"])
    out = g[cols].median().add_prefix("median_")
    out["share_C_pos"] = g.C.apply(lambda s: float((s > 0).mean()))
    out["n_etf_days"] = g.size()
    return out.reset_index()


def same_exposure_tracking(rel: pd.DataFrame, overlap: pd.DataFrame, cfg: dict, h: int = 20) -> pd.DataFrame:
    """KOSPI200 그룹 상대 (명목 배수 조정 후 069500 대비) 의 2021–2025 분포를 069500 고변동성 후보일 여부로 나눈다."""
    k = rel[
        rel.h.eq(h) & rel.ticker.isin(cfg["exposure_kospi200"]) & rel.date.dt.year.isin(cfg["core_years"])
    ]
    hi = overlap[overlap.ticker.eq("069500") & overlap.channel.eq("HIGH_LEVEL")][
        ["date", "overlap_candidate_day"]
    ]
    k = k.merge(hi, on="date", how="left")
    return (
        k.groupby(["ticker", "overlap_candidate_day"])
        .rel_same_exposure.agg(
            n="size",
            median="median",
            q10=lambda s: s.quantile(0.1),
            q90=lambda s: s.quantile(0.9),
            mean_abs=lambda s: s.abs().mean(),
        )
        .reset_index()
    )
