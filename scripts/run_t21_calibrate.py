"""12번 귀무 보정 · 홀드아웃 크기 · 시나리오 검출 — MC 결과(outputs/t21/mc/main_*)를 읽어 outputs/t21/calib/ 에 쓴다.

사용 (GPU): /home/sieg/projects-wsl/hongik_univ_26_2/.venv/bin/python scripts/run_t21_calibrate.py [--cpu] [--stage obs|syn|all]
임계값·귀무표는 백엔드 이름과 함께 저장한다. 관측 경보 판정은 R2H .venv 의 관측 단계에서 이 표를 읽어 한다.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import calib as K  # noqa: E402
from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import mc as MC  # noqa: E402
from r2h.k200_controlled import nullcal as N  # noqa: E402
from r2h.k200_controlled import registry as RG  # noqa: E402
from r2h.k200_controlled import synth as S  # noqa: E402
from r2h.k200_controlled.policies import PIPELINES_SCENARIO  # noqa: E402

LAM = {"page_up": 2.0, "page_down": 0.5}


def base_det(det: str, E: np.ndarray) -> tuple[str, np.ndarray]:
    """``*_sn`` 탐지기는 자기정규화 잔차 위의 같은 탐지기 (X1)."""
    return (det[:-3], C.selfnorm(E)) if det.endswith("_sn") else (det, E)
SYN_RESETS = ("none", "annual", RG.PRIMARY_RESET, "placebo_random")


def null_stat(engine, st: N.MCSet, m, det, svr, w, reset, seed, salt, raw_r=None):
    """귀무 경로 묶음의 원시 통계량 (rolling → T, page → S_free) 과 마스크·잔차."""
    mask = st.reset_mask(m, reset, seed, salt)
    if det == "raw_rolling_cos":
        return engine.rolling(raw_r, int(w), mask), mask, raw_r
    det, E = base_det(det, st.E[svr])
    if det == "rolling_cos":
        return engine.rolling(E, int(w), mask), mask, E
    if det in LAM:
        return N.page_free_batch(E, LAM[det], mask), mask, E
    Su, Sd = N.page_free_batch(E, 2.0, mask), N.page_free_batch(E, 0.5, mask)
    return np.fmax(Su, Sd), mask, E


def calibrate(engine, cal: N.MCSet, m, bid, det, svr, w, reset, seed, raw_cal=None) -> dict:
    T, mask, E = null_stat(engine, cal, m, det, svr, w, reset, seed, "cal", raw_cal)
    det = det[:-3] if det.endswith("_sn") else det
    out = {"table": N.null_table(T, bid)}
    if det in ("rolling_cos", "raw_rolling_cos"):
        out["crit"] = {a: C.crit_block_alpha(T, [bid == j for j in range(len(N.YEARS))], a) for a in N.ALPHAS}
    elif det in LAM:
        hits = engine.page_block_hits(E, LAM[det], N.H_GRID, mask, bid)
        rates = hits.mean(axis=(0, 2))
        out["crit"] = {a: N.h_from_rates(rates, N.H_GRID, a) for a in N.ALPHAS}
    else:
        hu = engine.page_block_hits(E, 2.0, N.H_GRID, mask, bid)
        hd = engine.page_block_hits(E, 0.5, N.H_GRID, mask, bid)
        out["crit"] = {}
        for a in N.ALPHAS:
            a_u, a_d, u = N.two_sided_h(hu, hd, N.H_GRID, a)
            out["crit"][a] = (a_u, a_d)
            out[f"union_cal_{a}"] = u
    return out


def alarms(engine, st: N.MCSet, m, det, svr, w, reset, crit, seed, salt, raw=None) -> np.ndarray:
    """(경로, 일) 경보 bool — rolling 은 T ≥ crit, page 는 경보 후 재설정 경로."""
    mask = st.reset_mask(m, reset, seed, salt)
    if det in ("rolling_cos", "raw_rolling_cos"):
        E = raw if det == "raw_rolling_cos" else st.E[svr]
        T = engine.rolling(E, int(w), mask)
        return np.nan_to_num(T, nan=-np.inf) >= crit
    det, E = base_det(det, st.E[svr])
    if det in LAM:
        return engine.page_alarm(E, LAM[det], crit, mask)
    hu, hd = crit
    return engine.page_alarm(E, 2.0, hu, mask) | engine.page_alarm(E, 0.5, hd, mask)


def regen_raw(st: N.MCSet, set_name: str, sc: str, cfg, g, m) -> np.ndarray:
    common = (cfg["seed"], g, m.dates, m.eval_start, "2021-03-02", "2025-09-30", [2020, 2021, 2022, 2023, 2024])
    return np.stack([MC.regen_returns((set_name, int(rp), sc, *common)) for rp in st.meta["rep"]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--stage", default="all")
    ap.add_argument("--cal-id", default="garch_t_N1")
    ap.add_argument("--dgp-fit-end", default=None, help="N0 재현용: 2020-01-01 (lock-1 2019 단독 적합)")
    ap.add_argument("--null-tag", default="n1_null")
    ap.add_argument("--scen-tag", default="n1_scen")
    a = ap.parse_args()
    cfg = C.load_cfg(ROOT / "configs" / "t21_k200_cusum_controlled_v1.json")
    m = C.load_market(cfg, ROOT)
    if a.dgp_fit_end:
        cfg["calibration_E11"]["null_dgp_fit_end"] = a.dgp_fit_end
    g = S.dgp_for(m, cfg)
    seed = cfg["seed"]
    bid = N.block_ids(m)
    blocks = [bid == j for j in range(len(N.YEARS))]
    engine = N.Engine(prefer_gpu=not a.cpu)
    out = ROOT / "outputs" / "t21" / ("calib_n1" if a.null_tag == "n1_null" else f"calib_{a.null_tag}")
    out.mkdir(parents=True, exist_ok=True)
    nd = ROOT / "outputs" / "t21" / "mc" / a.null_tag
    t0 = time.monotonic()
    cal, hold = N.load_set(nd, "null_cal", "S00_null"), N.load_set(nd, "null_hold", "S00_null")
    if hold.R == 0:  # 파일럿 전용: 홀드아웃이 없으면 보정 집합으로 대신 (기록에 남김)
        hold = cal
        log_pilot = True
    else:
        log_pilot = False
    raw_cal, raw_hold = regen_raw(cal, "null_cal", "S00_null", cfg, g, m), regen_raw(hold, "null_hold", "S00_null", cfg, g, m)
    log = {"backend": engine.name, "R_cal": cal.R, "R_hold": hold.R, "pilot_hold_is_cal": log_pilot}

    reg = RG.build()
    keys = reg[reg["detector"] != "posthoc_full"][["svr", "detector", "w", "reset"]].drop_duplicates()
    syn_keys = pd.DataFrame(
        [
            {"svr": p, "detector": d, "w": w, "reset": r}
            for p in PIPELINES_SCENARIO
            for d, ws in (("rolling_cos", (20, 30, 60, 120, 252)), ("page_up", ("NA",)), ("page_down", ("NA",)), ("page_two", ("NA",)))
            for w in ws
            for r in (SYN_RESETS if (d != "rolling_cos" or w == 60) else ("none",))
        ]
        + [{"svr": "refitV20_g0", "detector": "rolling_cos", "w": 20, "reset": RG.PRIMARY_RESET}]
        + [{"svr": "NA", "detector": "raw_rolling_cos", "w": w, "reset": "none"} for w in (20, 60, 120)]
        + [{"svr": p, "detector": d, "w": "NA", "reset": "none"} for p in ("B1", "refit21") for d in ("page_up_sn", "page_down_sn", "page_two_sn")]
    )
    keys = pd.concat([keys, syn_keys]).drop_duplicates().reset_index(drop=True)
    res: dict[tuple, dict] = {}
    size_rows = []
    pkl = out / "null_calibration.pkl"
    if a.stage == "syn" and pkl.exists():  # 관측용 보정이 끝났으면 다시 하지 않고 시나리오 검출만
        with open(pkl, "rb") as fh:
            saved = pickle.load(fh)
        res, alt = saved["res"], saved["alt"]
        keys = keys.iloc[0:0]
    for i, k in enumerate(keys.itertuples(index=False)):
        key = (k.svr, k.detector, str(k.w), k.reset)
        c = calibrate(engine, cal, m, bid, k.detector, k.svr, k.w, k.reset, seed, raw_cal)
        for al in N.ALPHAS:
            A = alarms(engine, hold, m, k.detector, k.svr, k.w, k.reset, c["crit"][al], seed, "hold", raw_hold)
            r = C.block_alarm_rate(A, blocks)
            n = A.shape[0] * len(blocks)
            lo, hi = K.wilson(int(round(r * n)), n)
            clo, chi = K.cluster_bootstrap_ci(A, blocks, seed=seed)
            size_rows.append({"svr": k.svr, "detector": k.detector, "w": k.w, "reset": k.reset, "alpha": al,
                              "crit": json.dumps(c["crit"][al]), "holdout_rate": r, "ci_lo": lo, "ci_hi": hi,
                              "size_ok": bool(lo <= al <= hi), "cluster_ci_lo": clo, "cluster_ci_hi": chi,
                              "size_ok_cluster": bool(clo <= al <= chi), "block_icc": K.block_hit_icc(A, blocks),
                              "alarm_day_rate": float(A[:, bid >= 0].mean())})
        res[key] = c
        if i % 25 == 0:
            print(i, "/", len(keys), key, round(time.monotonic() - t0, 1), "s", flush=True)

    if a.stage == "syn" and pkl.exists():
        log["reused_calibration"] = True
    else:
        res, alt, size_rows = calibrate_alt(engine, cal, hold, m, seed, blocks, bid, res, size_rows, a, out, log, t0)
    if a.stage == "obs":
        (out / "calib_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
        return
    _syn(engine, m, seed, blocks, cfg, g, res, alt, syn_keys, a, out, log, t0)


def calibrate_alt(engine, cal, hold, m, seed, blocks, bid, res, size_rows, a, out, log, t0):
    """E11 대체 보정 + 홀드아웃 크기표 저장 + 보정 pkl 저장."""
    # E11 대체 보정 (B1 w60 rolling): 점근 · 정규 MC · 사전 iid · 사전 블록
    pool = np.load(ROOT / "outputs" / "t21" / "presample_pool.npy")
    n = m.n - m.eval_start
    rng = np.random.default_rng([seed, 11])
    alt_draws = {
        "normal_mc": rng.standard_normal((cal.R, n)),
        "iid_bootstrap_presample": rng.choice(pool, size=(cal.R, n), replace=True),
        "block_bootstrap_presample": np.concatenate(
            [pool[(rng.integers(0, pool.size, size=(cal.R, 1)) + np.arange(10)[None, :]) % pool.size] for _ in range(int(np.ceil(n / 10)))],
            axis=1,
        )[:, :n],
    }
    alt = {"asymptotic": {al: 1.3397 for al in N.ALPHAS}}
    for name, X in alt_draws.items():
        T = engine.rolling(X, 60, None)
        alt[name] = {al: C.crit_block_alpha(T, blocks, al) for al in N.ALPHAS}
    Th = engine.rolling(hold.E["B1"], 60, None)
    for name, crits in alt.items():
        for al, cr in crits.items():
            A = np.nan_to_num(Th, nan=-np.inf) >= cr
            r = C.block_alarm_rate(A, blocks)
            nn = A.shape[0] * len(blocks)
            lo, hi = K.wilson(int(round(r * nn)), nn)
            clo, chi = K.cluster_bootstrap_ci(A, blocks, seed=seed)
            size_rows.append({"svr": "B1", "detector": "rolling_cos", "w": 60, "reset": "none", "alpha": al,
                              "calibration": name, "crit": json.dumps(cr), "holdout_rate": r, "ci_lo": lo, "ci_hi": hi,
                              "size_ok": bool(lo <= al <= hi), "cluster_ci_lo": clo, "cluster_ci_hi": chi,
                              "size_ok_cluster": bool(clo <= al <= chi), "block_icc": K.block_hit_icc(A, blocks),
                              "alarm_day_rate": float(A[:, bid >= 0].mean())})
    size = pd.DataFrame(size_rows)
    size["calibration"] = size["calibration"].fillna(a.cal_id) if "calibration" in size else a.cal_id
    size.to_csv(out / "size_holdout.csv", index=False)
    with open(out / "null_calibration.pkl", "wb") as fh:
        pickle.dump({"res": res, "alt": alt, "backend": engine.name, "H_GRID": N.H_GRID, "QTAB": N.QTAB}, fh)
    log["calib_seconds"] = round(time.monotonic() - t0, 1)
    print("보정 끝", log, flush=True)
    return res, alt, size_rows


def _syn(engine, m, seed, blocks, cfg, g, res, alt, syn_keys, a, out, log, t0):
    """시나리오 검출 (같은 α 임계값으로)."""
    # ── 시나리오 검출 ──
    sd = ROOT / "outputs" / "t21" / "mc" / a.scen_tag
    det_rows, delays = [], {}
    alt_keys = [("B1", "rolling_cos", "60", "none", name) for name in alt]
    for sc in S.SCENARIOS:
        st = N.load_set(sd, "scen", sc)
        taus = K.parse_taus(st.meta)
        raw_sc = regen_raw(st, "scen", sc, cfg, g, m)
        for k in syn_keys.itertuples(index=False):
            key = (k.svr, k.detector, str(k.w), k.reset)
            for al in N.ALPHAS:
                A = alarms(engine, st, m, k.detector, k.svr, k.w, k.reset, res[key]["crit"][al], seed, "scen", raw_sc)
                rec = {"scenario": sc, "svr": k.svr, "detector": k.detector, "w": k.w, "reset": k.reset, "alpha": al,
                       "calibration": "garch_t_N1", "block_alarm_rate": C.block_alarm_rate(A, blocks)}
                if sc != "S00_null":
                    rec.update(K.detection_table(A, taus, cfg["synthetic"]["detection_horizon_days"]))
                    rec.update(K.all_change_detection(A, taus, cfg["synthetic"]["detection_horizon_days"]))
                    delays[(sc, *key, al)] = np.array(
                        [(-1 if (d := K.first_alarm_after(A[i], ts[0], cfg["synthetic"]["detection_horizon_days"])) is None else d)
                         for i, ts in enumerate(taus)], dtype=np.int32)
                det_rows.append(rec)
        T = engine.rolling(st.E["B1"], 60, None)
        for _, _, _, _, name in alt_keys:
            for al in N.ALPHAS:
                A = np.nan_to_num(T, nan=-np.inf) >= alt[name][al]
                rec = {"scenario": sc, "svr": "B1", "detector": "rolling_cos", "w": 60, "reset": "none", "alpha": al,
                       "calibration": name, "block_alarm_rate": C.block_alarm_rate(A, blocks)}
                if sc != "S00_null":
                    rec.update(K.detection_table(A, taus, cfg["synthetic"]["detection_horizon_days"]))
                det_rows.append(rec)
        print("시나리오", sc, round(time.monotonic() - t0, 1), "s", flush=True)
    pd.DataFrame(det_rows).to_csv(out / "synthetic_detection.csv", index=False)
    with open(out / "synthetic_delays.pkl", "wb") as fh:
        pickle.dump(delays, fh)
    log["total_seconds"] = round(time.monotonic() - t0, 1)
    (out / "calib_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("끝", log)


if __name__ == "__main__":
    main()
