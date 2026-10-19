"""정책 CUSUM 의 연환산변동성 국면·선행후행·이벤트 정렬 반응 (12B-lock-1 `regimes`·`events`·`lead_lag`).

모두 서술 분석 (관측 귀무 부적합 → NULL_MODEL_INVALID_DESCRIPTIVE). NA 는 0 으로 채우지 않고 유효 수(coverage)를 함께 낸다.
양방향 Page 는 upper/h_up · lower/h_down 을 따로 두고 하나의 비율로 합치지 않는다. 유의성은 거르는 조건이 아니다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from r2h.k200_overlay import regimes as R

LABEL = "NULL_MODEL_INVALID_DESCRIPTIVE"
MATS = ("T_past_pct", "cusum_raw_T", "cusum_alarm_a05", "T_over_h", "upper_over_h_up", "lower_over_h_down", "T_posthoc_pct")
META = ("family", "changed_variable", "detector_type", "window_w", "policy_id", "reset_rule")
REL = np.arange(-60, 121)


# ---------- 공통 ----------
def to_matrices(al: pd.DataFrame, dates: pd.Series) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """(실험, 날짜) 정렬 원장 → (실험 메타, {열: (n_exp, n_day) 행렬}). 날짜축·실험 상수성 검증."""
    nd = len(dates)
    ne = len(al) // nd
    if ne * nd != len(al):
        raise AssertionError("행 수가 날짜 수의 배수가 아님")
    ids = al["experiment_id"].to_numpy().reshape(ne, nd)
    if not (ids == ids[:, :1]).all():
        raise AssertionError("실험 경계 불일치")
    dd = al["date"].to_numpy().reshape(ne, nd)
    if not (dd == pd.to_datetime(dates).to_numpy()[None, :]).all():
        raise AssertionError("날짜축 불일치")
    meta = al.iloc[::nd][["experiment_id", *META]].reset_index(drop=True)
    mats = {c: al[c].to_numpy(float).reshape(ne, nd) for c in MATS}
    return meta, mats


def spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    """둘 다 유한한 날의 평균 순위 Spearman ρ. 분산 0 이면 NaN (0 아님)."""
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 3:
        return np.nan, n
    rx = pd.Series(x[ok]).rank().to_numpy()
    ry = pd.Series(y[ok]).rank().to_numpy()
    sx, sy = rx.std(), ry.std()
    if sx <= 0 or sy <= 0:
        return np.nan, n
    return float(((rx - rx.mean()) * (ry - ry.mean())).mean() / (sx * sy)), n


def _nanstat(f, x: np.ndarray, axis: int = 1) -> np.ndarray:
    """전부 NaN 인 행은 경고 없이 NaN."""
    ok = np.isfinite(x).any(axis=axis)
    out = np.full(x.shape[0], np.nan)
    if ok.any():
        out[ok] = f(x[ok], axis=axis)
    return out


def diff1(x: np.ndarray) -> np.ndarray:
    """1차 차분 (첫 날 NaN, 어느 한쪽 NaN 이면 NaN)."""
    return np.r_[np.nan, np.diff(x)]


# ---------- 1. 국면 행렬 ----------
def regime_cells(lv: np.ndarray, ch: np.ndarray) -> list[tuple[str, str, np.ndarray]]:
    """12칸 + 수준 주변 4 + 변화 주변 3 + NA. (cell_type, cell, 날짜 마스크)."""
    out = []
    for a in R.LEVELS:
        for b in R.CHANGES:
            out.append(("level|change", f"{a}|{b}", (lv == a) & (ch == b)))
    out += [("level_only", a, lv == a) for a in R.LEVELS]
    out += [("change_only", b, ch == b) for b in R.CHANGES]
    out.append(("NA", "NA", (lv == "NA") | (ch == "NA")))
    return out


def regime_matrix(meta: pd.DataFrame, M: dict[str, np.ndarray], reg: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tp, al = M["T_past_pct"], M["cusum_alarm_a05"]
    valid = np.isfinite(tp)
    for aw, g in reg.groupby("anchor_w", sort=True):
        for var, lc, cc in (("PAST", "level_past", "change_past"), ("POSTHOC", "level_posthoc", "change_posthoc")):
            for ctype, cell, m in regime_cells(g[lc].to_numpy(), g[cc].to_numpy()):
                v = valid & m[None, :]
                nv = v.sum(1)
                d = {"anchor_w": aw, "regime_variant": var, "cell_type": ctype, "cell": cell,
                     "n_days_cell": int(m.sum()), "n_valid": nv}
                d["coverage"] = np.where(m.sum() > 0, nv / max(m.sum(), 1), np.nan)
                X = np.where(v, tp, np.nan)
                d["mean_T_past_pct"] = _nanstat(np.nanmean, X)
                d["median_T_past_pct"] = _nanstat(np.nanmedian, X)
                d["mean_T_posthoc_pct"] = _nanstat(np.nanmean, np.where(m[None, :], M["T_posthoc_pct"], np.nan))
                d["alarm_a05_days_valid"] = (v & (al == 1)).sum(1)
                d["alarm_rate_a05_over_n_valid"] = np.where(nv > 0, d["alarm_a05_days_valid"] / np.maximum(nv, 1), np.nan)
                for c in ("T_over_h", "upper_over_h_up", "lower_over_h_down"):
                    Y = np.where(m[None, :], M[c], np.nan)
                    d[f"mean_{c}"] = _nanstat(np.nanmean, Y)
                    d[f"n_{c}"] = np.isfinite(Y).sum(1)
                f = pd.DataFrame(d)
                f.insert(0, "experiment_id", meta["experiment_id"].to_numpy())
                rows.append(f)
    out = pd.concat(rows, ignore_index=True)
    out = meta.merge(out, on="experiment_id")
    out["posthoc_label"] = np.where(out["regime_variant"] == "POSTHOC", "POSTHOC", "")
    out["label"] = LABEL
    return out


# ---------- 2. 연환산변동성 반응 ----------
def vol_response(meta: pd.DataFrame, M: dict[str, np.ndarray], mk: pd.DataFrame, r20: pd.DataFrame) -> pd.DataFrame:
    tp = M["T_past_pct"]
    ex = (mk["date"].dt.year != 2020).to_numpy()
    tgt = {f"vol{w}": mk[f"annualized_vol_{w}"].to_numpy(float) for w in (20, 60, 120)}
    tgt |= {"d5": r20["d5"].to_numpy(float), "d20": r20["d20"].to_numpy(float)}
    lv, ch = r20["level_past"].to_numpy(), r20["change_past"].to_numpy()
    groups = {"EXP": ch == "EXPANDING", "STA": ch == "STABLE", "CON": ch == "CONTRACTING",
              "HISTA": np.isin(lv, ["HIGH", "EXTREME"]) & (ch == "STABLE"), "LOSTA": np.isin(lv, ["LOW", "MID"]) & (ch == "STABLE")}
    rows = []
    for i, eid in enumerate(meta["experiment_id"]):
        x = tp[i]
        d = {"experiment_id": eid}
        for k, y in tgt.items():
            for suf, msk in (("", np.ones_like(ex)), ("_ex2020", ex)):
                rho, n = spearman(np.where(msk, x, np.nan), y)
                d[f"rho_{k}{suf}"], d[f"n_{k}{suf}"] = rho, n
        mu = {}
        for g, m in groups.items():
            v = m & np.isfinite(x)
            mu[g] = float(x[v].mean()) if v.any() else np.nan
            d[f"n_{g}"] = int(v.sum())
        d["contrast_EXPANDING_minus_STABLE"] = mu["EXP"] - mu["STA"]
        d["contrast_CONTRACTING_minus_STABLE"] = mu["CON"] - mu["STA"]
        d["contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE"] = mu["HISTA"] - mu["LOSTA"]
        rows.append(d)
    out = meta.merge(pd.DataFrame(rows), on="experiment_id")
    out["anchor_w_contrast"] = 20
    out["label"] = LABEL
    return out


# ---------- 3. 선행후행 ----------
def lead_lag(policy: np.ndarray, market: np.ndarray, lags=range(-20, 21), keep: np.ndarray | None = None) -> pd.DataFrame:
    """ρ(policy[t+k], market[t]). k>0: 정책이 시장보다 늦음. keep 이 주어지면 t, t+k 모두 keep 인 쌍만."""
    n = policy.size
    keep = np.ones(n, bool) if keep is None else keep
    rows = []
    for k in lags:
        if k >= 0:
            p, m, kp, km = policy[k:], market[: n - k], keep[k:], keep[: n - k]
        else:
            p, m, kp, km = policy[: n + k], market[-k:], keep[: n + k], keep[-k:]
        ok = kp & km
        rho, nn = spearman(np.where(ok, p, np.nan), np.where(ok, m, np.nan))
        rows.append({"lag_k": k, "rho": rho, "n": nn})
    return pd.DataFrame(rows)


def lead_lag_all(meta: pd.DataFrame, M: dict[str, np.ndarray], mk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dm = diff1(np.log(mk["annualized_vol_20"].to_numpy(float)))
    ex = (mk["date"].dt.year != 2020).to_numpy()
    long, peak = [], []
    for i, eid in enumerate(meta["experiment_id"]):
        dp = diff1(M["T_past_pct"][i])
        a = lead_lag(dp, dm)
        b = lead_lag(dp, dm, keep=ex)
        t = a.rename(columns={"rho": "rho", "n": "n"}).assign(rho_ex2020=b["rho"].to_numpy(), n_ex2020=b["n"].to_numpy())
        t.insert(0, "experiment_id", eid)
        long.append(t)
        d = {"experiment_id": eid}
        for suf, tt in (("", a), ("_ex2020", b)):
            f = tt[np.isfinite(tt["rho"])]
            if len(f):
                j = f["rho"].abs().to_numpy().argmax()
                d[f"peak_lag{suf}"], d[f"rho_peak{suf}"] = int(f["lag_k"].iloc[j]), float(f["rho"].iloc[j])
            else:
                d[f"peak_lag{suf}"], d[f"rho_peak{suf}"] = np.nan, np.nan
            d[f"rho_lag0{suf}"] = float(tt.loc[tt.lag_k == 0, "rho"].iloc[0])
            d[f"n_lag0{suf}"] = int(tt.loc[tt.lag_k == 0, "n"].iloc[0])
        peak.append(d)
    lab = "DESCRIPTIVE (no inference; serial dependence); " + LABEL
    L = meta[["experiment_id", "family", "detector_type", "window_w"]].merge(pd.concat(long, ignore_index=True), on="experiment_id")
    P = meta[["experiment_id", "family", "detector_type", "window_w"]].merge(pd.DataFrame(peak), on="experiment_id")
    L["label"], P["label"] = lab, lab
    return L, P


# ---------- 4. 이벤트 정렬 ----------
def event_aligned(meta: pd.DataFrame, M: dict[str, np.ndarray], mk: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """실험 × 이벤트 × rel ∈ [−60,120]. 날짜축 밖은 in_range=False, 값 NaN 으로 남김."""
    nd = len(mk)
    v20 = mk["annualized_vol_20"].to_numpy(float)
    ne = len(meta)
    parts = []
    for e in ev.itertuples(index=False):
        dur = int(e.i_end - e.i_start)
        pos = int(e.i_start) + REL
        inr = (pos >= 0) & (pos < nd)
        pc = np.clip(pos, 0, nd - 1)
        ph = np.array([R.phase_of(int(r), dur) for r in REL], dtype=object)

        def g(X: np.ndarray) -> np.ndarray:
            return np.where(inr[None, :], X[:, pc], np.nan).ravel()

        f = pd.DataFrame({
            "experiment_id": np.repeat(meta["experiment_id"].to_numpy(), REL.size),
            "event_set": e.event_set, "event_id": e.interval_id, "period": e.period, "shock_type": e.shock_type,
            "i_start": int(e.i_start), "dur": dur, "rel": np.tile(REL, ne), "phase": np.tile(ph, ne),
            "in_range": np.tile(inr, ne),
            "date": np.tile(pd.Series(mk["date"].to_numpy()[pc]).where(inr).to_numpy(), ne),
            "T_past_pct": g(M["T_past_pct"]), "T_raw": g(M["cusum_raw_T"]), "alarm_a05": g(M["cusum_alarm_a05"]),
            "annualized_vol_20": np.tile(np.where(inr, v20[pc], np.nan), ne)})
        parts.append(f)
    out = pd.concat(parts, ignore_index=True)
    out["label"] = LABEL
    return out


def event_phase_summary(ea: pd.DataFrame) -> pd.DataFrame:
    x = ea.assign(valid=np.isfinite(ea["T_past_pct"]), alarm_ok=np.isfinite(ea["alarm_a05"]))
    g = x.groupby(["experiment_id", "event_set", "shock_type", "phase"], sort=True)
    out = g.agg(mean_T_past_pct=("T_past_pct", "mean"), n_valid=("valid", "sum"), n_total=("rel", "size"),
                n_in_range=("in_range", "sum"), alarm_share_a05_in_range=("alarm_a05", "mean"),
                n_alarm_known=("alarm_ok", "sum")).reset_index()
    out["coverage"] = out["n_valid"] / out["n_total"]
    out["label"] = LABEL
    return out


def shock_type_response(ea: pd.DataFrame) -> pd.DataFrame:
    a = ea[(ea["event_set"] == "A_t20") & ea["phase"].isin(["onset", "during"])]
    rows = []
    for scope, s in (("PRIMARY", a[a["period"] == "PRIMARY"]), ("ALL", a)):
        for eid, h in s.groupby("experiment_id", sort=True):
            d = {"experiment_id": eid, "scope": scope}
            for nm, key in (("cumulative", "누적형"), ("single", "단일 충격형")):
                v = h.loc[h["shock_type"] == key, "T_past_pct"]
                d[f"mean_T_past_pct_{nm}"] = float(v.mean()) if v.notna().any() else np.nan
                d[f"n_valid_{nm}"] = int(v.notna().sum())
                d[f"n_total_{nm}"] = int(len(v))
                d[f"n_events_{nm}"] = int(h.loc[h["shock_type"] == key, "event_id"].nunique())
            d["diff_cumulative_minus_single"] = d["mean_T_past_pct_cumulative"] - d["mean_T_past_pct_single"]
            rows.append(d)
    out = pd.DataFrame(rows)
    out["phases"] = "onset+during"
    out["label"] = LABEL
    return out


# ---------- 5. 연도별 안정성 ----------
def yearly_stability(meta: pd.DataFrame, M: dict[str, np.ndarray], mk: pd.DataFrame, r20: pd.DataFrame) -> pd.DataFrame:
    yr = mk["date"].dt.year.to_numpy()
    v20, d20 = mk["annualized_vol_20"].to_numpy(float), r20["d20"].to_numpy(float)
    rows = []
    for i, eid in enumerate(meta["experiment_id"]):
        x, al = M["T_past_pct"][i], M["cusum_alarm_a05"][i]
        ys = {}
        for y in sorted(np.unique(yr)):
            m = yr == y
            xv = np.where(m, x, np.nan)
            r1, n1 = spearman(xv, v20)
            r2, _ = spearman(xv, d20)
            ys[y] = r1
            rows.append({"experiment_id": eid, "calendar_year": str(y), "n_days": int(m.sum()), "n_valid": n1,
                         "mean_T_past_pct": float(np.nanmean(xv)) if n1 else np.nan,
                         "rho_vol20_level": r1, "rho_d20": r2, "alarm_days_a05": int((al[m] == 1).sum())})
        pm = yr >= 2021
        rp, n = spearman(np.where(pm, x, np.nan), v20)
        rd, _ = spearman(np.where(pm, x, np.nan), d20)
        sg = [ys[y] for y in range(2021, 2026)]
        fin = [s for s in sg if np.isfinite(s)]
        same = sum(1 for s in fin if np.isfinite(rp) and np.sign(s) == np.sign(rp))
        rows.append({"experiment_id": eid, "calendar_year": "POOLED_2021_2025", "n_days": int(pm.sum()), "n_valid": n,
                     "mean_T_past_pct": float(np.nanmean(np.where(pm, x, np.nan))) if n else np.nan,
                     "rho_vol20_level": rp, "rho_d20": rd, "alarm_days_a05": int((al[pm] == 1).sum()),
                     "n_years_finite_2021_2025": len(fin), "n_years_same_sign_as_pooled": same})
    out = meta[["experiment_id", "family", "detector_type", "window_w"]].merge(pd.DataFrame(rows), on="experiment_id")
    out["label"] = LABEL
    return out
