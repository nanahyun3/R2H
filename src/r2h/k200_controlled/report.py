"""12번 결과 조립 — 관측 계산 · 귀무표 부착 · 위약 · 변화점 요약 · SVR 요약 · 합성 요약 · AE 피처 분석 · CSV 쓰기.

결과 CSV 는 결정적(정렬·반올림 고정)으로 써서 노트북 경로와 스크립트 경로가 바이트 동일해야 한다.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from . import analysis as A
from . import audit as AU
from . import calib as K
from . import core as C
from . import observed as O

ROUND = 10


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format=f"%.{ROUND}g", lineterminator="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_hold(null_dir: Path, pipelines) -> dict[str, np.ndarray]:
    out = {}
    for pl in pipelines:
        f = null_dir / f"e__null_hold__S00_null__{pl}.npy"
        if not f.exists():  # 파일럿 MC 에는 홀드아웃이 없다 — 보정 집합으로 대신 (파일럿 시험 전용)
            f = null_dir / f"e__null_cal__S00_null__{pl}.npy"
        if f.exists():
            out[pl] = np.load(f)
    return out


# ── E5 위약 ────────────────────────────────────────────────────────


def placebo_metrics(ob: O.Observed, e: np.ndarray, det: str, resets: list[int], crit, evm: np.ndarray) -> dict:
    if det == "rolling_cos":
        T = C.rolling_segmented(e, 60, resets)
        al = np.nan_to_num(T, nan=-np.inf) >= crit
    else:
        hu, hd = crit
        Su, Sd = C.page_free(e, 2.0, resets)[0], C.page_free(e, 0.5, resets)[0]
        T = np.fmax(Su, Sd)
        al = C.page_alarm(e, 2.0, hu, resets)[1] | C.page_alarm(e, 0.5, hd, resets)[1]
    pc = O.own_percentile(T)
    return {"alarm_days": int(al.sum()), "event_alarm_days": int((al & evm).sum()),
            "event_mean_pctile": float(np.nanmean(pc[evm])) if np.isfinite(pc[evm]).any() else np.nan,
            "valid_days": int(np.isfinite(T).sum())}


def placebo_table(ob: O.Observed, cal: dict, seed: int, draws: int = 200) -> pd.DataFrame:
    """규칙 × q × gap (102) × {rolling w60, page_two}: 실제 트리거 vs 같은 횟수 달력·무작위·이동 위약 (α=0.20 임계)."""
    n = len(ob.m.eval_dates)
    evm = O.event_mask(ob.events, n)
    e = ob.paths["B1"].e
    rows = []
    for (rule, q, g), eff in sorted(ob.cp_effect.items()):
        reset = f"cp:{rule}:{q}:{g}"
        for det, w in (("rolling_cos", "60"), ("page_two", "NA")):
            crit = cal["res"][("B1", det, w, reset)]["crit"][0.20]
            real = placebo_metrics(ob, e, det, list(eff), crit, evm)
            rng = np.random.default_rng([seed, 5, int(g), int(q * 100), sum(map(ord, rule)), 0 if det == "rolling_cos" else 1])
            pl_r = [placebo_metrics(ob, e, det, K.placebo_random(n, len(eff), int(g), rng), crit, evm) for _ in range(draws)]
            pl_s = [placebo_metrics(ob, e, det, K.placebo_shift(list(eff), n, rng), crit, evm) for _ in range(draws)]
            pl_c = placebo_metrics(ob, e, det, K.placebo_calendar(n, len(eff)), crit, evm)
            for metric in ("alarm_days", "event_alarm_days", "event_mean_pctile", "valid_days"):
                vr = np.array([d[metric] for d in pl_r], float)
                vs = np.array([d[metric] for d in pl_s], float)
                rows.append({
                    "rule": rule, "q": q, "gap": g, "detector": det, "n_resets": len(eff), "metric": metric,
                    "real": real[metric], "calendar": pl_c[metric],
                    "random_mean": np.nanmean(vr), "random_q95": np.nanquantile(vr, 0.95),
                    "random_p_ge": float((1 + np.sum(vr >= real[metric])) / (1 + np.isfinite(vr).sum())),
                    "shift_mean": np.nanmean(vs), "shift_q95": np.nanquantile(vs, 0.95),
                    "shift_p_ge": float((1 + np.sum(vs >= real[metric])) / (1 + np.isfinite(vs).sum())),
                })
    return pd.DataFrame(rows)


# ── E4 변화점 요약 ─────────────────────────────────────────────────


def change_point_summary(ob: O.Observed) -> tuple[pd.DataFrame, pd.DataFrame]:
    ed = ob.m.eval_dates
    n = len(ed)
    evm = O.event_mask(ob.events, n)
    near = np.zeros(n, bool)  # 사건 구간 ±5 거래일
    for a, b in zip(ob.events["i0"], ob.events["i1"]):
        near[max(0, int(a) - 5) : min(n, int(b) + 6)] = True
    yrs = sorted(set(ed.year))
    rows, sets = [], {}
    for (rule, q, g), eff in sorted(ob.cp_effect.items()):
        eff = np.asarray(eff, int)
        yc = {y: int(np.sum(ed.year.to_numpy()[eff] == y)) for y in yrs} if eff.size else {y: 0 for y in yrs}
        tot = max(1, eff.size)
        shares = np.array(list(yc.values())) / tot
        sub = ob.trig[(ob.trig["rule"] == rule) & (ob.trig["q"] == q) & (ob.trig["gap"] == g) & ob.trig["in_eval"]]
        lead = []
        for a in ob.events["i0"]:
            before = eff[(eff <= a) & (eff >= a - 20)]
            if before.size:
                lead.append(int(a - before.max()))
        rows.append({
            "rule": rule, "family": rule[0], "q": q, "gap": g, "n_triggers": int(eff.size),
            **{f"n_{y}": yc[y] for y in yrs},
            "max_year_share": float(shares.max()) if eff.size else np.nan,
            "herfindahl_year": float(np.sum(shares**2)) if eff.size else np.nan,
            "share_in_event": float(np.mean(evm[eff])) if eff.size else np.nan,
            "share_near_event_pm5": float(np.mean(near[eff])) if eff.size else np.nan,
            "event_base_rate": float(evm.mean()),
            "events_with_trigger_20d_before": len(lead),
            "median_lead_days": float(np.median(lead)) if lead else np.nan,
            "direction_up_share": float(np.mean(sub["direction"] > 0)) if len(sub) else np.nan,
        })
        sets[(rule, q, g)] = set(eff.tolist())
    # 중복성: 같은 q·gap 의 규칙 쌍 Jaccard (±2일 허용)
    jac = []
    keys = sorted(sets)
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if a[1:] != b[1:]:
                continue
            A_, B_ = sets[a], sets[b]
            if not A_ or not B_:
                continue
            hit = sum(1 for x in A_ if any(abs(x - y) <= 2 for y in B_))
            hit2 = sum(1 for y in B_ if any(abs(x - y) <= 2 for x in A_))
            jac.append({"rule_a": a[0], "rule_b": b[0], "q": a[1], "gap": a[2], "n_a": len(A_), "n_b": len(B_),
                        "match_a_in_b_pm2": hit / len(A_), "match_b_in_a_pm2": hit2 / len(B_)})
    return pd.DataFrame(rows), pd.DataFrame(jac)


# ── SVR 요약 ───────────────────────────────────────────────────────


def svr_summary(ob: O.Observed) -> tuple[pd.DataFrame, pd.DataFrame]:
    r = ob.m.r[ob.m.eval_start :]
    yr = ob.m.eval_dates.year.to_numpy()
    fits, rows = [], []
    for pl, p in ob.paths.items():
        for f in p.fits:
            fits.append({"pipeline": pl, **f})
        ok = np.isfinite(p.vhat) & (p.vhat > 0)
        # 재적합 경계 단절: 재적합일의 |Δlog v̂| vs 평상시
        dl = np.abs(np.diff(np.log(np.where(ok, p.vhat, np.nan))))
        at_refit = np.zeros(dl.size, bool)
        for s in p.refit_pos[1:]:
            at_refit[s - 1] = True
        for y in ["all", *sorted(set(yr))]:
            msk = ok if y == "all" else ok & (yr == y)
            v, rr = p.vhat[msk], r[msk]
            qlike = float(np.mean(np.log(v) + rr**2 / v)) if msk.any() else np.nan  # QLIKE = log v̂ + r²/v̂
            rows.append({
                "pipeline": pl, "year": y, "n_eligible": int(msk.sum()), "n_refits": len(p.refit_pos),
                "mean_e2": float(np.mean(rr**2 / v)) if msk.any() else np.nan,
                "qlike": qlike,
                "mse_var": float(np.mean((rr**2 - v) ** 2)) if msk.any() else np.nan,
                "nonpos_var_days": int(np.sum(np.isfinite(p.vhat) & (p.vhat <= 0) & ((yr == y) if y != "all" else True))),
                "refit_jump_median": float(np.nanmedian(dl[at_refit])) if (y == "all" and at_refit.any()) else np.nan,
                "ordinary_jump_median": float(np.nanmedian(dl[~at_refit])) if y == "all" else np.nan,
                "refit_jump_ratio": float(np.nanmedian(dl[at_refit]) / np.nanmedian(dl[~at_refit])) if (y == "all" and at_refit.any()) else np.nan,
            })
    return pd.DataFrame(rows), pd.DataFrame(fits)


# ── AE 피처 분석 ───────────────────────────────────────────────────


def ae_features(ob: O.Observed) -> pd.DataFrame:
    """후보 연속 피처 (모두 t 종가까지). 미래 실현변동성은 평가 전용 열(POSTHOC_ONLY)로 따로."""
    es = ob.m.eval_start
    r_all = pd.Series(ob.m.r, index=ob.m.dates)
    f = pd.DataFrame(index=ob.m.eval_dates)
    r = r_all.iloc[es:]
    f["ret"] = r.to_numpy()
    f["abs_ret"] = np.abs(f["ret"])
    for L in (5, 20, 60):
        f[f"rv{L}"] = r_all.rolling(L).std(ddof=1).iloc[es:].to_numpy()
    f["rv_ratio_5_60"] = np.log(f["rv5"] / f["rv60"])
    b1 = ob.paths["B1"]
    f["vhat_B1"] = b1.vhat
    f["e_B1"] = b1.e
    f["e2_B1"] = b1.e**2
    f["dlog_vhat20_B1"] = np.log(b1.vhat) - np.log(pd.Series(b1.vhat).shift(20).to_numpy())  # X4 예측분산 변화
    for w in (20, 30, 60, 120, 252):
        eid = "B1" if w == 60 else f"E2_w{w}"
        f[f"cos_w{w}_B1"] = ob.raw[eid]["T"]
    f["cos_w60_B0"] = ob.raw["B0"]["T"]
    f["cos_raw_w60"] = ob.raw["E3_raw_rolling_cos"]["T"]
    f["page_up_B1"] = ob.raw["E3_page_up"]["T"]
    f["page_dn_B1"] = ob.raw["E3_page_down"]["T"]
    f["cos_w60_refit21"] = ob.raw["E7_refit21"]["T"]
    f["page_up_refit21"] = ob.raw["E7_refit21_page_two"]["S_up"]
    sc = ob.scores.iloc[es:].reset_index(drop=True)
    for c in ("P20_score", "V20_two_score", "V60_two_score", "M20_60_score", "K60_score", "V5_two_score"):
        f[c] = sc[c].to_numpy()
    fut = r_all.rolling(20).std(ddof=1).shift(-20).iloc[es:].to_numpy()
    f["POSTHOC_future_rv20"] = fut
    return f


def ae_redundancy(f: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Spearman 상관 · 다른 피처로 설명되는 R² · 미래 RV20 증분 R² (현재 RV20 통제, 서술용)."""
    X = f.drop(columns=["POSTHOC_future_rv20"])
    corr = X.corr(method="spearman")
    rows = []
    y = np.log(f["POSTHOC_future_rv20"])
    base_x = np.log(f["rv20"])
    for c in X.columns:
        others = X.drop(columns=[c])
        d = pd.concat([X[c], others], axis=1).dropna()
        r2 = np.nan
        if len(d) > 50:
            Z = (d - d.mean()) / d.std(ddof=0)
            Z = Z.loc[:, Z.std() > 0]
            if c in Z:
                yy = Z[c].to_numpy()
                Xo = np.column_stack([np.ones(len(Z)), Z.drop(columns=[c]).to_numpy()])
                beta, *_ = np.linalg.lstsq(Xo, yy, rcond=None)
                r2 = 1 - np.sum((yy - Xo @ beta) ** 2) / np.sum((yy - yy.mean()) ** 2)
        dd = pd.concat([y, base_x, X[c]], axis=1, keys=["y", "b", "x"]).replace([np.inf, -np.inf], np.nan).dropna()
        inc = np.nan
        if len(dd) > 50 and c != "rv20":
            X0 = np.column_stack([np.ones(len(dd)), dd["b"]])
            X1 = np.column_stack([X0, (dd["x"] - dd["x"].mean()) / (dd["x"].std() or 1)])
            def r2f(M):
                bb, *_ = np.linalg.lstsq(M, dd["y"].to_numpy(), rcond=None)
                res = dd["y"].to_numpy() - M @ bb
                return 1 - np.sum(res**2) / np.sum((dd["y"] - dd["y"].mean()) ** 2)
            inc = r2f(X1) - r2f(X0)
        top = corr[c].drop(c).abs().sort_values(ascending=False)
        rows.append({"feature": c, "coverage": float(X[c].notna().mean()), "r2_from_others": r2,
                     "max_abs_spearman": float(top.iloc[0]), "most_similar": top.index[0],
                     "incremental_r2_future_rv20_over_rv20": inc, "n_used_future": int(len(dd))})
    return pd.DataFrame(rows), corr.reset_index().rename(columns={"index": "feature"})


