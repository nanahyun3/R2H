"""11번 — 대표 6종 ETF 개별 급변 구간: 구간·스케일·지속 → 바텀업 → 누적수익률 → W3 SVR–GARCH CUSUM (계약 11-lock-1).

09 의 ETF 단위 A 를 읽기만 하고, CUSUM 은 W3 ``run_pipeline`` 을 관측 자료에 그대로 다시 돌린다 (W3 results 에 쓰지 않음).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.common_vol.core import extract_intervals
from r2h.joint_cusum import pipeline as JP
from r2h.peer_shock.core import annualized_vol, percent_log_returns_gap

OUT_DIR = "research/etf_shock_bottomup_11"
CFG_PATH = "configs/t20_etf_shock_bottomup_v1.json"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_cfg(root: Path) -> dict:
    return json.loads((root / CFG_PATH).read_text(encoding="utf-8"))


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.6g")


def period_of(year: int, cfg: dict) -> str:
    for name, (a, b) in cfg["periods"].items():
        if a <= year <= b:
            return name
    raise ValueError(year)


# ── 1. 경계 σ (mid-rank 규칙 역산) ─────────────────────────────────────────
def boundary_sigma(x: np.ndarray, min_ref: int, upper: float) -> np.ndarray:
    """엄밀 과거 기준집합 n 개 중 m=⌈upper·n⌉ 번째 작은 값. 동점이 없으면 U ≥ upper ⟺ x > b."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    ref: list[float] = []
    for t, v in enumerate(x):
        n = len(ref)
        if n >= min_ref:
            m = math.ceil(upper * n - 1e-9)
            out[t] = ref[m - 1]
        if np.isfinite(v):
            bisect.insort(ref, float(v))
    return out


def past_median(x: np.ndarray, min_ref: int) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    ref: list[float] = []
    for t, v in enumerate(x):
        if len(ref) >= min_ref:
            out[t] = float(np.median(ref))
        if np.isfinite(v):
            bisect.insort(ref, float(v))
    return out


# ── 2. 입력·일별 표 ────────────────────────────────────────────────────────
def load_daily(root: Path, cfg: dict) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    inp = cfg["inputs"]
    st = pd.read_csv(root / inp["etf_states"], dtype={"ticker": str}, parse_dates=["date"])
    closes = pd.read_csv(root / inp["closes"], index_col=0, parse_dates=True)
    dates = pd.DatetimeIndex(closes.index)
    c10 = pd.read_csv(root / inp["c10_daily"], parse_dates=["date"]).set_index("date").reindex(dates)
    rows = []
    for t in cfg["tickers"]:
        c = closes[t]
        r = percent_log_returns_gap(c).to_numpy()
        df = pd.DataFrame({"date": dates, "ticker": t, "close": c.to_numpy(float), "r": r})
        df["cumret"] = (c.to_numpy(float) / c.iloc[0] - 1) * 100
        for q in (cfg["q_main"], cfg["q_companion"]):
            s = annualized_vol(r, q)
            x = st[(st["ticker"] == t) & (st["q"] == q)].set_index("date").reindex(dates)
            assert np.allclose(s, x["sigma"].to_numpy(float), equal_nan=True, atol=1e-9), f"σ 재계산 불일치 {t} q{q}"
            b = boundary_sigma(s, cfg["min_ref"], cfg["A_upper"])
            a = x["A"].to_numpy(float)
            ok = np.isfinite(a) & (x["ties_A"].to_numpy() == 0)
            assert ((s[ok] > b[ok]).astype(float) == a[ok]).all(), f"경계 σ 와 A 불일치 {t} q{q}"
            df[f"sigma{q}"] = s
            df[f"U{q}"] = x["U_A"].to_numpy(float)
            df[f"A{q}"] = a
            df[f"b{q}"] = b
            df[f"med{q}"] = past_median(s, cfg["min_ref"])
        df["N_A_q20"] = c10["n_A_q20"].to_numpy(float)
        df["C1"] = c10["q20_k9"].to_numpy(float)
        rows.append(df)
    return pd.concat(rows, ignore_index=True), dates


