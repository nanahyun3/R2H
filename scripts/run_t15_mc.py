# ruff: noqa: E402  — 작업자 스레드 수 환경변수를 numpy import 전에 정해야 한다
"""W3 (T15) 전체 재적합 Monte Carlo 실행기 (계약 §9, D1·D15).

사용 (R2H .venv):
  python scripts/run_t15_mc.py fit                      # DCC-t·CCC-t 적합 → outputs/t15/mc/models.pkl
  python scripts/run_t15_mc.py benchmark --reps 4       # G2: 경로당 CPU·wall·RSS, 병렬 1/4/8/16/22
  python scripts/run_t15_mc.py calibration --reps N --workers W
  python scripts/run_t15_mc.py tables                   # 꼬리표·단기 창 임계값·적합도 envelope
  python scripts/run_t15_mc.py eval --domain null_eval_dcc --reps N --workers W
  python scripts/run_t15_mc.py alt --reps N --workers W
결과는 Git 제외 ``outputs/t15/mc/`` 에 쓴다. 반복의 시드는 (study_id, seed, 영역, rep) 로 정해져 작업자 수와 무관하다.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"  # 작업자당 스레드 1 (설정 monte_carlo.threads_per_worker)

import argparse
import json
import multiprocessing as mp
import pickle
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.joint_cusum import dcc, mc
from r2h.joint_cusum.pipeline import load_cfg, load_returns
from r2h.joint_cusum.scores import TailTable, all_subsets, build_tail_table

OUT = ROOT / "outputs" / "t15" / "mc"
G: dict = {}  # fork 로 작업자에게 넘기는 읽기 전용 상태


def _dates(cfg: dict) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(load_returns(cfg, ROOT / "data" / "raw").index)


def _models() -> dict:
    with open(OUT / "models.pkl", "rb") as fh:
        return pickle.load(fh)


def _tables() -> TailTable:
    z = np.load(OUT / "tail_table.npz")
    return TailTable(z["table"], z["n_pool"])


def cmd_fit(cfg: dict) -> None:
    """관측 수익률로 DCC-t 와 CCC-t 를 한 번 적합 (계약 §6.1: 2019-01-03..2025-12-30, 추가 적합 기간 없음)."""
    R = load_returns(cfg, ROOT / "data" / "raw")
    models = {k: dcc.fit_multit(R.to_numpy(), k, tuple(R.columns)) for k in ("DCC", "CCC")}
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "models.pkl", "wb") as fh:
        pickle.dump(models, fh)
    rows = []
    for k, m in models.items():
        for tk, g in zip(R.columns, m.margins, strict=True):
            rows.append(
                {
                    "model": k,
                    "ticker": tk,
                    "mu": g.mu,
                    "omega": g.omega,
                    "alpha": g.alpha,
                    "beta": g.beta,
                    "nu_margin": g.nu,
                    "success": g.success,
                }
            )
        rows.append(
            {
                "model": k,
                "ticker": "JOINT",
                "a": m.a,
                "b": m.b,
                "nu_joint": m.nu,
                "loglik": m.loglik,
                "success": m.success,
            }
        )
        num = dcc.validity_numeric(m)
        (OUT / f"N1_{k}.json").write_text(json.dumps(num, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(OUT / "null_model_params.csv", index=False, float_format="%.10g")
    print("fit done", {k: (round(m.a, 4), round(m.b, 4), round(m.nu, 3)) for k, m in models.items()})


# ── 작업자 함수 (fork 상속 G 사용) ──────────────────────────────────


def _w_cal(rep: int) -> tuple[int, dict]:
    return rep, mc.calibration_rep(G["model"], G["dates"], G["cfg"], rep)


def _w_eval(rep: int) -> tuple[int, dict]:
    return rep, mc.eval_rep(G["model"], G["dates"], G["cfg"], G["tt"], G["domain"], rep, G["holdout"])


def _w_alt(job: tuple[str, int]) -> tuple[tuple[str, int], dict]:
    name, rep = job
    return job, mc.alt_rep(G["model"], G["dates"], G["cfg"], G["tt"], G["crit"], G["pipe_crit"], name, rep)


def _pool(workers: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork"))


def _run(fn, jobs, workers: int, label: str) -> list:
    t0 = time.time()
    out = []
    if workers <= 1:
        for j in jobs:
            out.append(fn(j))
    else:
        with _pool(workers) as ex:
            for k, res in enumerate(ex.map(fn, jobs, chunksize=1)):
                out.append(res)
                if (k + 1) % max(1, len(jobs) // 20) == 0:
                    el = time.time() - t0
                    print(
                        f"[{label}] {k + 1}/{len(jobs)} {el / 60:.1f}분 (예상 총 {el / (k + 1) * len(jobs) / 60:.1f}분)",
                        flush=True,
                    )
    print(f"[{label}] 완료 {len(jobs)} 반복, {(time.time() - t0) / 60:.2f}분", flush=True)
    return out


def _stack(results: list, n: int) -> dict[str, np.ndarray]:
    """rep 순서로 정렬해 키별로 쌓는다."""
    results = sorted(results, key=lambda x: x[0])
    if [r[0] for r in results] != list(range(n)):
        raise AssertionError("반복 번호 누락")
    keys = results[0][1].keys()
    return {k: np.stack([r[1][k] for r in results]) for k in keys}


def cmd_benchmark(cfg: dict, reps: int) -> None:
    """G2: 반복 1회의 CPU·wall·최대 RSS (보정 반복 = 전체 재적합 포함), 작업자 수별 처리량."""
    G.update(model=_models()["DCC"], dates=_dates(cfg), cfg=cfg)
    rows = []
    for k in range(reps):
        c0, w0 = time.process_time(), time.time()
        mc.calibration_rep(
            G["model"], G["dates"], cfg, 10_000_000 + k
        )  # benchmark 전용 rep 번호 (공식 영역과 겹치지 않음)
        rows.append(
            {
                "mode": "sequential",
                "workers": 1,
                "rep": k,
                "cpu_s": time.process_time() - c0,
                "wall_s": time.time() - w0,
            }
        )
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    for workers in (4, 8, 16, 22):
        jobs = list(range(20_000_000, 20_000_000 + workers * 2))
        w0 = time.time()
        _run(_w_cal, jobs, workers, f"bench{workers}")
        wall = time.time() - w0
        rows.append(
            {
                "mode": "parallel",
                "workers": workers,
                "rep": len(jobs),
                "cpu_s": np.nan,
                "wall_s": wall,
                "throughput_rep_per_min": len(jobs) / wall * 60,
            }
        )
    df = pd.DataFrame(rows)
    df["max_rss_mb_parent"] = rss_mb
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "benchmark.csv", index=False, float_format="%.4g")
    print(df.to_string())


def cmd_calibration(cfg: dict, reps: int, workers: int) -> None:
    G.update(model=_models()["DCC"], dates=_dates(cfg), cfg=cfg)
    res = _run(_w_cal, list(range(reps)), workers, "calibration")
    arr = _stack(res, reps)
    np.save(OUT / "cal_T.npy", arr.pop("T"))
    np.save(OUT / "cal_E.npy", arr.pop("E"))
    np.savez(OUT / "cal_diag.npz", **arr)


def cmd_tables(cfg: dict) -> None:
    """보정 반복 → 꼬리표 (주 창 4개, K=100,001), 단기 창 임계값, E(h) 꼬리표."""
    T = np.load(OUT / "cal_T.npy", mmap_mode="r")
    K = int(cfg["tail_score"]["table_size_K"])
    tt = build_tail_table(np.asarray(T[:, :, :, :4, :], dtype=np.float64), K)
    np.savez(OUT / "tail_table.npz", table=tt.table, n_pool=tt.n_pool)
    E = np.load(OUT / "cal_E.npy", mmap_mode="r")
    te = build_tail_table(np.asarray(E, dtype=np.float64), 10_001)
    np.savez(OUT / "energy_table.npz", table=te.table, n_pool=te.n_pool)
    dates = _dates(cfg)
    years = cfg["sample"]["evaluation_years"]
    ev = dates[
        (dates >= pd.Timestamp(f"{years[0]}-01-01")) & (dates < pd.Timestamp(f"{years[-1] + 1}-01-01"))
    ]
    yod = ev.year.to_numpy()
    pos = np.zeros(len(ev), dtype=int)
    for y in years:
        m = yod == y
        pos[m] = np.arange(int(m.sum()))
    am = np.stack(
        [mc.annual_max_common(np.asarray(T[r], dtype=np.float64), yod, pos) for r in range(T.shape[0])]
    )
    np.save(OUT / "cal_annual_max.npy", am)
    print("tables done", tt.table.shape, int(tt.n_pool.min()), int(tt.n_pool.max()))


def cmd_eval(cfg: dict, domain: str, reps: int, workers: int) -> None:
    kind = "CCC" if domain == "null_eval_ccc" else "DCC"
    G.update(
        model=_models()[kind],
        dates=_dates(cfg),
        cfg=cfg,
        tt=_tables(),
        domain=domain,
        holdout=domain == "null_holdout",
    )
    res = _run(_w_eval, list(range(reps)), workers, domain)
    np.savez(OUT / f"{domain}.npz", **_stack(res, reps))


def cmd_alt(cfg: dict, reps: int, workers: int) -> None:
    """대립 시나리오. 유의일 임계값은 null_eval_dcc 에서 (S1: 0.98 분위, 부분집합: 1−0.02/57 분위)."""
    tickers = list(cfg["universe"]["tickers"])
    subs = all_subsets(tickers)
    null = np.load(OUT / "null_eval_dcc.npz")
    a1, a2 = cfg["multiple_testing"]["alpha_primary"], cfg["multiple_testing"]["alpha_secondary"] / len(subs)
    crit: dict[str, float] = {}
    for s_i, s in enumerate(subs):
        q = 1 - (a1 if s == tuple(cfg["universe"]["stages"]["S1"]) else a2)
        crit[f"day:{'+'.join(s)}"] = float(np.quantile(null["M_subset"][:, s_i], q, method="higher"))
    am = np.load(OUT / "cal_annual_max.npy")  # (reps, ETF, 정책, 창7, 연도)
    for i, tk in enumerate(tickers):
        for p_i, p in enumerate(("A", "B", "base")):
            for w_i, w in enumerate(cfg["pipeline"]["windows_short_eligibility"]):
                v = am[:, i, p_i, 4 + w_i, :].ravel()
                crit[f"short:{tk}:{p}:{w}"] = float(np.nanquantile(v, 0.95))
    pipe = pd.read_csv(
        ROOT / "research/window_study_w1/results/03_synthetic/pipeline/pipeline_thresholds.csv"
    )
    pipe_crit = {
        (p, int(w)): float(c) for p, w, c in zip(pipe.policy, pipe.w, pipe.critical_annual_max, strict=True)
    }
    # 목표 가족 → (라벨, 부분집합) — 설정 targets 를 기계적으로 풀기만 한다
    stages = cfg["universe"]["stages"]
    resolved = {}
    for name, targets in cfg["alternatives"]["targets"].items():
        lst = []
        for tgt in targets:
            if tgt.startswith("subset:"):
                lst.append((tgt, tuple(t for t in tickers if t in tgt.split(":")[1].split("+"))))
            else:
                lst.append((tgt, tuple(stages[tgt])))
        resolved[name] = lst
    cfg = {**cfg, "alternatives": {**cfg["alternatives"], "targets_resolved": resolved}}
    (OUT / "alt_criticals.json").write_text(json.dumps(crit, indent=1), encoding="utf-8")
    G.update(model=_models()["DCC"], dates=_dates(cfg), cfg=cfg, tt=_tables(), crit=crit, pipe_crit=pipe_crit)
    jobs = [(name, r) for name in cfg["alternatives"]["scenarios"] for r in range(reps)]
    res = _run(_w_alt, jobs, workers, "alt")
    with open(OUT / "alt_results.pkl", "wb") as fh:
        pickle.dump(sorted(res, key=lambda x: (x[0][0], x[0][1])), fh)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fit", "benchmark", "calibration", "tables", "eval", "alt"])
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--domain", default="null_eval_dcc")
    a = ap.parse_args()
    cfg = load_cfg()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.cmd == "fit":
        cmd_fit(cfg)
    elif a.cmd == "benchmark":
        cmd_benchmark(cfg, a.reps)
    elif a.cmd == "calibration":
        cmd_calibration(cfg, a.reps, a.workers)
    elif a.cmd == "tables":
        cmd_tables(cfg)
    elif a.cmd == "eval":
        cmd_eval(cfg, a.domain, a.reps, a.workers)
    elif a.cmd == "alt":
        cmd_alt(cfg, a.reps, a.workers)
    log = {
        "cmd": a.cmd,
        "reps": a.reps,
        "workers": a.workers,
        "domain": a.domain,
        "wall_s": time.time() - t0,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(OUT / "run_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(log, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
