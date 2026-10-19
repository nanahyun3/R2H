"""10번 PART R — 급변 구간 라벨(ETF·시장)과 CNN·오토인코더 입력 데이터셋 (MODEL_INPUT_SPEC.md).

입력: lock-1 ``pipeline.run()`` · lock-2 ``lock2.run()`` 결과, 09 ETF 상태, W3 CUSUM (관측 재실행).
산출: results/ (구간표·창 색인·분포·명세, Git 포함) · outputs/t19/ (창 텐서 npz, Git 제외).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.common_vol.core import extract_intervals
from r2h.common_vol.lock2 import boundary_sigma
from r2h.common_vol.pipeline import OUT_DIR, sha, write_csv
from r2h.joint_cusum import pipeline as JP
from r2h.peer_shock.core import percent_log_returns_gap

CFG_R = "configs/t19_model_input_v1.json"


def load_cfg_r(root: Path) -> dict:
    return json.loads((root / CFG_R).read_text(encoding="utf-8"))


def period_of(year: int) -> str:
    return {2019: "REFERENCE_ONLY", 2020: "PILOT", 2026: "PARTIAL_NON_BLIND"}.get(year, "PRIMARY")


def cusum_ratio(root: Path, cr: dict, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """W3 관측 CUSUM 재실행 → 날짜 × 6종, 12셀 최대 T / crit_w3 (2021–2025, 그 밖 NaN). W3 요약과 대조."""
    wcfg = JP.load_cfg(root / cr["w3_config"])
    out = JP.run_pipeline(JP.load_returns(wcfg, root / "data/raw"), wcfg)
    wins = JP.all_windows(wcfg)
    summ = pd.read_csv(root / cr["w3_individual_summary"], dtype={"ticker": str})
    tk = wcfg["universe"]["tickers"]
    R = {}
    for i, t in enumerate(tk):
        cells = []
        for _, x in summ[summ["ticker"] == t].iterrows():
            T = out.T[i, JP.POLICIES.index(x["policy"]), wins.index(int(x["w"]))]
            assert abs(np.nanmax(T) - x["max_T"]) < 1e-6 and int((T >= x["crit_w3"]).sum()) == x["alarm_days_w3"]
            cells.append(T / x["crit_w3"])
        V = np.vstack(cells)
        ok = np.isfinite(V).any(axis=0)
        R[t] = np.where(ok, np.nanmax(np.where(np.isfinite(V), V, -np.inf), axis=0), np.nan)  # 12셀 모두 결측인 날(연초 w−1일)은 NaN
    df = pd.DataFrame(R, index=pd.DatetimeIndex(out.eval_dates))
    return df.reindex(dates)


def build_features(root: Path, res: dict, x2: dict, cr: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, list[str]]:
    st = res["states"]
    dates = st["dates"]
    eg = st["eg"]
    tickers = list(eg["ticker"])
    es = pd.read_csv(root / "outputs/t18/daily_etf_states.csv.gz", dtype={"ticker": str}, parse_dates=["date"])
    closes = pd.read_csv(root / "outputs/t18/closes_aligned.csv.gz", index_col=0, parse_dates=True).reindex(dates)
    daily = res["daily"].set_index("date").reindex(dates)
    inten = x2["intensity"].set_index("date")["I"].reindex(dates)
    cus = cusum_ratio(root, cr, dates)
    feats = {}
    for t in tickers:
        a = es[(es["ticker"] == t) & (es["q"] == 20)].set_index("date").reindex(dates)
        b6 = es[(es["ticker"] == t) & (es["q"] == 60)].set_index("date").reindex(dates)
        s20 = a["sigma"].to_numpy(float)
        b20 = boundary_sigma(s20, 252, 0.90)
        ok = np.isfinite(a["A"].to_numpy(float)) & (a["ties_A"].to_numpy() == 0)
        assert ((s20[ok] > b20[ok]).astype(float) == a["A"].to_numpy(float)[ok]).all(), t
        r = percent_log_returns_gap(closes[t]).to_numpy()
        f = pd.DataFrame(index=dates)
        f["r"] = r
        f["abs_r"] = np.abs(r)
        f["sigma20"] = s20
        f["sigma60"] = b6["sigma"].to_numpy(float)
        f["ratio20"] = s20 / b20
        f["U20"] = a["U_A"].to_numpy(float)
        f["U60"] = b6["U_A"].to_numpy(float)
        f["peer_L"] = a["L"].to_numpy(float)
        f["peer_UB"] = a["U_B"].to_numpy(float)
        f["breadth"] = daily["n_A_q20"].to_numpy(float) / len(st["groups"])
        f["intensity"] = inten.to_numpy(float)
        c = cus[t].to_numpy(float) if t in cus.columns else np.full(len(dates), np.nan)
        f["cusum_R"] = c
        f["cusum_mask"] = np.isfinite(c).astype(float)
        f["A20"] = a["A"].to_numpy(float)
        f["close"] = closes[t].to_numpy(float)
        assert list(f.columns[:13]) == cr["features"]
        feats[t] = f
    return feats, daily, tickers


def etf_intervals(feats: dict[str, pd.DataFrame], daily: pd.DataFrame, eg: pd.DataFrame, cr: dict) -> pd.DataFrame:
    name = dict(zip(eg["ticker"], eg["name"]))
    grp = dict(zip(eg["ticker"], eg["exposure_group"]))
    rows = []
    for t, f in feats.items():
        dates = f.index
        A = f["A20"].to_numpy(float)
        r = f["r"].to_numpy(float)
        close = f["close"].to_numpy(float)
        for j, iv in enumerate(extract_intervals(A, np.ones(len(A), bool)), start=1):
            s, e = iv["i0"], iv["i1"]
            seg = f.iloc[s:e + 1]
            pk = s + int(np.nanargmax(seg["sigma20"].to_numpy()))
            w = r[pk - 19:pk + 1]
            dev = (w - w.mean()) ** 2
            sh = dev / dev.sum()
            top = pk - 19 + int(np.argmax(sh))
            base = close[s - 1]
            path = np.concatenate([[1.0], close[s:e + 1] / base])
            mdd = float((path / np.maximum.accumulate(path) - 1).min() * 100)
            rows.append({
                "ticker": t, "name": name[t], "exposure_group": grp[t], "interval_id": f"{t}_A20_{j:03d}",
                "start": dates[s].date(), "end": dates[e].date(), "duration": e - s + 1, "period": period_of(dates[s].year),
                "available_from": dates[s + 1].date() if s + 1 < len(dates) else None,
                "end_known_at": dates[e + 1].date() if e + 1 < len(dates) else None,
                "right_censored": e == len(dates) - 1,
                "peak_date": dates[pk].date(), "peak_sigma20": float(f["sigma20"].iloc[pk]), "peak_ratio20": float(f["ratio20"].iloc[pk]),
                "top1_date": dates[top].date(), "top1_r": float(r[top]), "top1_share": float(sh.max()),
                "shock_type": "단일 충격형" if sh.max() >= cr["single_shock_top1_share"] else "누적형",
                "window_exit_end": bool(e + 1 < len(dates) and A[e + 1] == 0 and e + 1 == top + 20),
                "ret_interval_pct": float((close[e] / base - 1) * 100), "max_drawdown_pct": mdd,
                "C1_overlap_days": int((daily["q20_k9"].iloc[s:e + 1] == 1).sum()),
                "max_breadth_17": int(np.nanmax(daily["n_A_q20"].iloc[s:e + 1])),
                "cusum_max_R": float(np.nanmax(f["cusum_R"].iloc[s:e + 1])) if f["cusum_mask"].iloc[s:e + 1].any() else np.nan,
                "i0": s, "i1": e,
            })
    return pd.DataFrame(rows)


def market_intervals(res: dict, x2: dict, feats: dict[str, pd.DataFrame]) -> pd.DataFrame:
    iv = res["intervals"]
    c1 = iv[iv["rule"] == "q20_k9"][["interval_id", "period", "start", "end", "duration_trading_days", "i0", "i1"]].rename(columns={"duration_trading_days": "duration"})
    c1.insert(0, "label", "C1")
    h2 = x2["hysteresis"].query("rule == 'H2'")[["interval_id", "start", "end", "duration", "i0", "i1"]].assign(period="PRIMARY")
    h2.insert(0, "label", "H2")
    wb = x2["wb_intervals"][["interval_id", "start", "end", "duration", "i0", "i1"]].assign(period="PRIMARY")
    wb.insert(0, "label", "WB")
    m = pd.concat([c1, h2, wb], ignore_index=True)
    for t, f in feats.items():
        A = f["A20"].to_numpy(float)
        m[t] = [int((A[a:b + 1] == 1).sum()) for a, b in zip(m["i0"], m["i1"])]
    return m


def split_of(d: pd.Timestamp, cr: dict) -> str:
    for k, (a, b) in cr["splits"].items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return k
    return "none"


def build_datasets(feats: dict[str, pd.DataFrame], daily: pd.DataFrame, etf_iv: pd.DataFrame, cr: dict) -> dict:
    W, H = cr["window"], cr["horizon"]
    fn = cr["features"]
    dates = next(iter(feats.values())).index
    c1 = daily["q20_k9"].to_numpy(float)
    t0 = int(np.searchsorted(dates, pd.Timestamp(cr["start"])))
    split = np.array([split_of(d, cr) for d in dates], dtype=object)
    embargo = np.zeros(len(dates), bool)
    for t in range(len(dates)):
        fut = split[t + 1:t + 1 + H]
        embargo[t] = len(fut) == H and (fut != split[t]).any()
    # 정규화: train 날짜 값만으로 ETF·피처별 평균·표준편차
    norm = {}
    trmask = split == "train"
    for t, f in feats.items():
        v = f[fn].iloc[np.flatnonzero(trmask)]
        norm[t] = {}
        for c in fn:
            if c == "cusum_mask":
                continue
            x = v[c].to_numpy(float)
            x = x[np.isfinite(x)]
            # 값이 없는 채널(CUSUM 이 없는 14종)은 평균 0 · 표준편차 1 로 둔다 (nan_mask 로 결측 위치 보존)
            norm[t][c] = {"mean": float(x.mean()), "std": float(x.std()) or 1.0} if x.size else {"mean": 0.0, "std": 1.0}

    def tensor(t: str, ends: list[int]) -> tuple[np.ndarray, np.ndarray]:
        F = feats[t][fn].to_numpy(float)
        Z = F.copy()
        for k, c in enumerate(fn):
            if c in norm[t]:
                sd = norm[t][c]["std"] if norm[t][c]["std"] > 0 else 1.0
                Z[:, k] = (F[:, k] - norm[t][c]["mean"]) / sd
        nanm = ~np.isfinite(Z)
        Z = np.where(nanm, 0.0, Z)
        X = np.stack([Z[e - W + 1:e + 1] for e in ends]).astype(np.float32) if ends else np.zeros((0, W, len(fn)), np.float32)
        M = np.stack([nanm[e - W + 1:e + 1] for e in ends]) if ends else np.zeros((0, W, len(fn)), bool)
        return X, M

    def fut_any(x: np.ndarray, t: int) -> float:
        if t + H >= len(x):
            return np.nan
        seg = x[t + 1:t + 1 + H]
        return float(np.nanmax(seg) == 1) if np.isfinite(seg).all() else np.nan

    out = {}
    # D1 슬라이딩
    rows, Xs, Ms = [], [], []
    for t, f in feats.items():
        A = f["A20"].to_numpy(float)
        ends = [e for e in range(max(t0, W - 1), len(dates))]
        X, M = tensor(t, ends)
        Xs.append(X)
        Ms.append(M)
        for e in ends:
            rows.append({"ticker": t, "end_date": dates[e].date(), "split": split[e], "embargo": bool(embargo[e]),
                         "y_A20_t": A[e], "y_next5_A20": fut_any(A, e), "y_C1_t": c1[e], "y_next5_C1": fut_any(c1, e)})
    out["D1"] = (pd.DataFrame(rows), np.concatenate(Xs), np.concatenate(Ms))
    # D2 사건 정렬
    rows, Xs, Ms = [], [], []
    pre, post = cr["event_pre"], cr["event_post"]
    for _, r in etf_iv[etf_iv["start"].astype(str) >= cr["start"]].iterrows():
        s = int(r["i0"])
        e = s + post
        if s - pre < 0 or e >= len(dates):
            continue
        X, M = tensor(r["ticker"], [e])
        Xs.append(X)
        Ms.append(M)
        rows.append({"ticker": r["ticker"], "interval_id": r["interval_id"], "window_start": dates[s - pre].date(), "event_start": r["start"],
                     "window_end": dates[e].date(), "onset_index": pre, "duration": int(r["duration"]), "shock_type": r["shock_type"],
                     "split": split[s], "period": r["period"]})
    out["D2"] = (pd.DataFrame(rows), np.concatenate(Xs), np.concatenate(Ms))
    # D3 정상 창 (오토인코더)
    rows, Xs, Ms = [], [], []
    for t, f in feats.items():
        A = f["A20"].to_numpy(float)
        ends = []
        for e in range(max(t0, W - 1), len(dates) - H, cr["normal_stride"]):
            w = A[e - W + 1:e + 1 + H]
            if np.isfinite(w).all() and (w == 0).all():
                ends.append(e)
        X, M = tensor(t, ends)
        Xs.append(X)
        Ms.append(M)
        rows += [{"ticker": t, "end_date": dates[e].date(), "split": split[e], "embargo": bool(embargo[e])} for e in ends]
    out["D3"] = (pd.DataFrame(rows), np.concatenate(Xs), np.concatenate(Ms))
    out["norm"] = norm
    return out


def class_balance(ds: dict) -> pd.DataFrame:
    rows = []
    d1 = ds["D1"][0]
    for sp, g in d1[~d1["embargo"]].groupby("split", sort=False):
        for y in ("y_next5_A20", "y_A20_t", "y_C1_t", "y_next5_C1"):
            v = g[y].dropna()
            rows.append({"dataset": "D1", "split": sp, "label": y, "n": len(v), "positives": int(v.sum()), "rate": float(v.mean()) if len(v) else np.nan})
    for name in ("D2", "D3"):
        for sp, g in ds[name][0].groupby("split", sort=False):
            rows.append({"dataset": name, "split": sp, "label": "-", "n": len(g), "positives": np.nan, "rate": np.nan})
    return pd.DataFrame(rows)


def run(root: Path, res: dict, x2: dict) -> dict:
    cr = load_cfg_r(root)
    for line in (root / OUT_DIR / "CONTRACT_FREEZE_SHA256_MODEL_INPUT.txt").read_text().splitlines():
        dg, nm = line.split(maxsplit=1)
        assert sha(root / nm) == dg, f"PART R 명세 변경: {nm}"
    feats, daily, tickers = build_features(root, res, x2, cr)
    eiv = etf_intervals(feats, daily, res["states"]["eg"], cr)
    miv = market_intervals(res, x2, feats)
    ds = build_datasets(feats, daily, eiv, cr)
    cb = class_balance(ds)
    rd = root / OUT_DIR / "results"
    write_csv(eiv, rd / "model_intervals_etf.csv")
    write_csv(miv, rd / "model_intervals_market.csv")
    for k in ("D1", "D2", "D3"):
        write_csv(ds[k][0], rd / f"model_dataset_index_{k}.csv")
    write_csv(cb, rd / "model_class_balance.csv")
    (rd / "normalization.json").write_text(json.dumps(ds["norm"], ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"spec": "research/common_volatility_candidates_10/MODEL_INPUT_SPEC.md", "window": cr["window"], "horizon": cr["horizon"],
                "features": cr["features"], "task_excluded_features": cr["task_excluded_features"], "splits": cr["splits"],
                "datasets": {k: {"n": int(len(ds[k][0])), "X_shape": list(ds[k][1].shape), "index": f"results/model_dataset_index_{k}.csv",
                                 "tensor": f"{cr['out_private']}/model_windows_{k}.npz"} for k in ("D1", "D2", "D3")},
                "tickers": tickers, "normalization": "results/normalization.json (train 날짜 값만, cusum_mask 제외)",
                "nan_policy": "정규화 후 NaN → 0, nan_mask 로 위치 보존"}
    (rd / "model_feature_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    priv = root / cr["out_private"]
    priv.mkdir(parents=True, exist_ok=True)
    for k in ("D1", "D2", "D3"):
        np.savez_compressed(priv / f"model_windows_{k}.npz", X=ds[k][1], nan_mask=ds[k][2], features=np.array(cr["features"]))
    return {"cfg": cr, "feats": feats, "etf_intervals": eiv, "market_intervals": miv, "datasets": ds, "class_balance": cb, "manifest": manifest}
