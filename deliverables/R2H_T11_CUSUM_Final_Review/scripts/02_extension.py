"""T11 최종 재평가 — EXTENSION 실험 E1–E5 (T11 원본 결과표와 분리, ``extension/`` 에만 쓴다).

E1 잔차 수준 size        — CUSUM-of-squares 통계량 자체의 유한표본 크기 (iid N · iid t5 · GARCH 미표준화)
E2 파이프라인 size·power — 합성 GARCH(1,1) 에 ``fit_etf`` 를 그대로 적용 (귀무 / 검정 구간 중간 ω×3)
E3 stationary bootstrap  — 임계값의 귀무를 '독립' 에서 '정상 의존' 으로 바꾼 재판정 (다른 귀무가설)
E4 시점 무결성           — 검정 구간 t₀ 이후 수익률만 교란 → t₀ 이전 분산·잔차·이동창 통계량 불변 여부
E5 정책 B 이동창         — 검정 구간 w=60 에서 정책 A 대신 B 잔차

실행 (R2H 루트): ``PYTHONPATH=src python deliverables/R2H_T11_CUSUM_Final_Review/scripts/02_extension.py [E1 E2 …]``
seed 20261012. 모든 난수는 ``np.random.default_rng([SEED, 실험번호, …])`` 로 파생한다.
"""

from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.paper2020 import ArgmaxTiePolicy, DegenerateTauPolicy, cusum_squares_test
from r2h.svrgarch_etf.model import baseline_residuals, fit_etf, fullsample_test
from r2h.svrgarch_etf.rolling import (
    ASYMPTOTIC_5PCT,
    SEED,
    WINDOWS,
    bootstrap_critical_value,
    episodes,
    iid_stats,
    rolling_cusum,
)

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
RES = REPO / "research" / "svr_garch_cusum_etf" / "results"
OUT = HERE / "extension"
OUT.mkdir(parents=True, exist_ok=True)
STATE = Path(os.environ.get("T11_STATE", REPO / "outputs" / "cache" / "t11_state.npz"))
KOLMOGOROV_95 = 1.3581  # 01_recompute.kolmogorov_quantile(0.95)

# E2 DGP — GARCH(1,1), N(0,1) 혁신, 일간 100·Δlog 수익률 규모 (무조건 분산 ω/(1−α−β) = 2.5)
OMEGA, ALPHA, BETA = 0.05, 0.08, 0.90
N_SERIES, BURN = 1902, 500
N_FIT = round(0.70 * N_SERIES)
BREAK_AT = N_FIT + 285  # 검정 구간 571 일 중 286 번째 날부터 ω×3
OMEGA_MULT = 3.0
REPS_E2 = int(os.environ.get("E2_REPS", "500"))


def cusum_T(e: np.ndarray) -> float:
    e = e[np.isfinite(e)]
    return cusum_squares_test(
        e, tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
    ).statistic


def garch_path(rng: np.random.Generator, n: int, omega_mult_from: int | None = None) -> np.ndarray:
    """GARCH(1,1) 경로. omega_mult_from 이 주어지면 그 위치부터 ω×OMEGA_MULT (분산 구조변화)."""
    total = n + BURN
    z = rng.standard_normal(total)
    y = np.empty(total)
    s2 = OMEGA / (1 - ALPHA - BETA)
    for t in range(total):
        om = OMEGA * (OMEGA_MULT if (omega_mult_from is not None and t - BURN >= omega_mult_from) else 1.0)
        if t > 0:
            s2 = om + ALPHA * y[t - 1] ** 2 + BETA * s2
        y[t] = np.sqrt(s2) * z[t]
    return y[BURN:]


def garch_matrix(rng: np.random.Generator, reps: int, n: int) -> np.ndarray:
    """garch_path 를 반복 축으로 벡터화 (E1 용, 구조변화 없음)."""
    z = rng.standard_normal((reps, n + BURN))
    y = np.empty_like(z)
    s2 = np.full(reps, OMEGA / (1 - ALPHA - BETA))
    for t in range(n + BURN):
        if t > 0:
            s2 = OMEGA + ALPHA * y[:, t - 1] ** 2 + BETA * s2
        y[:, t] = np.sqrt(s2) * z[:, t]
    return y[:, BURN:]


