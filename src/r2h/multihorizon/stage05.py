"""05 단계: 20종 일별 다중 기간 특징 → 신호 → 기간별 에피소드 → 공통 구간 → 순위, CUSUM 일별 재계산·대조.

가격을 역산할 수 있는 일별 표는 ``outputs/t14/05/`` (Git 제외) 에,
집계·구간표는 ``research/multihorizon_w2/results/05/`` 에 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.multihorizon.core import (
    CHANNELS,
    overlap_intervals,
    percent_log_returns,
    period_episodes,
    rank_intervals,
    sha256,
    signal_matrix,
    ticker_features,
    year_status,
)
from r2h.multihorizon.cusum import critical_tables, daily_cusum, load_daily_cache, verify_against_w1
from r2h.multihorizon.relation import (
    alarm_contrast,
    event_study,
    joined,
    level_change_jaccard,
    spearman_matrix,
)

FLOAT = "%.10g"
GZ = {"method": "gzip", "mtime": 0}  # gzip 헤더 시각을 0 으로 고정 (바이트 재현)


def load_universe(root: Path) -> pd.DataFrame:
    """T11 공식 종목표 + W1 노출 그룹 (계약 §4.7 [A-7])."""
    d = pd.read_csv(root / "research/svr_garch_cusum_etf/reference_close_sha256.csv", dtype={"ticker": str})
    from r2h.window_study.empirical import category_exposure

    e = category_exposure(root)[["ticker", "exposure_group"]]
    return d[["ticker", "name", "category", "close_sha256", "raw_file_sha256"]].merge(e, on="ticker")


def load_prices(root: Path, universe: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for t, raw_sha in zip(universe.ticker, universe.raw_file_sha256, strict=True):
        path = root / "data/raw" / f"{t}.csv"
        if sha256(path) != raw_sha:
            raise AssertionError(f"원자료 SHA 불일치: {t}")
        p = pd.read_csv(path, parse_dates=["Date"])
        out[t] = p
    dates = {tuple(p.Date) for p in out.values()}
    if len(dates) != 1:
        raise AssertionError("20종 거래일 집합이 다릅니다")
    return out


CUSUM_VARIANTS = {
    "main": ("A", "pipe", "common"),
    "A_own": ("A", "pipe", "own"),
    "A_point": ("A", "point", "common"),
    "B": ("B", "pipe", "common"),
    "base": ("base", "pipe", "common"),
}


def cusum_variants(cus: pd.DataFrame, cfg: dict, dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    """주 CUSUM (정책 A·W1 연간 임계값·공통일) 과 계약 §3-5 의 병렬 민감도 4종의 일별 상태표."""
    out = {}
    for name, (policy, ttype, sample) in CUSUM_VARIANTS.items():
        g = cus[cus.policy.eq(policy)].set_index("date")
        frame = pd.DataFrame(
            {f"alarm_w{w}": g[f"{ttype}_{sample}_w{w}"] for w in cfg["cusum_windows"]}, index=g.index
        )
        out[name] = frame.reindex(dates).fillna("NOT_AVAILABLE")
    return out


def sensitivity_intervals(ticker: str, f: pd.DataFrame, cfg: dict) -> list[dict]:
    """[A-3] 임계값 5%·20%, [A-4] 고정 504 기준분포로 같은 공통 구간 규칙을 다시 적용한 구간 목록 (순위 키 불변)."""
    rows = []
    variants = [("main_10pct", 0.90, 0.10, "")]
    variants += [(f"sens_{round((1 - u) * 100)}pct", u, lo, "") for u, lo in cfg["signal_sensitivity"]]
    variants += [("fixed504_10pct", 0.90, 0.10, "_fixed504")]
    for tag, up, lo, suffix in variants:
        sig = signal_matrix(f, cfg, up, lo, u_suffix=suffix)
        _, iv = overlap_intervals(ticker, sig, f, cfg)
        for r in iv.itertuples(index=False):
            rows.append(
                {
                    "variant": tag,
                    "ticker": ticker,
                    "channel": r.channel,
                    "interval_start": r.interval_start,
                    "interval_end": r.interval_end,
                    "duration_trading_days": r.duration_trading_days,
                    "max_overlap_count": r.max_overlap_count,
                    "start_year": r.start_year,
                }
            )
    return rows


def sensitivity_summary(sens: pd.DataFrame, iv: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """변형별 (채널) 주 해석 연도 공통 구간 수와, 주 결과 ETF×채널 1위 구간이 변형에서도 날짜가 겹치는 구간을 갖는 비율."""
    top = (
        iv[iv.rank_in_etf_channel.eq(1)].sort_values("interval_start").groupby(["ticker", "channel"]).head(1)
    )
    rows = []
    for (variant, ch), g in sens.groupby(["variant", "channel"]):
        core = g[g.start_year.isin(cfg["core_years"])]
        kept, total = 0, 0
        for r in top[top.channel.eq(ch)].itertuples(index=False):
            total += 1
            o = g[g.ticker.eq(r.ticker)]
            kept += int(((o.interval_start <= r.interval_end) & (o.interval_end >= r.interval_start)).any())
        rows.append(
            {
                "variant": variant,
                "channel": ch,
                "n_intervals_core": len(core),
                "n_max7_core": int(core.max_overlap_count.eq(7).sum()),
                "median_duration_core": float(core.duration_trading_days.median()) if len(core) else np.nan,
                "top1_overlap_retained": kept,
                "top1_total": total,
            }
        )
    return pd.DataFrame(rows)


def run_stage05(root: Path, source_root: Path, w1_root: Path, cfg: dict, cfg_w1: dict) -> dict:
    res = root / "research/multihorizon_w2/results/05"
    work = root / "outputs/t14/05"
    res.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    uni = load_universe(root)
    prices = load_prices(root, uni)
    pipe_c, point_c = critical_tables(source_root, cfg["t12_run_id"], w1_root)
    feats, eps, ivs, overlaps, cus_all, unit_rows, sens_rows = [], [], [], [], [], [], []
    for t in uni.ticker:
        p = prices[t]
        dates = pd.DatetimeIndex(p.Date)
        r = percent_log_returns(p.Close, cfg["return_scale"]).to_numpy()
        f = ticker_features(dates, r, cfg)
        f.insert(0, "ticker", t)
        feats.append(f)
        daily = load_daily_cache(source_root, cfg["t12_run_id"], t)
        cus = daily_cusum(t, daily, cfg_w1, pipe_c, point_c, cfg["cusum_windows"])
        cus_all.append(cus)
        # 단위 검사: cache r 과 원자료 % 로그수익률
        base = daily[daily.window.eq(0) & daily.policy.eq("A")].set_index("date")
        rr = pd.Series(r, index=dates).reindex(base.index)
        unit_rows.append(
            {
                "ticker": t,
                "n": len(base),
                "max_abs_diff_r": float(np.nanmax(np.abs(rr - base.r))),
                "max_abs_e_minus_r_over_sqrt_vhat": float(
                    np.nanmax(np.abs(base.e - base.r / np.sqrt(base.vhat.where(base.vhat > 0))))
                ),
                "n_vhat_nonpositive_A": int((base.vhat <= 0).sum()),
            }
        )
        sig = signal_matrix(f, cfg)
        eps.append(period_episodes(t, sig, f))
        variants = cusum_variants(cus, cfg, dates)
        ov, iv = overlap_intervals(t, sig, f, cfg, cusum_alarm=variants)
        sens_rows += sensitivity_intervals(t, f, cfg)
        overlaps.append(ov)
        ivs.append(iv)
    feat = pd.concat(feats, ignore_index=True)
    ep = pd.concat(eps, ignore_index=True)
    ov = pd.concat(overlaps, ignore_index=True)
    iv = pd.concat(ivs, ignore_index=True)
    cus = pd.concat(cus_all, ignore_index=True)
    iv = iv.merge(uni[["ticker", "name", "category", "exposure_group"]], on="ticker", how="left")
    iv["year_status"] = [year_status(y, cfg) for y in iv.start_year]
    iv["rank_in_etf_channel"] = rank_intervals(iv, ["ticker", "channel"])
    iv = iv.sort_values(["ticker", "channel", "rank_in_etf_channel", "interval_start"]).reset_index(drop=True)
    iv.insert(
        0,
        "interval_id",
        [
            f"W2-{t}-{c[:3]}-{s.replace('-', '')}"
            for t, c, s in zip(iv.ticker, iv.channel, iv.interval_start, strict=True)
        ],
    )
    ep["year_status"] = [year_status(y, cfg) for y in ep.start_year]
    # W1 대조
    w1m = pd.read_csv(
        w1_root / "research/window_study_w1/results/04_real/alarm_metrics.csv", dtype={"ticker": str}
    )
    ver = verify_against_w1(cus, w1m, cfg["cusum_windows"], cfg["cusum_episode_gap_non_alarm_days"])
    # 결측·적격성 표
    feat["year"] = feat.date.dt.year
    elig = (
        feat.groupby(["ticker", "q"])
        .agg(
            n_days=("V", "size"),
            n_V=("V", lambda s: int(s.notna().sum())),
            n_V_zero=("V", lambda s: int((s == 0).sum())),
            n_U_V=("U_V", lambda s: int(s.notna().sum())),
            n_U_D=("U_D", lambda s: int(s.notna().sum())),
            first_U_V=("U_V", lambda s: s.first_valid_index()),
            first_U_D=("U_D", lambda s: s.first_valid_index()),
        )
        .reset_index()
    )
    first_uv = feat.loc[feat.U_V.notna()].groupby(["ticker", "q"]).date.min().rename("first_U_V_date")
    first_ud = feat.loc[feat.U_D.notna()].groupby(["ticker", "q"]).date.min().rename("first_U_D_date")
    elig = (
        elig.drop(columns=["first_U_V", "first_U_D"])
        .merge(first_uv, on=["ticker", "q"], how="left")
        .merge(first_ud, on=["ticker", "q"], how="left")
    )
    st = feat.groupby(["ticker", "q", "D_status"]).size().unstack(fill_value=0).reset_index()
    for c in (
        "OK",
        "NUMERATOR_ZERO",
        "DENOMINATOR_ZERO",
        "BOTH_ZERO",
        "INSUFFICIENT_HISTORY",
        "NOT_DEFINED_Q1",
    ):
        if c not in st:
            st[c] = 0
    st["zero_missing_total"] = st.NUMERATOR_ZERO + st.DENOMINATOR_ZERO + st.BOTH_ZERO
    st["zero_missing_rate_of_computable"] = st.zero_missing_total / (st.OK + st.zero_missing_total).replace(
        0, np.nan
    )
    elig = elig.merge(st, on=["ticker", "q"], how="left")
    core = feat[feat.year.isin(cfg["core_years"])]
    tie = (
        core.groupby(["ticker", "q"])
        .agg(
            tie_share_V=("ties_V", lambda s: float((s > 0).mean())),
            tie_share_D=("ties_D", lambda s: float((s > 0).mean())),
        )
        .reset_index()
    )
    elig = elig.merge(tie, on=["ticker", "q"], how="left")
    # 신호 비율 (주 해석 연도, 임계값 민감도 포함)
    rate_rows = []
    for up, lo, tag in [
        (cfg["signal_upper"], cfg["signal_lower"], "main_10pct"),
        *[(u, l_, f"sens_{round((1 - u) * 100)}pct") for u, l_ in cfg["signal_sensitivity"]],
    ]:
        for suffix, ref in (("", "expanding"), ("_fixed504", "fixed504")):
            if ref == "fixed504" and tag != "main_10pct":
                continue
            for t in uni.ticker:
                ft = feat[feat.ticker.eq(t)]
                sg = signal_matrix(ft.drop(columns=["ticker", "year"]), cfg, up, lo, u_suffix=suffix)
                yrs = sg["HIGH_LEVEL"].index.year
                coremask = np.isin(yrs, cfg["core_years"])
                for ch in (*CHANNELS, "DAILY_SHOCK"):
                    m, es = sg[ch][coremask], sg[ch + "__estimable"][coremask]
                    for q in m.columns:
                        ne = int(es[q].sum())
                        rate_rows.append(
                            {
                                "threshold_set": tag,
                                "reference": ref,
                                "ticker": t,
                                "channel": ch,
                                "q": int(q),
                                "n_estimable_core": ne,
                                "n_signal_core": int(m[q].sum()),
                                "signal_rate_core": m[q].sum() / ne if ne else np.nan,
                            }
                        )
    rates = pd.DataFrame(rate_rows)
    # H3 — 주 (A·연간 임계값·공통일) 와 민감도
    sp_rows, ct_rows = [], []
    for vname, (policy, ttype, sample) in CUSUM_VARIANTS.items():
        jv = joined(feat, cus, cfg, policy, ttype, sample)
        if ttype == "pipe" and sample == "common":
            sp_rows.append(spearman_matrix(jv, cfg).assign(variant=vname, policy=policy))
        ct_rows.append(alarm_contrast(jv, cfg).assign(variant=vname))
    spear = pd.concat(sp_rows, ignore_index=True)
    contrast = pd.concat(ct_rows, ignore_index=True)
    events, event_traj = event_study(feat, cus, cfg, cfg["cusum_episode_gap_non_alarm_days"])
    jac = level_change_jaccard(ov, cfg)
    # 쓰기
    files = {
        "h3_spearman.csv": spear,
        "h3_alarm_contrast.csv": contrast,
        "h3_cusum_events.csv": events,
        "h3_event_trajectory_mean.csv": event_traj[event_traj.year.isin(cfg["core_years"])]
        .groupby(["w", "rel_day"])[["U_V", "D"]]
        .mean()
        .reset_index(),
        "h1_level_vs_change_jaccard.csv": jac,
        "eligibility_missingness.csv": elig,
        "signal_rates.csv": rates,
        "period_episodes.csv": ep,
        "overlap_intervals.csv": iv,
        "cusum_w1_reconciliation.csv": ver,
        "unit_checks.csv": pd.DataFrame(unit_rows),
        "sensitivity_intervals.csv": sensitivity_summary(pd.DataFrame(sens_rows), iv, cfg),
    }
    for name, frame in files.items():
        frame.to_csv(res / name, index=False, float_format=FLOAT)
    feat.drop(columns=["year"]).to_csv(
        work / "daily_features.csv.gz", index=False, compression=GZ, float_format=FLOAT
    )
    ov.to_csv(work / "daily_overlap.csv.gz", index=False, compression=GZ)
    cus.to_csv(work / "daily_cusum.csv.gz", index=False, compression=GZ, float_format=FLOAT)
    manifest = {
        "stage": "05",
        "files_sha256": {f"results/05/{k}": sha256(res / k) for k in files},
        "work_sha256": {
            f"outputs/t14/05/{k}": sha256(work / k)
            for k in ("daily_features.csv.gz", "daily_overlap.csv.gz", "daily_cusum.csv.gz")
        },
    }
    (res / "05_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "spearman": spear,
        "contrast": contrast,
        "events": events,
        "event_traj": event_traj,
        "jaccard": jac,
        "sensitivity": files["sensitivity_intervals.csv"],
        "features": feat,
        "episodes": ep,
        "intervals": iv,
        "overlap": ov,
        "cusum": cus,
        "verify": ver,
        "eligibility": elig,
        "rates": rates,
        "units": pd.DataFrame(unit_rows),
        "universe": uni,
        "prices": prices,
        "manifest": manifest,
    }
