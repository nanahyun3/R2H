"""10-lock-2 확장 — 우연 기준선 k*, 자산군 균형, 이력 구간, 연속 강도 지수, 20→60일 시차, C1 바텀업.

입력은 lock-1 ``pipeline.run()`` 결과와 09 의 ETF 상태(outputs/t18). lock-1 결과는 바꾸지 않는다.
"""

from __future__ import annotations

import bisect
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.common_vol.core import extract_intervals, rule_id
from r2h.common_vol.pipeline import OUT_DIR, sha, write_csv
from r2h.peer_shock.core import percent_log_returns_gap

CFG2_PATH = "configs/t19_common_vol_candidates_v2.json"


def load_cfg2(root: Path) -> dict:
    return json.loads((root / CFG2_PATH).read_text(encoding="utf-8"))


# ── 1. 우연 기준선 ─────────────────────────────────────────────────────────
def circular_null(a: np.ndarray, reps: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """a: (일 × 그룹) 0/1. 그룹마다 독립 원형 이동 → (P_day[k], P_fw[k]), k = 0..G."""
    n, g = a.shape
    day_counts = np.zeros(g + 2)
    fw_counts = np.zeros(g + 2)
    idx = np.arange(n)
    for _ in range(reps):
        off = rng.integers(1, n, size=g)
        sh = a[(idx[:, None] - off[None, :]) % n, np.arange(g)[None, :]]
        na = sh.sum(axis=1).astype(int)
        hist = np.bincount(na, minlength=g + 2)
        day_counts += hist[::-1].cumsum()[::-1]  # 날짜별 N_A ≥ k 개수
        fw_counts[: na.max() + 1] += 1  # 최대값 ≥ k
    return day_counts[: g + 1] / (reps * n), fw_counts[: g + 1] / reps


def kstar(p: np.ndarray, alpha: float) -> int:
    ok = np.flatnonzero(p < alpha)
    return int(ok[0]) if ok.size else -1


def null_table(st: dict, daily: pd.DataFrame, cfg2: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(cfg2["seed"])
    prim = (daily["period"] == "PRIMARY").to_numpy()
    rows, ks = [], []
    for q in cfg2["null"]["q_list"]:
        a = st["mats"][q]["A"][prim]
        assert np.isfinite(a).all()
        pd_, pf = circular_null(a.astype(int), cfg2["null"]["reps"], rng)
        obs = a.sum(axis=1)
        for k in range(a.shape[1] + 1):
            rows.append({"q": q, "k": k, "p_day_null": pd_[k], "p_fw_null": pf[k],
                         "obs_days": int((obs >= k).sum()), "obs_share": float((obs >= k).mean()),
                         "expected_days_null": float(pd_[k] * len(obs))})
        ks.append({"q": q, "k_star_day": kstar(pd_, cfg2["null"]["day_alpha"]), "k_star_fw": kstar(pf, cfg2["null"]["fw_alpha"]),
                   "obs_max": int(obs.max()), "null_mean_N_A": float(a.sum() / len(obs))})
    return pd.DataFrame(rows), pd.DataFrame(ks)


# ── 2. 자산군 균형 ─────────────────────────────────────────────────────────
def class_split(st: dict, cfg2: dict) -> tuple[list[int], list[int]]:
    eg = st["eg"].drop_duplicates("exposure_group").set_index("exposure_group")
    cat = eg.loc[st["groups"], "category"]
    eq = [i for i, c in enumerate(cat) if c in cfg2["asset_class"]["equity_categories"]]
    ne = [i for i, c in enumerate(cat) if c in cfg2["asset_class"]["non_equity_categories"]]
    assert len(eq) + len(ne) == len(st["groups"])
    return eq, ne


def balance(st: dict, daily: pd.DataFrame, cfg2: dict) -> pd.DataFrame:
    eq, ne = class_split(st, cfg2)
    a = st["mats"][20]["A"]
    out = pd.DataFrame({"date": daily["date"], "period": daily["period"]})
    out["n_eq"] = (a[:, eq] == 1).sum(axis=1)
    out["n_non"] = (a[:, ne] == 1).sum(axis=1)
    out["W"] = (out["n_eq"] / len(eq) + out["n_non"] / len(ne)) / 2
    full = np.isfinite(a).all(axis=1)
    thr = cfg2["asset_class"]["balanced_threshold_from_k"] / len(st["groups"])
    out["WB"] = np.where(full, (out["W"] >= thr - 1e-12).astype(float), np.nan)
    out.attrs["n_eq_groups"], out.attrs["n_non_groups"], out.attrs["thr"] = len(eq), len(ne), thr
    return out


# ── 3. 이력 구간 ───────────────────────────────────────────────────────────
def hysteresis(n_a: np.ndarray, valid: np.ndarray, k_in: int, k_out: int, mask: np.ndarray) -> list[tuple[int, int]]:
    """N_A ≥ k_in 에서 진입, N_A ≥ k_out 인 동안 유지. NA(valid=False) 는 끊는 경계. mask 밖은 보지 않는다."""
    idx = np.flatnonzero(mask)
    out, on, s = [], False, 0
    for t in idx:
        if not valid[t]:
            if on:
                out.append((s, t - 1))
            on = False
            continue
        if not on and n_a[t] >= k_in:
            on, s = True, t
        elif on and n_a[t] < k_out:
            out.append((s, t - 1))
            on = False
    if on:
        out.append((s, idx[-1]))
    return out


# ── 4. 연속 강도 지수 ──────────────────────────────────────────────────────
def boundary_sigma(x: np.ndarray, min_ref: int, upper: float) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    ref: list[float] = []
    for t, v in enumerate(x):
        n = len(ref)
        if n >= min_ref:
            out[t] = ref[math.ceil(upper * n - 1e-9) - 1]
        if np.isfinite(v):
            bisect.insort(ref, float(v))
    return out


def intensity(root: Path, st: dict, daily: pd.DataFrame, cfg2: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    ic = cfg2["intensity"]
    es = pd.read_csv(root / cfg2["etf_states"], dtype={"ticker": str}, parse_dates=["date"])
    es = es[es["q"] == ic["q"]]
    dates = st["dates"]
    ratio = {}
    for t, x in es.groupby("ticker"):
        x = x.set_index("date").reindex(dates)
        s = x["sigma"].to_numpy(float)
        b = boundary_sigma(s, ic["min_ref"], ic["A_upper"])
        a = x["A"].to_numpy(float)
        ok = np.isfinite(a) & (x["ties_A"].to_numpy() == 0)
        assert ((s[ok] > b[ok]).astype(float) == a[ok]).all(), f"경계 σ 와 A 불일치 {t}"
        ratio[t] = s / b
    cols = {}
    for g in st["groups"]:
        if g in ratio:
            cols[g] = ratio[g]
        else:
            cols[g] = np.fmin(*[ratio[t] for t in ic["kospi_core_pair"]])  # AND 규칙과 같은 방향
    R = pd.DataFrame(cols, index=dates)
    E = (R - 1).clip(lower=0)
    I = E.sum(axis=1, min_count=len(st["groups"]))
    out = pd.DataFrame({"date": dates, "I": I.to_numpy(), "n_A_q20": daily["n_A_q20"].to_numpy(), "period": daily["period"].to_numpy()})
    contrib = E.copy()
    contrib.insert(0, "date", dates)
    return out, contrib.reset_index(drop=True)


def top_peaks(s: pd.Series, k: int, sep: int) -> list[int]:
    """값이 큰 순으로 고르되 이미 고른 날과 sep 거래일 이상 떨어진 날만 (탐욕)."""
    order = np.argsort(-s.to_numpy(float))
    chosen: list[int] = []
    for i in order:
        if not np.isfinite(s.iloc[i]):
            continue
        if all(abs(i - j) >= sep for j in chosen):
            chosen.append(int(i))
        if len(chosen) == k:
            break
    return chosen


# ── 5. 시차 ────────────────────────────────────────────────────────────────
def lead_lag(daily: pd.DataFrame, max_lag: int) -> pd.DataFrame:
    p = daily[daily["period"] == "PRIMARY"]
    a, b = p["n_A_q20"].to_numpy(float), p["n_A_q60"].to_numpy(float)
    rows = []
    for L in range(0, max_lag + 1):
        x, y = a[: len(a) - L], b[L:]
        rows.append({"lag": L, "corr": float(np.corrcoef(x, y)[0, 1])})
    return pd.DataFrame(rows)


# ── 6. C1 바텀업 ───────────────────────────────────────────────────────────
def c1_bottomup(root: Path, st: dict, daily: pd.DataFrame, iv: pd.DataFrame, cfg2: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    q, win = cfg2["c1_bottomup"]["q"], cfg2["c1_bottomup"]["window"]
    closes = pd.read_csv(root / "outputs/t18/closes_aligned.csv.gz", index_col=0, parse_dates=True).reindex(st["dates"])
    rep = {g: (g if g in closes.columns else cfg2["intensity"]["kospi_core_pair"][0]) for g in st["groups"]}
    rets = {g: percent_log_returns_gap(closes[rep[g]]).to_numpy() for g in st["groups"]}
    a = st["mats"][q]["A"]
    c1 = iv[(iv["rule"] == rule_id(20, 9)) & (iv["period"] == "PRIMARY")]
    entry_rows, exit_rows = [], []
    for _, r in c1.iterrows():
        s, e = int(r["i0"]), int(r["i1"])
        for j, g in enumerate(st["groups"]):
            on = np.flatnonzero(a[s:e + 1, j] == 1)
            if not on.size:
                continue
            t0 = s + int(on[0])
            k = t0
            while k - 1 >= 0 and a[k - 1, j] == 1:
                k -= 1
            entry_rows.append({"interval_id": r["interval_id"], "group": g, "label": st["label"][g], "entry_date": st["dates"][k].date(),
                               "entry_offset_vs_interval": int(k - s), "days_in_interval": int(on.size)})
        x = e + 1
        if x < len(daily):
            for j, g in enumerate(st["groups"]):
                if a[e, j] == 1 and a[x, j] == 0:
                    w = rets[g][e - win + 1:e + 1]
                    dev = (w - np.nanmean(w)) ** 2
                    sh = dev / np.nansum(dev)
                    top = e - win + 1 + int(np.nanargmax(sh))
                    exit_rows.append({"interval_id": r["interval_id"], "group": g, "label": st["label"][g], "exit_date": st["dates"][x].date(),
                                      "top_day": st["dates"][top].date(), "top_r": float(rets[g][top]), "top_share": float(np.nanmax(sh)),
                                      "window_exit": bool(x == top + win)})
    return pd.DataFrame(entry_rows), pd.DataFrame(exit_rows)


def interval_rows(flags_or_pairs, daily: pd.DataFrame, rid: str, n_a_col: str) -> pd.DataFrame:
    rows = []
    for j, (s, e) in enumerate(flags_or_pairs, start=1):
        seg = daily.loc[s:e, n_a_col]
        rows.append({"rule": rid, "interval_id": f"{rid}_{j:03d}", "start": daily.loc[s, "date"].date(), "end": daily.loc[e, "date"].date(),
                     "duration": e - s + 1, "max_n_A": int(seg.max()), "min_n_A": int(seg.min()), "i0": s, "i1": e})
    return pd.DataFrame(rows)


def run(root: Path, res: dict) -> dict:
    cfg2 = load_cfg2(root)
    for line in (root / OUT_DIR / "CONTRACT_FREEZE_SHA256_LOCK2.txt").read_text().splitlines():
        dg, name = line.split(maxsplit=1)
        assert sha(root / name) == dg, f"lock-2 동결 파일 변경: {name}"
    st, daily, iv = res["states"], res["daily"], res["intervals"]
    prim = (daily["period"] == "PRIMARY").to_numpy()
    nt, ks = null_table(st, daily, cfg2)
    bal = balance(st, daily, cfg2)
    wb = interval_rows([(r["i0"], r["i1"]) for r in extract_intervals(bal["WB"].to_numpy(), prim)], daily, "WB", "n_A_q20")
    valid = (daily["n_eval_A_q20"] == len(st["groups"])).to_numpy()
    hy = pd.concat([interval_rows(hysteresis(daily["n_A_q20"].to_numpy(), valid, h["k_in"], h["k_out"], prim), daily, h["id"], "n_A_q20")
                    for h in cfg2["hysteresis"]], ignore_index=True)
    inten, contrib = intensity(root, st, daily, cfg2)
    ll = lead_lag(daily, cfg2["lead_lag"]["max_lag"])
    ent, ext = c1_bottomup(root, st, daily, iv, cfg2)
    pi = inten[inten["period"] == "PRIMARY"].reset_index()
    peaks = pi.loc[top_peaks(pi["I"], cfg2["intensity"]["top_peaks"], 20)].sort_values("date")
    peak_rows = []
    for _, r in peaks.iterrows():
        c = contrib.loc[r["index"], st["groups"]].sort_values(ascending=False)
        peak_rows.append({"date": r["date"].date(), "I": float(r["I"]), "n_A_q20": int(r["n_A_q20"]), "C1": bool(daily.loc[r["index"], "q20_k9"] == 1),
                          "top3": "; ".join(f"{st['label'][g]} {v:.2f}" for g, v in c.head(3).items()), "n_groups_positive": int((c > 0).sum())})
    c1 = iv[(iv["rule"] == rule_id(20, 9)) & (iv["period"] == "PRIMARY")]
    c1peak = []
    for _, r in c1.iterrows():
        seg = inten.loc[r["i0"]:r["i1"], "I"]
        i = int(seg.idxmax())
        c = contrib.loc[i, st["groups"]].sort_values(ascending=False)
        eq, ne = class_split(st, cfg2)
        eqset = {st["groups"][k] for k in eq}
        c1peak.append({"interval_id": r["interval_id"], "peak_date": daily.loc[i, "date"].date(), "I": float(seg.max()),
                       "equity_share": float(c[[g for g in c.index if g in eqset]].sum() / c.sum()),
                       "top3": "; ".join(f"{st['label'][g]} {v:.2f}" for g, v in c.head(3).items())})
    from scipy.stats import spearmanr
    rho = float(spearmanr(pi["I"], pi["n_A_q20"]).statistic)
    two_d = bal[bal["period"] == "PRIMARY"].groupby(["n_eq", "n_non"]).size().rename("days").reset_index()
    out = {"cfg2": cfg2, "null": nt, "kstar": ks, "balance": bal, "balance_2d": two_d, "wb_intervals": wb, "hysteresis": hy,
           "intensity": inten, "contrib": contrib, "intensity_peaks": pd.DataFrame(peak_rows), "c1_intensity_peak": pd.DataFrame(c1peak),
           "rho_I_NA": rho, "lead_lag": ll, "c1_entry": ent, "c1_exit": ext}
    rd = root / OUT_DIR / "results"
    for name in ("null", "kstar", "balance_2d", "wb_intervals", "hysteresis", "intensity_peaks", "c1_intensity_peak", "lead_lag", "c1_entry", "c1_exit"):
        write_csv(out[name], rd / f"lock2_{name}.csv")
    d2 = bal[["date", "period", "n_eq", "n_non", "W", "WB"]].copy()
    d2["I"] = inten["I"].to_numpy()
    d2["date"] = d2["date"].dt.date
    write_csv(d2, rd / "lock2_daily.csv")
    return out