# ───────────────────────────── E1
def e1() -> dict:
    rows = []
    for n in (60, 571):
        rng0 = np.random.default_rng([SEED, 1, n, 0])
        c_norm = float(np.quantile(iid_stats(rng0.standard_normal((20_000, n))), 0.95))
        for dgp in ("iid_normal", "iid_t5", "garch_unstandardized"):
            rng = np.random.default_rng([SEED, 1, n, ("iid_normal", "iid_t5", "garch_unstandardized").index(dgp) + 1])
            R = 10_000
            if dgp == "iid_normal":
                X = rng.standard_normal((R, n))
            elif dgp == "iid_t5":
                X = rng.standard_t(5, size=(R, n)) / np.sqrt(5 / 3)
            else:
                X = garch_matrix(rng, R, n)
            T = iid_stats(X)
            for cname, c in (("paper_1.3397", ASYMPTOTIC_5PCT), ("kolmogorov_1.3581", KOLMOGOROV_95), ("normal_mc95", c_norm)):
                p = float(np.mean(T >= c))
                rows.append({"n": n, "dgp": dgp, "critical": cname, "c": c, "R": R, "reject_rate": p,
                             "mc_se": float(np.sqrt(p * (1 - p) / R))})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "E1_residual_size.csv", index=False)
    return {"rows": len(df)}


# ───────────────────────────── E2
def _e2_one(args: tuple[str, int]) -> dict:
    scenario, rep = args
    rng = np.random.default_rng([SEED, 2, rep, 0 if scenario == "null" else 1])
    y = garch_path(rng, N_SERIES, BREAK_AT if scenario == "break" else None)
    dates = pd.bdate_range("2019-01-03", periods=N_SERIES)
    s = pd.Series(y, index=dates)
    f = fit_etf(f"SIM{rep}", s)
    out = {"scenario": scenario, "rep": rep, "C": f.params.C, "g2": f.params.paper_gamma_squared, "eps": f.params.epsilon}
    for pol in ("A", "B"):
        r = fullsample_test(f, pol)
        out[f"T_{pol}"] = float(r["T"])
    base = baseline_residuals(s).to_numpy()
    out["T_base"] = cusum_T(base[N_FIT:])
    # 이동창 w=60 — 파이프라인과 같은 방식: 적합 구간 잔차 iid 부트스트랩 95% 임계값
    w = 60
    t0 = N_FIT + w - 1  # 창 전체가 검정 구간 안
    for key, e in (("A", f.residuals("A")), ("B", f.residuals("B")), ("base", base)):
        pool = (f.residuals("A") if key == "B" else e)[:N_FIT]
        c = bootstrap_critical_value(pool, w, reps=2_000, salt=rep * 10 + ("A", "B", "base").index(key))
        stat = rolling_cusum(e, w)
        alarm = np.nan_to_num(stat, nan=-np.inf) >= c
        alarm[:t0] = False  # 순수 검정 구간만
        eps = episodes(alarm, gap=5)
        starts = np.array([a for a, _ in eps], dtype=int)
        out[f"c60_{key}"] = c
        if scenario == "null":
            out[f"ep_test_{key}"] = len(eps)
            out[f"rate_test_{key}"] = len(eps) / ((N_SERIES - t0) / 252)
        else:
            pre = starts[starts < BREAK_AT]
            post = starts[starts >= BREAK_AT]
            out[f"rate_pre_{key}"] = len(pre) / ((BREAK_AT - t0) / 252)
            out[f"delay_{key}"] = int(post[0] - BREAK_AT) if post.size else np.nan
            # 변화 후 첫 경보일 (에피소드 시작이 아니라 경보일 기준; 변화 직전부터 이어진 에피소드도 포함)
            post_alarm = np.flatnonzero(alarm[BREAK_AT:])
            out[f"first_alarm_delay_{key}"] = int(post_alarm[0]) if post_alarm.size else np.nan
    return out


