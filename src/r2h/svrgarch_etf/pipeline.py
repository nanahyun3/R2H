"""T11 오토런 — S0 데이터 → S1 적합 → S2 사후 검정 → S3 잔차 → S4 이동창 CUSUM → S5 귀무 오탐률
→ S6 사건 근접 → S7 사건일 제거 → S8 흐름 겹침 → 결과표·manifest.

커밋 대상 결과표에는 일별 수익률·잔차를 넣지 않는다 (수익률 복원 가능). 그것들은 ``outputs/cache/t11_state.npz`` (git 제외).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import platform
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..evaluation.null_tests import bh_qvalues, circular_shift_test_fast, proximity_count
from .data import KOSPI200_GROUP, REPO_ROOT, STUDY_DIR, load_close_panel, percent_log_returns
from .events import FAMILIES, event_table, family_dates, high_vol_flag, positions
from .model import GRID, baseline_residuals, fit_etf, fullsample_test
from .rolling import (
    ASYMPTOTIC_5PCT,
    SEED,
    WINDOWS,
    bootstrap_critical_value,
    episodes,
    normal_critical_value,
    null_alarm_episodes_per_year,
    rolling_cusum,
    window_khat,
    yearly_blocks,
)

RTYPES = ("svrA", "base")  # 1차 잔차 · 모형 없는 기준선
LAGS = (5, 10, 20)
EPISODE_GAP = 5
B = 2000
PRIMARY_FAMILIES: tuple[str, ...] = ("P1", "COMMON")
PRIMARY: dict[str, Any] = {
    "rtype": "svrA",
    "mask": "none",
    "window": 60,
    "zone": "test",
    "families": PRIMARY_FAMILIES,
    "L": 10,
}


def _one_based(k: int | None) -> int:
    if k is None:
        raise ValueError("CUSUM change location undefined")
    return k


def _period(d: pd.Timestamp) -> str:
    return "2019-2024" if d.year <= 2024 else str(d.year)


def _zones(idx: pd.DatetimeIndex, split: pd.Timestamp, w: int) -> dict[str, np.ndarray]:
    """구간 위치. test 는 창 전체가 검정 구간 안에 들어간 날부터 (split + w − 1) — 적합 구간 잔차가 섞인 창 제외."""
    pos = np.arange(len(idx))
    t0 = int(idx.searchsorted(split)) + w - 1
    return {
        "all": pos,
        "fit": pos[idx < split],
        "test": pos[pos >= t0],
        "test_pre2026": pos[(pos >= t0) & (idx < pd.Timestamp("2026-01-01"))],
    }


def _zone_label(s: int, split_pos: int, w: int) -> str:
    """에피소드 시작 위치의 구간: fit / boundary (창이 두 구간에 걸침) / test (창 전체 out-of-sample)."""
    if s < split_pos:
        return "fit"
    return "test" if s >= split_pos + w - 1 else "boundary"


def _salt(ticker: str, rtype: str) -> int:
    """부트스트랩 난수 salt — ticker 순서와 무관하게 ticker 코드로 정한다."""
    return int(ticker) * 10 + RTYPES.index(rtype)


def run(
    out_dir: str | Path | None = None,
    *,
    raw_dir: str | Path | None = None,
    allow_mismatch: bool = False,
    null_sims: int = 100,
    log: Callable[[str], object] = print,
) -> dict[str, Any]:
    t0 = time.time()
    out = Path(out_dir) if out_dir else STUDY_DIR / "results"
    out.mkdir(parents=True, exist_ok=True)
    state_path = REPO_ROOT / "outputs" / "cache" / "t11_state.npz"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # S0 ── 데이터
    panel = load_close_panel(raw_dir, allow_mismatch=allow_mismatch)
    r = percent_log_returns(panel.close)
    idx = pd.DatetimeIndex(r.index)
    tickers = list(r.columns)
    log(
        f"S0 data: {len(tickers)} ETFs × {len(idx)} returns · data_version {panel.data_version} · source {panel.source}"
    )

    # S1/S2 ── 적합 · 사후 검정
    fits, fit_rows, full_rows, resid = {}, [], [], {}
    for t in tickers:
        f = fit_etf(t, r[t])
        fits[t] = f
        fit_rows.append(
            {
                "ticker": t,
                "n_returns": f.returns.size,
                "n_train": f.n_train,
                "n_validation": f.n_fit - f.n_train,
                "n_test": f.returns.size - f.n_fit,
                "split_date": f.split_date.date(),
                "C": f.params.C,
                "paper_gamma_squared": f.params.paper_gamma_squared,
                "epsilon": f.params.epsilon,
                "val_mae": f.val_mae,
                "n_nonpos_var_A": int(np.sum(f.var_a[1:] <= 0)),
                "n_nonpos_var_B_test": int(np.sum(f.var_b_test <= 0)),
            }
        )
        for pol in ("A", "B"):
            full_rows.append(fullsample_test(f, pol))
        # 잔차를 공통 index 로 정렬 (DQ 로 뺀 날은 NaN)
        a = pd.Series(f.residuals("A"), index=f.dates).reindex(idx)
        bse = baseline_residuals(r[t]).reindex(idx)
        resid[(t, "svrA")] = a.to_numpy()
        resid[(t, "base")] = bse.to_numpy()
        resid[(t, "svrB")] = pd.Series(f.residuals("B"), index=f.dates).reindex(idx).to_numpy()
        log(
            f"S1 {t}: C={f.params.C} g2={f.params.paper_gamma_squared} eps={f.params.epsilon} split {f.split_date.date()}"
        )
    fit_df = pd.DataFrame(fit_rows)
    full_df = pd.DataFrame(full_rows)
    # 기준선 잔차도 같은 검정 구간에서 사후 검정 (비교용)
    from ..paper2020 import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test

    for t in tickers:
        split = fits[t].split_date
        e = pd.Series(resid[(t, "base")], index=idx)[idx >= split].dropna().to_numpy()
        res = cusum_squares_test(
            e, tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
        )
        test_dates = pd.Series(resid[(t, "base")], index=idx)[idx >= split].dropna().index
        full_df = pd.concat(
            [
                full_df,
                pd.DataFrame(
                    [
                        {
                            "ticker": t,
                            "policy": "base",
                            "n_test": e.size,
                            "n_nonpos_var": 0,
                            "test_start": test_dates[0].date(),
                            "test_end": test_dates[-1].date(),
                            "status": "ok",
                            "T": res.statistic,
                            "reject": res.reject,
                            "khat_date": test_dates[_one_based(res.change_index_one_based) - 1].date(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    # S4 ── 임계값 · 이동창
    events = event_table(panel.close["069500"])
    hv_flag = high_vol_flag(panel.close["069500"]).reindex(idx).fillna(False).to_numpy()
    crit_rows, roll, ep_rows, nul_rows = [], {}, [], []
    normal_c = {w: normal_critical_value(w) for w in WINDOWS}
    for t in tickers:
        split = fits[t].split_date
        split_pos = int(idx.searchsorted(split))
        p1 = positions(idx, family_dates(events, "P1", t))
        for rtype in RTYPES:
            e_full = resid[(t, rtype)]
            fit_part = e_full[np.asarray(idx < split)]
            for w in WINDOWS:
                c_boot = bootstrap_critical_value(fit_part, w, salt=_salt(t, rtype))
                crit_rows.append(
                    {
                        "ticker": t,
                        "rtype": rtype,
                        "window": w,
                        "c_bootstrap": c_boot,
                        "c_normal": normal_c[w],
                        "c_asymptotic": ASYMPTOTIC_5PCT,
                    }
                )
                for mask in ("none", "P1"):
                    e = e_full.copy()
                    if mask == "P1":
                        e[p1] = np.nan  # 그 ETF 의 큰 수익률일 제거 (D7 기계적 성분 점검)
                    stat = rolling_cusum(e, w)
                    alarm = np.nan_to_num(stat, nan=-np.inf) >= c_boot
                    if mask == "none":
                        roll[(t, rtype, w)] = stat
                    for k, (s, en) in enumerate(episodes(alarm, gap=EPISODE_GAP)):
                        kh = window_khat(e, s, w)
                        ep_rows.append(
                            {
                                "ticker": t,
                                "rtype": rtype,
                                "mask": mask,
                                "window": w,
                                "episode": k,
                                "start": idx[s].date(),
                                "end": idx[en].date(),
                                "n_alarm_days": int(alarm[s : en + 1].sum()),
                                "peak_T": float(np.nanmax(stat[s : en + 1])),
                                "khat_at_start": idx[kh].date() if kh is not None else None,
                                "zone": _zone_label(s, split_pos, w),
                                "period": _period(idx[s]),
                                "hivol_at_start": bool(hv_flag[s]),
                            }
                        )
                nul_rows.append(
                    {
                        "ticker": t,
                        "rtype": rtype,
                        "window": w,
                        "c_bootstrap": c_boot,
                        "null_episodes_per_year": null_alarm_episodes_per_year(
                            fit_part,
                            w,
                            c_boot,
                            len(idx),
                            sims=null_sims,
                            salt=_salt(t, rtype),
                            gap=EPISODE_GAP,
                        ),
                    }
                )
        log(f"S4/S5 {t} done ({time.time() - t0:.0f}s)")
    crit_df, ep_df, nul_df = pd.DataFrame(crit_rows), pd.DataFrame(ep_rows), pd.DataFrame(nul_rows)
    obs_rate = ep_df[ep_df["mask"] == "none"].groupby(["ticker", "rtype", "window"]).size() / (len(idx) / 252)
    nul_df["observed_episodes_per_year"] = [
        obs_rate.get((a, b, c), 0.0)
        for a, b, c in zip(nul_df.ticker, nul_df.rtype, nul_df.window, strict=True)
    ]

    # S6/S7 ── 사건 근접 (원형 이동 귀무, BH)
    ov_rows = []
    for t in tickers:
        for rtype, mask, w in itertools.product(RTYPES, ("none", "P1"), WINDOWS):
            # 경보가 0건인 조합도 빠짐없이 행을 만든다 (1차 가족 크기 고정 — 검토 지적 1)
            zones = _zones(idx, fits[t].split_date, w)
            g = ep_df[
                (ep_df.ticker == t) & (ep_df.rtype == rtype) & (ep_df["mask"] == mask) & (ep_df.window == w)
            ]
            starts = positions(idx, pd.to_datetime(g["start"]))
            for fam in FAMILIES:
                ev = positions(idx, family_dates(events, fam, t))
                if fam == "C3" and ev.size == 0:
                    continue
                for zname, zpos in zones.items():
                    lo, hi = zpos.min(), zpos.max()
                    c = starts[(starts >= lo) & (starts <= hi)] - lo
                    p = ev[(ev >= lo) & (ev <= hi)] - lo
                    n = hi - lo + 1
                    for L in LAGS:
                        cst = (
                            circular_shift_test_fast(c, p, n, L, B=B, seed=SEED)
                            if c.size and p.size
                            else None
                        )
                        ov_rows.append(
                            {
                                "ticker": t,
                                "rtype": rtype,
                                "mask": mask,
                                "window": w,
                                "family": fam,
                                "zone": zname,
                                "L": L,
                                "n_episodes": int(c.size),
                                "n_events": int(p.size),
                                "precision": proximity_count(c, p, L) / c.size if c.size else np.nan,
                                "coverage": proximity_count(p, c, L) / p.size if p.size else np.nan,
                                "T_obs": cst["T_obs"] if cst else 0,
                                "T_null_mean": cst["T_null_mean"] if cst else np.nan,
                                "p_value": cst["p_value"] if cst else np.nan,
                            }
                        )
    ov = pd.DataFrame(ov_rows)
    # 1차 가족 (D1): 크기는 결과와 무관하게 고정. 경보·사건이 없어 검정할 수 없는 행은 p=1 로 넣는다.
    # D5: KOSPI200 그룹 4종은 1건 — 대표 069500 만 남긴다. → (20 − 3) ETF × 2 사건 = 34 검정.
    prim = (
        (ov.rtype == PRIMARY["rtype"])
        & (ov["mask"] == PRIMARY["mask"])
        & (ov.window == PRIMARY["window"])
        & (ov.zone == PRIMARY["zone"])
        & ov.family.isin(PRIMARY_FAMILIES)
        & (ov.L == PRIMARY["L"])
        & ~ov.ticker.isin([k for k in KOSPI200_GROUP if k != "069500"])
    )
    ov["primary_family"] = prim
    ov["p_primary"] = np.nan
    ov.loc[prim, "p_primary"] = ov.loc[prim, "p_value"].fillna(1.0)
    ov["q_primary"] = np.nan
    ov.loc[prim, "q_primary"] = bh_qvalues(ov.loc[prim, "p_primary"].to_numpy())
    tested = ov.p_value.notna()
    ov["q_global"] = np.nan
    ov.loc[tested, "q_global"] = bh_qvalues(ov.loc[tested, "p_value"].to_numpy())

    # S8 ── 경보 에피소드별 흐름 겹침 (±10 거래일)
    flows = []
    ref_eps = ep_df[(ep_df.ticker == "069500") & (ep_df["mask"] == "none")]
    for row in ep_df[ep_df["mask"] == "none"].itertuples():
        s = int(idx.searchsorted(pd.Timestamp(str(row.start))))  # 에피소드 시작일은 idx 안의 날짜

        def near(fam: str, t: str = str(row.ticker), s: int = s) -> bool:
            pos = positions(idx, family_dates(events, fam, t))
            return bool(np.any(np.abs(pos - s) <= 10))

        ref = ref_eps[(ref_eps.rtype == row.rtype) & (ref_eps.window == row.window)]
        rpos = positions(idx, pd.to_datetime(ref["start"]))
        flows.append(
            {
                "ticker": row.ticker,
                "rtype": row.rtype,
                "window": row.window,
                "start": row.start,
                "zone": row.zone,
                "period": row.period,
                "P1": near("P1"),
                "P4": near("P4_h5") or near("P4_h10") or near("P4_h20"),
                "COMMON": near("COMMON"),
                "C3": near("C3"),
                "HIVOL": bool(hv_flag[s]),
                "KOSPI200_sync": bool(row.ticker != "069500" and np.any(np.abs(rpos - s) <= 10)),
                "kospi_group": row.ticker in KOSPI200_GROUP,
            }
        )
    flow_df = pd.DataFrame(flows)

    # 달력연도 블록 (D7)
    yb = []
    for t in tickers:
        for rtype in RTYPES:
            y = yearly_blocks(idx, resid[(t, rtype)])
            y.insert(0, "rtype", rtype)
            y.insert(0, "ticker", t)
            yb.append(y)
    year_df = pd.concat(yb, ignore_index=True)
    year_df["reject_asymptotic"] = year_df["T"] >= ASYMPTOTIC_5PCT

    # 저장 ── 결과표 (커밋) · 상태 (로컬)
    stats = pd.DataFrame({"date": np.repeat(idx.date, 1)})
    for (t, rtype, w), v in roll.items():
        stats[f"{t}|{rtype}|{w}"] = np.round(v, 5)
    tables = {
        "fit_summary.csv": fit_df,
        "fullsample_tests.csv": full_df,
        "critical_values.csv": crit_df,
        "alarm_episodes.csv": ep_df,
        "null_alarm_rate.csv": nul_df,
        "overlap_metrics.csv": ov,
        "episode_flows.csv": flow_df,
        "yearly_blocks.csv": year_df,
    }
    for name, df in tables.items():
        df.to_csv(out / name, index=False, lineterminator="\n", float_format="%.6g")
    stats.to_csv(
        out / "rolling_stats.csv.gz",
        index=False,
        lineterminator="\n",
        compression={"method": "gzip", "mtime": 0},
    )
    arrays: dict[str, Any] = dict(
        dates=idx.astype("datetime64[ns]").astype(np.int64),
        tickers=np.array(tickers),
        **{f"r__{t}": r[t].to_numpy() for t in tickers},
        **{f"res__{t}__{k}": resid[(t, k)] for t in tickers for k in ("svrA", "svrB", "base")},
        **{
            f"varA__{t}": pd.Series(fits[t].var_a, index=fits[t].dates).reindex(idx).to_numpy()
            for t in tickers
        },
        **{
            f"proxy__{t}": pd.Series(fits[t].proxy, index=fits[t].dates).reindex(idx).to_numpy()
            for t in tickers
        },
        **{
            f"varB__{t}": pd.Series(
                np.r_[np.full(fits[t].n_fit, np.nan), fits[t].var_b_test], index=fits[t].dates
            )
            .reindex(idx)
            .to_numpy()
            for t in tickers
        },
    )
    np.savez_compressed(state_path, **arrays)
    import sklearn

    manifest = {
        "study": "T11 SVR-GARCH CUSUM on 20 ETFs",
        "data_version": panel.data_version,
        "data_source": panel.source,
        "close_hash_ok": panel.hash_ok,
        "n_returns": len(idx),
        "first": str(idx[0].date()),
        "last": str(idx[-1].date()),
        "protocol": {
            "fit_fraction": 0.7,
            "train_fraction_of_fit": 0.7,
            "grid_points": len(GRID),
            "windows": list(WINDOWS),
            "episode_gap": EPISODE_GAP,
            "lags": list(LAGS),
            "B": B,
            "seed": SEED,
            "primary": {k: (list(v) if isinstance(v, tuple) else v) for k, v in PRIMARY.items()},
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "outputs": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.iterdir())
            if p.is_file() and p.name != "run_manifest.json"
        },
        "runtime_seconds_excluded_from_hash": round(time.time() - t0, 1),
    }
    (out / "run_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, default=str) + "\n"
    )
    log(f"done in {time.time() - t0:.0f}s → {out}")
    return manifest