# ── 사건 유형별 반응 (X-D8) ─────────────────────────────────────────

EVENT_EXPS = ("B1", "E2_w20", "E2_w120", "E2_w252", "E3_raw_rolling_cos", "E3_page_up", "E3_page_down",
              "X1_page_up_sn", "X1_page_down_sn", "E7_refit21", "E8_refit_only")


def event_response(ob: O.Observed, ledger: pd.DataFrame) -> pd.DataFrame:
    """11번 사건 구간마다 탐지기의 자기 분포 백분위 평균 · 최대 T/임계 · α=0.20 경보일 (서술용)."""
    rows = []
    for e in EVENT_EXPS:
        d = ledger[ledger["experiment_id"] == e].set_index("date")
        pc = d["cusum_raw_T"].rank(pct=True)
        for r in ob.events.itertuples():
            seg = slice(r.start, r.end)
            rows.append({"experiment": e, "interval": r.interval_id, "type": r.shock_type, "year": r.start.year,
                         "days": int(len(pc[seg])), "mean_pctile": float(pc[seg].mean()),
                         "max_T_over_crit": float(d["cusum_T_over_critical_a05"][seg].max()),
                         "alarm_a20_days": int(d["cusum_alarm_a20"][seg].sum())})
    return pd.DataFrame(rows)