def e2() -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    jobs = [(sc, r) for sc in ("null", "break") for r in range(REPS_E2)]
    t = time.time()
    with Pool(int(os.environ.get("E2_PROCS", "20"))) as p:
        res = p.map(_e2_one, jobs, chunksize=4)
    df = pd.DataFrame(res)
    df.to_csv(OUT / "E2_pipeline_size_power_reps.csv", index=False)
    summ = []
    for sc, g in df.groupby("scenario"):
        R = len(g)
        for key in ("A", "B", "base"):
            for cname, c in (("paper_1.3397", ASYMPTOTIC_5PCT), ("kolmogorov_1.3581", KOLMOGOROV_95)):
                p = float((g[f"T_{key}"] >= c).mean())
                summ.append({"scenario": sc, "residual": key, "measure": f"posthoc_reject@{cname}", "value": p,
                             "mc_se": float(np.sqrt(p * (1 - p) / R)), "R": R})
            if sc == "null":
                v = g[f"rate_test_{key}"]
                summ.append({"scenario": sc, "residual": key, "measure": "w60_test_episodes_per_year", "value": float(v.mean()),
                             "mc_se": float(v.std(ddof=1) / np.sqrt(R)), "R": R})
                summ.append({"scenario": sc, "residual": key, "measure": "w60_test_any_alarm_share",
                             "value": float((g[f"ep_test_{key}"] > 0).mean()), "mc_se": np.nan, "R": R})
            else:
                v = g[f"rate_pre_{key}"]
                summ.append({"scenario": sc, "residual": key, "measure": "w60_prebreak_episodes_per_year", "value": float(v.mean()),
                             "mc_se": float(v.std(ddof=1) / np.sqrt(R)), "R": R})
                d = g[f"first_alarm_delay_{key}"]
                summ.append({"scenario": sc, "residual": key, "measure": "w60_detect_share_by_end", "value": float(d.notna().mean()),
                             "mc_se": float(np.sqrt(d.notna().mean() * (1 - d.notna().mean()) / R)), "R": R})
                summ.append({"scenario": sc, "residual": key, "measure": "w60_first_alarm_delay_median_days",
                             "value": float(d.median()) if d.notna().any() else np.nan, "mc_se": np.nan, "R": R})
                for lim in (20, 60):
                    q = float((d <= lim).mean())
                    summ.append({"scenario": sc, "residual": key, "measure": f"w60_detect_within_{lim}d", "value": q,
                                 "mc_se": float(np.sqrt(q * (1 - q) / R)), "R": R})
    s = pd.DataFrame(summ)
    s.to_csv(OUT / "E2_pipeline_size_power_summary.csv", index=False)
    return {"seconds": round(time.time() - t), "R_per_scenario": REPS_E2}