# ── 3. CUSUM (W3 함수 재실행) ──────────────────────────────────────────────
def cusum_daily(root: Path, cfg: dict, dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    wcfg = JP.load_cfg(root / cfg["inputs"]["w3_config"])
    assert wcfg["universe"]["tickers"] == cfg["tickers"]
    ret = JP.load_returns(wcfg, root / cfg["inputs"]["raw_dir"])
    out = JP.run_pipeline(ret, wcfg)
    wins = JP.all_windows(wcfg)
    summ = pd.read_csv(root / cfg["inputs"]["w3_individual_summary"], dtype={"ticker": str})
    crit = {}
    for _, x in summ.iterrows():
        i, p, w = cfg["tickers"].index(x["ticker"]), JP.POLICIES.index(x["policy"]), wins.index(int(x["w"]))
        T = out.T[i, p, w]
        assert abs(np.nanmax(T) - x["max_T"]) < 1e-6 and int((T >= x["crit_w3"]).sum()) == x["alarm_days_w3"] and int(np.isfinite(T).sum()) == x["valid_days"]
        crit[(x["ticker"], x["policy"], int(x["w"]))] = float(x["crit_w3"])
    ev = pd.DatetimeIndex(out.eval_dates)
    in_cal = dates[(dates.year >= 2021) & (dates.year <= 2025)]
    assert ev.equals(in_cal), "W3 평가일과 09 달력의 2021–2025 불일치"
    rows = []
    for i, t in enumerate(cfg["tickers"]):
        df = pd.DataFrame({"date": ev, "ticker": t})
        for p in cfg["cusum_table_policies"]:
            for w in cfg["cusum_table_windows"]:
                T = out.T[i, JP.POLICIES.index(p), wins.index(w)]
                df[f"T_{p}_{w}"] = T
                df[f"R_{p}_{w}"] = T / crit[(t, p, w)]
        rows.append(df)
    return pd.concat(rows, ignore_index=True), {"crit": crit, "n_checked": len(summ)}


# ── 4. 구간 ────────────────────────────────────────────────────────────────
def intervals_for(d: pd.DataFrame, cu: pd.DataFrame, cfg: dict, q: int) -> pd.DataFrame:
    """한 ETF 의 q 기준 A 구간 (전체 달력에서 한 번에 추출) + 스케일·바텀업·누적수익률·CUSUM."""
    d = d.reset_index(drop=True)
    f = d[f"A{q}"].to_numpy(float)
    ivs = extract_intervals(f, np.ones(f.size, bool))
    cells = [(p, w) for p in cfg["cusum_table_policies"] for w in cfg["cusum_table_windows"]]
    cu = cu.set_index("date")
    ctx = cfg["context_days"]
    rows = []
    for j, iv in enumerate(ivs, start=1):
        s, e = iv["i0"], iv["i1"]
        seg = d.iloc[s:e + 1]
        pk = int(seg[f"sigma{q}"].to_numpy().argmax()) + s
        win = d["r"].to_numpy()[pk - q + 1:pk + 1]
        dev2 = (win - win.mean()) ** 2
        share = dev2 / dev2.sum()
        assert abs(share.sum() - 1) < 1e-12 and abs(np.sqrt(252 * dev2.sum() / (q - 1)) - d.loc[pk, f"sigma{q}"]) < 1e-9
        order = np.argsort(-share)
        top = pk - q + 1 + int(order[0])
        exit_i = e + 1 if e + 1 < len(d) else None
        win_exit = exit_i is not None and f[exit_i] == 0 and exit_i == top + q
        base_close = d.loc[s - 1, "close"] if s > 0 else np.nan
        path = d["close"].to_numpy()[s:e + 1] / base_close - 1
        runmax = np.maximum.accumulate(np.concatenate([[1.0], d["close"].to_numpy()[s:e + 1] / base_close]))
        dd = (np.concatenate([[1.0], d["close"].to_numpy()[s:e + 1] / base_close]) / runmax - 1).min()
        pre = d.loc[s - 1, "close"] / d.loc[s - 1 - ctx, "close"] - 1 if s - 1 - ctx >= 0 else np.nan
        post = d.loc[e + ctx, "close"] / d.loc[e, "close"] - 1 if e + ctx < len(d) else np.nan
        sd = d.loc[s:e, "date"]
        csub = cu.reindex(sd)
        cus = {}
        for p, w in cells:
            rr = csub[f"R_{p}_{w}"].to_numpy(float)
            cus[f"maxR_{p}_{w}"] = float(np.nanmax(rr)) if np.isfinite(rr).any() else np.nan
            cus[f"alarm_{p}_{w}"] = int((rr >= 1).sum())
        cov = csub["R_A_20"].notna().mean() if len(csub) else 0.0
        allR = np.array([cus[f"maxR_{p}_{w}"] for p, w in cells], float)
        y0 = d.loc[s, "date"].year
        rows.append({
            "ticker": d.loc[0, "ticker"], "q": q, "interval_id": f"{d.loc[0, 'ticker']}_q{q}_{j:03d}",
            "start": d.loc[s, "date"].date(), "end": d.loc[e, "date"].date(), "duration": e - s + 1,
            "primary_days": int(sd.dt.year.between(2021, 2025).sum()), "right_censored_data_end": e == len(d) - 1,
            "period": period_of(y0, cfg), "crosses_period": period_of(d.loc[e, "date"].year, cfg) != period_of(y0, cfg),
            "peak_date": d.loc[pk, "date"].date(), "peak_sigma": float(d.loc[pk, f"sigma{q}"]),
            "peak_U": float(seg[f"U{q}"].max()), "boundary_at_peak": float(d.loc[pk, f"b{q}"]),
            "peak_over_boundary": float(d.loc[pk, f"sigma{q}"] / d.loc[pk, f"b{q}"]),
            "peak_over_past_median": float(d.loc[pk, f"sigma{q}"] / d.loc[pk, f"med{q}"]),
            "entry_r": float(d.loc[s, "r"]), "entry_sigma_jump": float(d.loc[s, f"sigma{q}"] - d.loc[s - 1, f"sigma{q}"]) if s > 0 else np.nan,
            "top1_date": d.loc[top, "date"].date(), "top1_r": float(d.loc[top, "r"]), "top1_share": float(share[order[0]]),
            "top3": "; ".join(f"{d.loc[pk - q + 1 + int(k), 'date'].date()} {d.loc[pk - q + 1 + int(k), 'r']:+.2f}% ({share[k]:.0%})" for k in order[:3]),
            "shock_type": "단일 충격형" if share[order[0]] >= cfg["single_shock_top1_share"] else "누적형",
            "window_exit_end": bool(win_exit),
            "other_q_overlap_days": int((d.loc[s:e, f"A{60 if q == 20 else 20}"] == 1).sum()),
            "max_N_A_q20": float(d.loc[s:e, "N_A_q20"].max()), "C1_days": int((d.loc[s:e, "C1"] == 1).sum()),
            "ret_interval_pct": float(path[-1] * 100), "max_drawdown_pct": float(dd * 100),
            "ret_pre20_pct": float(pre * 100), "ret_post20_pct": float(post * 100),
            "cusum_coverage_A20": float(cov),
            "cusum_maxR_any": float(np.nanmax(allR)) if np.isfinite(allR).any() else np.nan,
            "cusum_alarm_days_any": int(sum(cus[f"alarm_{p}_{w}"] for p, w in cells)),
            **cus, "i0": s, "i1": e,
        })
    return pd.DataFrame(rows)


def inside_outside(d: pd.DataFrame, cu: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """2021–2025 에서 A20 날 vs 아닌 날의 T/crit 분포 (12 셀)."""
    m = d[["date", "ticker", "A20"]].merge(cu, on=["date", "ticker"], how="inner")
    rows = []
    for t in cfg["tickers"]:
        x = m[m["ticker"] == t]
        for p in cfg["cusum_table_policies"]:
            for w in cfg["cusum_table_windows"]:
                c = f"R_{p}_{w}"
                for side, mask in (("A20 날", x["A20"] == 1), ("비 A20 날", x["A20"] == 0)):
                    v = x.loc[mask, c].dropna()
                    rows.append({"ticker": t, "policy": p, "w": w, "side": side, "n_valid": len(v),
                                 "median_R": float(v.median()) if len(v) else np.nan,
                                 "p95_R": float(v.quantile(0.95)) if len(v) else np.nan,
                                 "max_R": float(v.max()) if len(v) else np.nan, "alarm_days": int((v >= 1).sum())})
    return pd.DataFrame(rows)


def expansion(d: pd.DataFrame, iv: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """확장 층: 단계별 새 ETF 와 앞 ETF 들의 같은 날 A20 겹침, 069500 주분석 구간마다 각 ETF 참여 여부."""
    w = d.pivot(index="date", columns="ticker", values="A20")[cfg["tickers"]]
    prim = w[(w.index.year >= 2021) & (w.index.year <= 2025)]
    stage = []
    for k, t in enumerate(cfg["tickers"]):
        prev = cfg["tickers"][:k]
        on = prim[t] == 1
        any_prev = (prim[prev] == 1).any(axis=1) if prev else pd.Series(False, index=prim.index)
        x = iv[(iv["ticker"] == t) & (iv["q"] == 20) & (iv["period"] == "PRIMARY")]
        alone = sum(1 for _, r in x.iterrows() if not any_prev.iloc[(prim.index >= pd.Timestamp(r["start"])) & (prim.index <= pd.Timestamp(r["end"]))].any())
        stage.append({"order": k + 1, "ticker": t, "stage": cfg["stage_labels"][t], "A20_days": int(on.sum()),
                      "days_with_069500": int((on & (prim["069500"] == 1)).sum()) if t != "069500" else int(on.sum()),
                      "days_with_any_prev": int((on & any_prev).sum()), "intervals": len(x), "intervals_alone_vs_prev": alone})
    k2 = []
    base = iv[(iv["ticker"] == "069500") & (iv["q"] == 20) & (iv["period"] == "PRIMARY")]
    for _, r in base.iterrows():
        seg = prim.loc[pd.Timestamp(r["start"]):pd.Timestamp(r["end"])]
        rec = {"interval_id": r["interval_id"], "start": r["start"], "end": r["end"], "duration": r["duration"]}
        for t in cfg["tickers"][1:]:
            rec[t] = int((seg[t] == 1).sum())
        k2.append(rec)
    return pd.DataFrame(stage), pd.DataFrame(k2)


def run(root: Path) -> dict:
    cfg = load_cfg(root)
    for line in (root / OUT_DIR / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        dg, name = line.split(maxsplit=1)
        assert sha(root / name) == dg, f"11 동결 파일 변경: {name}"
    d, dates = load_daily(root, cfg)
    cu, cinfo = cusum_daily(root, cfg, dates)
    iv = pd.concat([intervals_for(d[d["ticker"] == t], cu[cu["ticker"] == t], cfg, q)
                    for t in cfg["tickers"] for q in (cfg["q_main"], cfg["q_companion"])], ignore_index=True)
    io = inside_outside(d, cu, cfg)
    st, k2 = expansion(d, iv, cfg)
    summ = (iv.groupby(["ticker", "q", "period"], sort=False)
              .agg(n=("interval_id", "size"), days=("duration", "sum"), primary_days=("primary_days", "sum"), dur_median=("duration", "median"), dur_max=("duration", "max"),
                   peak_sigma_max=("peak_sigma", "max"), single_shock=("shock_type", lambda s: int((s == "단일 충격형").sum())),
                   window_exit=("window_exit_end", "sum"), cusum_alarm_intervals=("cusum_alarm_days_any", lambda s: int((s > 0).sum())))
              .reset_index())
    out = {"cfg": cfg, "daily": d, "dates": dates, "cusum": cu, "cusum_info": cinfo, "intervals": iv,
           "inside_outside": io, "stage": st, "k200_participation": k2, "summary": summ}
    res = root / OUT_DIR / "results"
    write_csv(iv, res / "intervals.csv")
    write_csv(io, res / "cusum_inside_outside.csv")
    write_csv(st, res / "expansion_stage.csv")
    write_csv(k2, res / "kospi200_interval_participation.csv")
    write_csv(summ, res / "interval_summary.csv")
    write_csv(pd.DataFrame([{"ticker": t, "policy": p, "w": w, "crit_w3": v} for (t, p, w), v in cinfo["crit"].items()]), res / "cusum_crit_w3.csv")
    return out


def results_digest(root: Path) -> dict[str, str]:
    return {p.name: sha(p) for p in sorted((root / OUT_DIR / "results").glob("*.csv"))}
