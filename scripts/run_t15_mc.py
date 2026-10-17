# ruff: noqa: E402, E501  — 스레드 환경변수를 numpy import 전에 정한다 · 한국어 설명 문자열
"""W3 (T15) 전체 재적합 Monte Carlo 실행기 (계약 W3-lock-2 §9–§11, D1·D15).

사용 (R2H .venv):
  python scripts/run_t15_mc.py fit                      # 평가연도별 DCC-t·CCC-t 적합 (y 이전 자료) → outputs/t15/mc/models.pkl
  python scripts/run_t15_mc.py benchmark --reps 3       # BENCHMARK: 경로당 CPU·wall·RSS, 병렬 4/8/16/22
  python scripts/run_t15_mc.py calibration --reps N --workers W      # H0_CALIBRATION
  python scripts/run_t15_mc.py tables                   # 위치 구간별 꼬리표 · W3 개별 임계값
  python scripts/run_t15_mc.py eval --domain dcc|ccc|holdout|robustness --reps N --workers W
  python scripts/run_t15_mc.py alt --reps N --workers W # H1_POWER
  python scripts/run_t15_mc.py h0a --reps N --workers W # H0-A (관측 Q 재배열)
  python scripts/run_t15_mc.py finalize
결과는 Git 제외 ``outputs/t15/mc/`` 에 쓴다. 반복의 시드는 (study_id, seed, 영역, rep) 로 정해져 작업자 수와 무관하다.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"  # 작업자당 스레드 1 (설정 monte_carlo.threads_per_worker)

import argparse
import hashlib
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
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.joint_cusum import dcc, mc
from r2h.joint_cusum.pipeline import load_cfg, load_returns
from r2h.joint_cusum.scores import TailTable, all_subsets, build_tail_table

OUT = ROOT / "outputs" / "t15" / "mc"
G: dict = {}  # fork 로 작업자에게 넘기는 읽기 전용 상태
EVAL_DOMAIN = {
    "dcc": ("DCC", "H0_EVALUATION"),
    "ccc": ("CCC", "H0_EVALUATION"),
    "holdout": ("DCC", "H0_EVALUATION_HOLDOUT"),
    "robustness": ("DCC", "ROBUSTNESS"),
}


def _dates(cfg: dict) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(load_returns(cfg, ROOT / "data" / "raw").index)


def _models() -> dict:
    with open(OUT / "models.pkl", "rb") as fh:
        return pickle.load(fh)


def _tables(name: str = "tail_table") -> TailTable:
    z = np.load(OUT / f"{name}.npz")
    return TailTable(z["table"], z["n_pool"], z["edges"])


def ljung_box(x: np.ndarray, lags: int = 10) -> float:
    """Ljung–Box p 값 (자기상관 1..lags)."""
    x = np.asarray(x, float) - np.mean(x)
    n = x.size
    den = np.sum(x * x)
    q = sum((np.sum(x[k:] * x[:-k]) / den) ** 2 / (n - k) for k in range(1, lags + 1)) * n * (n + 2)
    return float(stats.chi2.sf(q, lags))


def cmd_fit(cfg: dict) -> None:
    """평가연도 y 마다 y 이전 수익률로 DCC-t·CCC-t 적합 (lock-2 §10 시간 경계). 다른 적합 기간은 추가하지 않는다."""
    R = load_returns(cfg, ROOT / "data" / "raw")
    models: dict = {"DCC": {}, "CCC": {}}
    rows, n1, lb = [], [], []
    for y in cfg["sample"]["evaluation_years"]:
        X = R[R.index < pd.Timestamp(f"{y}-01-01")]
        for k in ("DCC", "CCC"):
            m = dcc.fit_multit(X.to_numpy(), k, tuple(R.columns))
            models[k][y] = m
            for tk, g in zip(R.columns, m.margins, strict=True):
                rows.append(
                    {
                        "model": k,
                        "year": y,
                        "n_fit": len(X),
                        "ticker": tk,
                        "mu": g.mu,
                        "omega": g.omega,
                        "alpha": g.alpha,
                        "beta": g.beta,
                        "persistence": g.persistence,
                        "nu_margin": g.nu,
                        "success": g.success,
                    }
                )
            rows.append(
                {
                    "model": k,
                    "year": y,
                    "n_fit": len(X),
                    "ticker": "JOINT",
                    "a": m.a,
                    "b": m.b,
                    "nu_joint": m.nu,
                    "loglik": m.loglik,
                    "success": m.success,
                }
            )
            for key, ok in dcc.validity_numeric(m).items():
                n1.append({"model": k, "year": y, "check": key, "ok": bool(ok)})
            if k == "DCC":
                for tk, g in zip(R.columns, m.margins, strict=True):
                    _, z = dcc.garch_filter(X[tk].to_numpy(), g)
                    lb.append(
                        {"year": y, "ticker": tk, "lb10_z_p": ljung_box(z), "lb10_z2_p": ljung_box(z**2)}
                    )
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "models.pkl", "wb") as fh:
        pickle.dump(models, fh)
    pd.DataFrame(rows).to_csv(OUT / "null_model_params.csv", index=False, float_format="%.10g")
    pd.DataFrame(n1).to_csv(OUT / "null_model_N1.csv", index=False)
    pd.DataFrame(lb).to_csv(OUT / "null_model_ljungbox.csv", index=False, float_format="%.6g")
    bad = [r for r in n1 if not r["ok"]]
    print("fit done; N1 failures:", [(r["model"], r["year"], r["check"]) for r in bad])


# ── 작업자 함수 (fork 상속 G 사용) ──────────────────────────────────


def _w_cal(rep: int) -> tuple[int, dict]:
    return rep, mc.calibration_rep(G["models"], G["dates"], G["cfg"], rep)


def _w_eval(rep: int) -> tuple[int, dict]:
    return rep, mc.eval_rep(
        G["models"], G["dates"], G["cfg"], G["tt"], G["domain"], rep, G["holdout"], G["burn"]
    )


def _w_alt(job: tuple[str, int]) -> tuple[tuple[str, int], dict]:
    name, rep = job
    return job, mc.alt_rep(G["models"], G["dates"], G["cfg"], G["tt"], G["crit"], G["pipe_crit"], name, rep)


def _w_h0a(rep: int) -> tuple[int, dict]:
    from r2h.joint_cusum.h0a import transform_Q
    from r2h.joint_cusum.scores import rep_statistics

    Qt, diag = transform_Q(
        G["Q"], G["yod"], G["wins"], G["method"], mc.rep_rng(G["cfg"], f"H0A:{G['method']}", rep)
    )
    st = rep_statistics(Qt, G["cfg"])
    return rep, {
        "M_subset": st.M_subset,
        "C_stage": st.C_stage,
        "M2_stage": st.M2_stage,
        "junction": np.array(diag["junction"]),
        "transform_key": np.array(diag["key"]),
    }


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
    """BENCHMARK: 반복 1회 (연도별 귀무 모의 + 6종 × 5개 연도 SVR 재적합 + 7개 창) 의 CPU·wall·RSS, 작업자 수별 처리량."""
    G.update(models=_models()["DCC"], dates=_dates(cfg), cfg=cfg)
    rows = []
    for k in range(reps):
        c0, w0 = time.process_time(), time.time()
        mc.calibration_rep(
            G["models"], G["dates"], cfg, 10_000_000 + k
        )  # BENCHMARK 전용 rep 번호 (공식 영역과 겹치지 않음)
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
    for workers in (8, 16, 22):
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
    df.to_csv(OUT / "benchmark.csv", index=False, float_format="%.4g")
    print(df.to_string())


def cmd_calibration(cfg: dict, reps: int, workers: int) -> None:
    G.update(models=_models()["DCC"], dates=_dates(cfg), cfg=cfg)
    res = _run(_w_cal, list(range(reps)), workers, "H0_CALIBRATION")
    arr = _stack(res, reps)
    np.save(OUT / "cal_T.npy", arr.pop("T"))
    np.save(OUT / "cal_E.npy", arr.pop("E"))
    np.save(OUT / "cal_annual_max_own.npy", arr.pop("annual_max_own"))
    np.savez(OUT / "cal_diag.npz", **arr)


def _eval_pos(cfg: dict) -> np.ndarray:
    dates = _dates(cfg)
    years = cfg["sample"]["evaluation_years"]
    ev = dates[
        (dates >= pd.Timestamp(f"{years[0]}-01-01")) & (dates < pd.Timestamp(f"{years[-1] + 1}-01-01"))
    ]
    pos = np.zeros(len(ev), dtype=int)
    for y in years:
        m = ev.year == y
        pos[m] = np.arange(int(m.sum()))
    return pos


def cmd_tables(cfg: dict) -> None:
    """H0_CALIBRATION → 위치 구간별 꼬리표 (주 창 4개, K=100,001) · E(h) 꼬리표 · W3 개별 임계값 (own-valid 연간 최대 95%)."""
    T = np.load(OUT / "cal_T.npy", mmap_mode="r")
    pos = _eval_pos(cfg)
    edges = cfg["tail_score"]["position_bins"]
    tt = build_tail_table(
        np.asarray(T[:, :, :, :4, :], dtype=np.float64), pos, edges, int(cfg["tail_score"]["table_size_K"])
    )
    np.savez(OUT / "tail_table.npz", table=tt.table, n_pool=tt.n_pool, edges=tt.edges)
    E = np.load(OUT / "cal_E.npy", mmap_mode="r")
    te = build_tail_table(np.asarray(E, dtype=np.float64), pos, edges, 10_001)
    np.savez(OUT / "energy_table.npz", table=te.table, n_pool=te.n_pool, edges=te.edges)
    am = np.load(OUT / "cal_annual_max_own.npy")  # (reps, ETF, 정책, 창7, 연도)
    tickers = cfg["universe"]["tickers"]
    wins = list(cfg["pipeline"]["windows_primary"]) + list(cfg["pipeline"]["windows_short_eligibility"])
    crit = {}
    for i, tk in enumerate(tickers):
        for p_i, p in enumerate(("A", "B", "base")):
            for w_i, w in enumerate(wins):
                crit[f"w3:{tk}:{p}:{w}"] = float(np.nanquantile(am[:, i, p_i, w_i, :].ravel(), 0.95))
    (OUT / "w3_individual_criticals.json").write_text(json.dumps(crit, indent=1), encoding="utf-8")
    print("tables done", tt.table.shape, "min pool", int(tt.n_pool[tt.n_pool > 0].min()))


def cmd_eval(cfg: dict, which: str, reps: int, workers: int, start: int = 0) -> None:
    kind, domain = EVAL_DOMAIN[which]
    G.update(
        models=_models()[kind],
        dates=_dates(cfg),
        cfg=cfg,
        tt=_tables(),
        domain=domain,
        holdout=which == "holdout",
        burn=2000 if which == "robustness" else 500,
    )
    res = _run(_w_eval, list(range(start, start + reps)), workers, f"{which}")
    res = [(r - start, v) for r, v in res]  # 쌓기용 상대 번호 (시드는 절대 번호로 이미 정해짐)
    name = (
        f"null_eval_{which}.npz" if start == 0 else f"null_eval_{which}_from{start}.npz"
    )  # 연장분은 별도 파일
    np.savez(OUT / name, **_stack(res, reps))


def cmd_alt(cfg: dict, reps: int, workers: int) -> None:
    """H1_POWER. 유의일 기준은 DCC H0_EVALUATION 에서 (S1: 0.98 분위, 부분집합: 1−0.02/57 분위)."""
    tickers = list(cfg["universe"]["tickers"])
    subs = all_subsets(tickers)
    null = np.load(OUT / "null_eval_dcc.npz")
    a1, a2 = cfg["multiple_testing"]["alpha_primary"], cfg["multiple_testing"]["alpha_secondary"] / len(subs)
    crit: dict[str, float] = json.loads((OUT / "w3_individual_criticals.json").read_text())
    for s_i, s in enumerate(subs):
        q = 1 - (a1 if s == tuple(cfg["universe"]["stages"]["S1"]) else a2)
        crit[f"day:{'+'.join(s)}"] = float(np.quantile(null["M_subset"][:, s_i], q, method="higher"))
    pipe = pd.read_csv(
        ROOT / "research/window_study_w1/results/03_synthetic/pipeline/pipeline_thresholds.csv"
    )
    pipe_crit = {
        (p, int(w)): float(c) for p, w, c in zip(pipe.policy, pipe.w, pipe.critical_annual_max, strict=True)
    }
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
    G.update(
        models=_models()["DCC"], dates=_dates(cfg), cfg=cfg, tt=_tables(), crit=crit, pipe_crit=pipe_crit
    )
    jobs = [(name, r) for name in cfg["alternatives"]["scenarios"] for r in range(reps)]
    res = _run(_w_alt, jobs, workers, "H1_POWER")
    with open(OUT / "alt_results.pkl", "wb") as fh:
        pickle.dump(sorted(res, key=lambda x: (x[0][0], x[0][1])), fh)


def cmd_h0a(cfg: dict, reps: int, workers: int) -> None:
    """H0-A: 관측 Q 경로의 ETF·연도별 원형 이동 / 원형 블록 재표집 (재적합 없음). 두 방법은 따로 저장한다."""
    from r2h.joint_cusum.analysis import load_obs

    obs = load_obs(cfg, ROOT)
    for method in cfg["null_models"]["H0A"]["methods"]:
        G.update(
            Q=obs.Q,
            yod=obs.out.year_of_day,
            wins=list(cfg["pipeline"]["windows_primary"]),
            method=method,
            cfg=cfg,
        )
        res = _run(_w_h0a, list(range(reps)), workers, f"H0A_{method}")
        np.savez(OUT / f"h0a_{method}.npz", **_stack(res, reps))


def cmd_finalize() -> None:
    """MC 완료 시점 기록 (구간 표의 inference_completed_at) 과 산출 파일 SHA256."""
    files = sorted(
        p
        for p in OUT.iterdir()
        if p.suffix in {".npz", ".npy", ".pkl", ".json", ".csv"} and p.name != "inference_meta.json"
    )
    meta = {
        "completed_at": time.strftime("%Y-%m-%d"),
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    (OUT / "inference_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print("finalized", len(files))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "cmd", choices=["fit", "benchmark", "calibration", "tables", "eval", "alt", "h0a", "finalize"]
    )
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--domain", default="dcc", choices=list(EVAL_DOMAIN))
    ap.add_argument("--start", type=int, default=0)  # 사전 연장 규칙: 50,000 부터 이어서
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
        cmd_eval(cfg, a.domain, a.reps, a.workers, a.start)
    elif a.cmd == "alt":
        cmd_alt(cfg, a.reps, a.workers)
    elif a.cmd == "h0a":
        cmd_h0a(cfg, a.reps, a.workers)
    elif a.cmd == "finalize":
        cmd_finalize()
    log = {
        "cmd": a.cmd,
        "reps": a.reps,
        "workers": a.workers,
        "domain": a.domain,
        "protocol": cfg["protocol_version"],
        "wall_s": time.time() - t0,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(OUT / "run_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(log, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
