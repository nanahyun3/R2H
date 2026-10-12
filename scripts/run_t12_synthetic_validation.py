"""T12 합성 타당성 (G2/G5) — ``uv run python scripts/run_t12_synthetic_validation.py [--workers 4] [--out DIR]``.

검출기 수준 DGP × detector_reps, 파이프라인 수준 DGP × pipeline_reps. 결과: ``null_dgp_validation.csv``
(실제 시세 없음 → 공개 가능). 정답은 생성 과정에서만 알려진다 (SYNTHETIC_CAUSAL_KNOWN_ONLY).
"""

import os

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from r2h.annual_expanding.config import REPO_ROOT, config_hash, load_config, rng_for  # noqa: E402
from r2h.annual_expanding.synthetic import (  # noqa: E402
    DETECTOR_DGPS,
    PIPELINE_DGPS,
    evaluate,
    pipeline_rep,
    wilson,
)
from r2h.annual_expanding.worker import frame_bytes  # noqa: E402

TESTS = {
    "rej_asym": ("annual_posthoc", "asymptotic_1.3397"),
    "rej_iid": ("annual_posthoc", "iid_history_bootstrap"),
    "rej_block": ("annual_posthoc", "block_history_bootstrap(L=10, different null)"),
    "pure_any": ("rolling_w60_PURE_any_episode_in_year", "iid_history_bootstrap_pointwise95"),
    "carry_any": ("rolling_w60_CARRY_any_episode_in_year", "iid_history_bootstrap_pointwise95"),
    "carry_warm_any": ("rolling_w60_CARRY_warm_days_any_episode", "iid_history_bootstrap_pointwise95"),
}


def detector_job(args):
    name, cfg = args
    gen, _kind, _ = DETECTOR_DGPS[name]
    syn = cfg["synthetic"]
    out = []
    for rep in range(syn["detector_reps"]):
        key = (cfg["study_id"], "detector", name, rep)
        sc = gen(rng_for(*key, "dgp"), syn["n_history"], syn["n_year"])
        out.append(
            evaluate(sc, w=60, cfg=cfg, key=key, asym=cfg["cusum"]["asymptotic_critical_5pct"], reps=1000)
        )
    return name, out


def pipeline_job(args):
    name, rep, cfg = args
    return name, rep, pipeline_rep(name, rep, cfg)


def summarize(name, kind, desc, level, recs, limitations):
    rows = []
    df = pd.DataFrame(recs)
    for col, (test, calib) in TESTS.items():
        k, n = int(df[col].sum()), len(df)
        lo, hi = wilson(k, n)
        is_h0 = kind == "H0"
        d = df["delay"].dropna() if col == "pure_any" and kind != "H0" else pd.Series(dtype=float)
        rows.append(
            {
                "dgp_name": name,
                "dgp_kind": kind,
                "parameter_set": desc,
                "level": level,
                "history_protocol": "pre-year pool n=490 (same DGP regime)"
                if level == "detector"
                else "annual SVR fit on 490-day history (27 grid), policy A",
                "policy": "residual-level" if level == "detector" else "A",
                "window": 60 if "rolling" in test else "",
                "test": test,
                "calibration": calib,
                "mc_reps": n,
                "rejections": k,
                "rate": k / n,
                "rate_ci_low": lo,
                "rate_ci_high": hi,
                "empirical_size": k / n if is_h0 else np.nan,
                "size_ci_low": lo if is_h0 else np.nan,
                "size_ci_high": hi if is_h0 else np.nan,
                "power": k / n if not is_h0 else np.nan,
                "delay_distribution": (
                    f"median={d.median():.0f};q25={d.quantile(0.25):.0f};q75={d.quantile(0.75):.0f};n={d.size}"
                    if d.size
                    else ""
                ),
                "coverage": "",
                "truth_known": "SYNTHETIC_CAUSAL_KNOWN_ONLY",
                "limitations": limitations,
            }
        )
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(REPO_ROOT / "outputs" / "t12" / "synthetic"))
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    t0 = time.time()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("spawn")
    rows, raw = [], {}
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=ctx) as ex:
        for name, recs in ex.map(detector_job, [(n, cfg) for n in DETECTOR_DGPS]):
            raw[name] = recs
            gen, kind, desc = DETECTOR_DGPS[name]
            lim = "residuals generated directly; bootstrap reps 1000 (block 500) per replicate"
            rows += summarize(name, kind, desc, "detector", recs, lim)
            print(f"detector {name} done ({time.time() - t0:.0f}s)", flush=True)
        jobs = [(n, r, cfg) for n in PIPELINE_DGPS for r in range(cfg["synthetic"]["pipeline_reps"])]
        prec: dict[str, list] = {n: [] for n in PIPELINE_DGPS}
        for name, _rep, rec in ex.map(pipeline_job, jobs, chunksize=10):
            prec[name].append(rec)
        for name, recs in prec.items():
            raw[name] = recs
            lim = (
                f"few reps ({len(recs)}); bootstrap reps {cfg['calibration']['iid_reps'] // 5}; one GARCH parameter set; "
                f"nonpositive-variance days total={sum(r['nonpos_var_days'] for r in recs)}"
            )
            rows += summarize(name, PIPELINE_DGPS[name], name, "pipeline", recs, lim)
            print(f"pipeline {name} done ({time.time() - t0:.0f}s)", flush=True)
    table = pd.DataFrame(rows)
    data = frame_bytes(table)
    (out / "null_dgp_validation.csv").write_bytes(data)
    (out / "replicates.json").write_text(json.dumps(raw, default=lambda x: None if x is None else int(x)))
    man = {
        "config_hash": config_hash(cfg),
        "sha256": hashlib.sha256(data).hexdigest(),
        "runtime_s": round(time.time() - t0, 1),
    }
    (out / "synthetic_manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(man)
    if a.publish:
        dst = REPO_ROOT / cfg["release"]["results_dir"]
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "null_dgp_validation.csv").write_bytes(data)
        (dst / "synthetic_manifest.json").write_text(json.dumps(man, indent=1) + "\n")