# ───────────────────────────── E3
def stationary_bootstrap(pool: np.ndarray, reps: int, n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis–Romano stationary bootstrap — 기하분포 블록(평균 mean_block), 원형 연결."""
    N = pool.size
    idx = np.empty((reps, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, N, reps)
    restart = rng.random((reps, n)) < 1.0 / mean_block
    fresh = rng.integers(0, N, (reps, n))
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % N)
    return pool[idx]


def e3() -> dict:
    z = np.load(STATE, allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    fit = pd.read_csv(RES / "fit_summary.csv", dtype={"ticker": str})
    crit = pd.read_csv(RES / "critical_values.csv", dtype={"ticker": str})
    fs = pd.read_csv(HERE / "analysis" / "fullsample_recomputed.csv", dtype={"ticker": str})
    rows = []
    n = len(idx)
    for t in [str(x) for x in z["tickers"]]:
        sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc[t, "split_date"])))
        e = z[f"res__{t}__svrA"]
        pool = e[:sp][np.isfinite(e[:sp])]
        rng = np.random.default_rng([SEED, 3, int(t)])
        c571 = float(np.quantile(iid_stats(stationary_bootstrap(pool, 5_000, 571, 20.0, rng)), 0.95))
        c60 = float(np.quantile(iid_stats(stationary_bootstrap(pool, 5_000, 60, 20.0, rng)), 0.95))
        TA = float(fs[(fs.ticker == t) & (fs.policy == "A")]["T"].iloc[0])
        c_iid571 = float(fs[(fs.ticker == t) & (fs.policy == "A")]["c_boot_n"].iloc[0])
        c_iid60 = float(crit[(crit.ticker == t) & (crit.rtype == "svrA") & (crit.window == 60)].c_bootstrap.iloc[0])
        stat = rolling_cusum(e, 60)
        t0 = sp + 59
        def rate(c: float) -> float:
            alarm = np.nan_to_num(stat, nan=-np.inf) >= c
            alarm[:t0] = False
            return len(episodes(alarm, gap=5)) / ((n - t0) / 252)
        rows.append({"ticker": t, "T_A": TA, "c571_iid": c_iid571, "c571_sb20": c571, "reject_iid": TA >= c_iid571,
                     "reject_sb20": TA >= c571, "c60_iid": c_iid60, "c60_sb20": c60,
                     "rate_test_w60_iid": rate(c_iid60), "rate_test_w60_sb20": rate(c60)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "E3_stationary_bootstrap.csv", index=False)
    return {"rows": len(df)}


# ───────────────────────────── E4
def e4() -> dict:
    z = np.load(STATE, allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    t = "069500"
    r = pd.Series(z[f"r__{t}"], index=idx)
    f0 = fit_etf(t, r)
    t0 = f0.n_fit + 300
    r1 = r.copy()
    r1.iloc[t0:] = r1.iloc[t0:] * 3.0
    f1 = fit_etf(t, r1)
    out: dict[str, object] = {"ticker": t, "t0_date": str(idx[t0].date()), "split_date": str(f0.split_date.date()),
                              "params_same": f0.params == f1.params}
    for pol in ("A", "B"):
        e0, e1_ = f0.residuals(pol), f1.residuals(pol)
        out[f"resid_{pol}_identical_before_t0"] = bool(np.array_equal(e0[:t0], e1_[:t0], equal_nan=True))
        out[f"resid_{pol}_changed_after_t0"] = bool(not np.allclose(e0[t0:], e1_[t0:], equal_nan=True))
        for w in WINDOWS:
            s0, s1 = rolling_cusum(e0, w), rolling_cusum(e1_, w)
            out[f"roll_{pol}_w{w}_identical_before_t0"] = bool(np.array_equal(s0[:t0], s1[:t0], equal_nan=True))
    b0, b1 = baseline_residuals(r).to_numpy(), baseline_residuals(r1).to_numpy()
    out["resid_base_identical_before_t0"] = bool(np.array_equal(b0[:t0], b1[:t0], equal_nan=True))
    for w in WINDOWS:
        out[f"roll_base_w{w}_identical_before_t0"] = bool(
            np.array_equal(rolling_cusum(b0, w)[:t0], rolling_cusum(b1, w)[:t0], equal_nan=True))
    # 대조: 적합 구간을 교란하면 ĝ 가 바뀌어 검정 구간 전체가 달라진다 (알려진 파라미터 look-ahead 의 방향 확인)
    r2 = r.copy()
    r2.iloc[100:200] = r2.iloc[100:200] * 3.0
    f2 = fit_etf(t, r2)
    out["control_fit_perturbed_params_changed"] = bool(f2.params != f0.params)
    out["control_fit_perturbed_test_resid_changed"] = bool(
        not np.allclose(f0.residuals("A")[f0.n_fit:], f2.residuals("A")[f0.n_fit:], equal_nan=True))
    (OUT / "E4_time_integrity.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return {"all_identical": all(v for k, v in out.items() if k.endswith("identical_before_t0"))}


# ───────────────────────────── E5
def e5() -> dict:
    z = np.load(STATE, allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    fit = pd.read_csv(RES / "fit_summary.csv", dtype={"ticker": str})
    crit = pd.read_csv(RES / "critical_values.csv", dtype={"ticker": str})
    n, w, rows = len(idx), 60, []
    for t in [str(x) for x in z["tickers"]]:
        sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc[t, "split_date"])))
        t0 = sp + w - 1
        c = float(crit[(crit.ticker == t) & (crit.rtype == "svrA") & (crit.window == w)].c_bootstrap.iloc[0])
        row = {"ticker": t, "c60_svrA_boot": c}
        for key in ("svrA", "svrB"):
            stat = rolling_cusum(z[f"res__{t}__{key}"], w)
            alarm = np.nan_to_num(stat, nan=-np.inf) >= c
            alarm[:t0] = False
            eps = episodes(alarm, gap=5)
            row[f"episodes_test_{key}"] = len(eps)
            row[f"rate_test_{key}"] = len(eps) / ((n - t0) / 252)
            row[f"alarm_days_test_{key}"] = int(alarm.sum())
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "E5_policyB_rolling_w60.csv", index=False)
    return {"rows": len(df)}


# ───────────────────────────── E6
def lrv_ratio(e: np.ndarray) -> tuple[float, float]:
    """ε² 의 Bartlett 장기분산 / τ̂² 와 lag 1–5 자기상관 합. 비 < 1 이면 τ̂ 정규화가 통계량을 눌러 검정이 보수적."""
    v = e[np.isfinite(e)] ** 2
    n = v.size
    d = v - v.mean()
    g0 = float(d @ d / n)
    h = int(np.floor(4 * (n / 100) ** (2 / 9)))
    lrv = g0 + 2 * sum((1 - k / (h + 1)) * float(d[k:] @ d[:-k] / n) for k in range(1, h + 1))
    acf5 = sum(float(d[k:] @ d[:-k] / n) / g0 for k in range(1, 6))
    return lrv / g0, acf5


def _e6_sim(rep: int) -> dict:
    rng = np.random.default_rng([SEED, 6, rep])
    y = garch_path(rng, N_SERIES)
    s = pd.Series(y, index=pd.bdate_range("2019-01-03", periods=N_SERIES))
    f = fit_etf(f"SIM{rep}", s)
    out = {"rep": rep}
    for key, e in (("A", f.residuals("A")), ("B", f.residuals("B")), ("base", baseline_residuals(s).to_numpy())):
        out[f"lrv_{key}_test"], out[f"acf5_{key}_test"] = lrv_ratio(e[N_FIT:])
    return out


def e6() -> dict:
    z = np.load(STATE, allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    fit = pd.read_csv(RES / "fit_summary.csv", dtype={"ticker": str})
    rows = []
    for t in [str(x) for x in z["tickers"]]:
        sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc[t, "split_date"])))
        for key in ("svrA", "svrB", "base"):
            e = z[f"res__{t}__{key}"]
            for zone, seg in (("fit", e[:sp]), ("test", e[sp:])):
                if key == "svrB" and zone == "fit":
                    continue  # 적합 구간의 정책 B 잔차 = 정책 A
                r, a = lrv_ratio(seg)
                rows.append({"ticker": t, "rtype": key, "zone": zone, "lrv_over_tau2": r, "acf_sq_sum_lag1_5": a})
    pd.DataFrame(rows).to_csv(OUT / "E6_residual_dependence_etf.csv", index=False)
    with Pool(int(os.environ.get("E2_PROCS", "20"))) as p:
        sims = pd.DataFrame(p.map(_e6_sim, range(100)))
    sims.to_csv(OUT / "E6_residual_dependence_sim.csv", index=False)
    return {"rows": len(rows), "sims": len(sims)}


if __name__ == "__main__":
    todo = sys.argv[1:] or ["E1", "E3", "E4", "E5", "E2"]
    log = {}
    for name in todo:
        t = time.time()
        log[name] = {**{"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6}[name](), "elapsed_s": round(time.time() - t, 1)}
        print(name, log[name], flush=True)
    prev = OUT / "extension_run_log.json"
    old = json.loads(prev.read_text()) if prev.exists() else {}
    old.update(log)
    prev.write_text(json.dumps(old, ensure_ascii=False, indent=1))