# ── 실행 ───────────────────────────────────────────────────────────


def run(root: Path, calib_dir: Path, null_dir: Path, results: Path, store: Path | None = None) -> dict:
    cfg = C.load_cfg(root / "configs" / "t21_k200_cusum_controlled_v1.json")
    ob = O.compute(root)
    with open(calib_dir / "null_calibration.pkl", "rb") as fh:
        cal = pickle.load(fh)
    hold = load_hold(null_dir, ob.paths.keys())
    validity = A.null_validity(ob, hold)
    invalid = set(validity.loc[validity["outside"], "pipeline"])
    raw_sum = O.raw_summary(ob)
    src = ob.m.raw_sha256[:16]
    ledger = A.build_ledger(ob, cal, invalid, src)
    summ = A.experiment_summary(ob, ledger, raw_sum)
    size = pd.read_csv(calib_dir / "size_holdout.csv")
    size_rows, size_agg = AU.size_decomposition(size, invalid)
    led_audit = AU.ledger_audit(ledger, len(ob.m.eval_dates), len(ob.raw))
    cp_sum, cp_jac = change_point_summary(ob)
    svr_s, svr_fits = svr_summary(ob)
    feats = ae_features(ob)
    red, corr = ae_redundancy(feats)
    plc = placebo_table(ob, cal, cfg["seed"])
    store = store or root / "outputs" / "t21" / "feature_store_n1"
    store.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(store / "daily_cusum_features.parquet", index=False, partition_cols=None)
    feats.reset_index(names="date").to_parquet(store / "ae_candidate_wide.parquet", index=False)
    written = {}
    tables = {
        "experiment_summary.csv": summ,
        "null_validity.csv": validity,
        "size_holdout.csv": size_rows,
        "size_fail_decomposition.csv": size_agg,
        "feature_store_audit.csv": led_audit,
        "change_point_summary.csv": cp_sum,
        "change_point_overlap.csv": cp_jac,
        "svr_training_summary.csv": svr_s,
        "svr_fits.csv": svr_fits,
        "placebo_comparison.csv": plc,
        "ae_redundancy.csv": red,
        "ae_spearman.csv": corr,
        "events_11.csv": ob.events,
        "event_response_by_shock_type.csv": event_response(ob, ledger),
    }
    syn = calib_dir / "synthetic_detection.csv"
    if syn.exists():
        tables["synthetic_size_power.csv"] = pd.read_csv(syn)
    for name, df in tables.items():
        write_csv(df, results / name)
        written[name] = sha256(results / name)
    return {"written": written, "ledger_rows": len(ledger), "ob": ob, "cal": cal, "ledger": ledger, "tables": tables,
            "feats": feats}
