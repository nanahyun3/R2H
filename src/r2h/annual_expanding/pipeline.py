"""T12 오케스트레이션 — 데이터 검증 → ETF 별 worker (순차/프로세스 병렬) → 안정 정렬 병합 → BH → profile → manifest.

병렬 단위는 ticker (PROTOCOL_LOCK L9). 병합 결과는 worker 수·완료 순서와 무관해야 하며, 그 동치성은
``parallel_reproducibility.csv`` 로 검증한다.
"""

from __future__ import annotations

import hashlib
import io
import json
import multiprocessing as mp
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..svrgarch_etf.data import load_close_panel, percent_log_returns, reference
from .config import REPO_ROOT, config_hash
from .diagnostics import bh_qvalues
from .profile import build_profile
from .worker import frame_bytes, run_ticker

TABLES: tuple[str, ...] = (
    "fold_manifest",
    "fit_summary",
    "annual_vol_diagnostics",
    "annual_forecast_diagnostics",
    "annual_residual_diagnostics",
    "annual_posthoc",
    "annual_cusum_diagnostics",
    "annual_history_ablation",
)
SORT_KEYS = ("ticker", "year", "policy", "history_strategy", "window", "boundary_mode", "calibration_method")
PK: dict[str, tuple[str, ...]] = {
    "fold_manifest": ("ticker", "year", "history_strategy"),
    "fit_summary": ("ticker", "year", "history_strategy"),
    "annual_vol_diagnostics": ("ticker", "year"),
    "annual_forecast_diagnostics": ("ticker", "year", "policy"),
    "annual_residual_diagnostics": ("ticker", "year", "policy"),
    "annual_posthoc": ("ticker", "year", "policy", "calibration_method"),
    "annual_cusum_diagnostics": ("ticker", "year", "policy", "window", "boundary_mode", "calibration_method"),
    "annual_history_ablation": ("ticker", "year", "policy", "history_strategy"),
    "diagnostic_profile": ("ticker", "year", "policy"),
}
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def code_sha() -> str:
    """T12 실행 코드(annual_expanding + 재사용 T11/paper2020 모듈)의 내용 해시 — 커밋 여부와 무관."""
    h = hashlib.sha256()
    for sub in ("annual_expanding", "paper2020", "svrgarch_etf"):
        for p in sorted((REPO_ROOT / "src" / "r2h" / sub).glob("*.py")):
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def git_sha() -> str:
    try:
        sha = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", "src", "configs", "scripts"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sort(df: pd.DataFrame) -> pd.DataFrame:
    keys = [k for k in SORT_KEYS if k in df.columns]
    if not keys or df.empty:
        return df
    tmp = df.copy()
    for k in keys:  # None/NaN 이 섞인 열도 문자열로 안정 정렬
        tmp[f"__{k}"] = tmp[k].astype(str)
    tmp = tmp.sort_values([f"__{k}" for k in keys], kind="mergesort")
    return tmp.drop(columns=[f"__{k}" for k in keys]).reset_index(drop=True)


def _worker_entry(args: tuple[str, pd.Series, dict, str, dict]) -> dict[str, Any]:
    return run_ticker(*args)


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"ticker": str}, keep_default_na=True)


def merge(work: Path, tickers: list[str], cfg: dict) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for name in TABLES:
        frames = [
            _read(work / t / f"{name}.csv") for t in tickers if (work / t / f"{name}.csv").stat().st_size > 1
        ]
        out[name] = _sort(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
    # BH — 범위: (검정 종류 × 정책 × history_strategy) 마다 20 ETF × 7 연도 (L6)
    rd = out["annual_residual_diagnostics"]
    for col in ("ljungbox_e_p", "ljungbox_e2_p", "archlm_p"):
        qcol = col[:-2] + "_q"
        rd[qcol] = np.nan
        for _, g in rd.groupby(["policy", "history_strategy"], sort=True):
            rd.loc[g.index, qcol] = bh_qvalues(g[col].to_numpy(float))
    rd["multiple_testing_scope"] = "BH within (test, policy, history_strategy) over tickers x years"
    out["annual_residual_diagnostics"] = rd
    out["diagnostic_profile"] = _sort(build_profile(out, cfg))
    return out


def integrity(tables: dict[str, pd.DataFrame], tickers: list[str], cfg: dict) -> pd.DataFrame:
    """PK 유일성 · 기대 행 수 (명세 §6)."""
    ny = len(cfg["folds"]["test_calendar_years"])
    nt = len(tickers)
    nw = len(cfg["cusum"]["windows"])
    exp = {
        "fold_manifest": nt * ny * 3,
        "annual_vol_diagnostics": nt * ny,
        "annual_forecast_diagnostics": nt * ny * 3,
        "annual_residual_diagnostics": nt * ny * 3,
        "annual_posthoc": nt * ny * 3 * 5,
        "annual_cusum_diagnostics": nt * ny * 3 * nw * 2 * 5,
        "annual_history_ablation": nt * ny * 2 * 3,
        "diagnostic_profile": nt * ny * 3,
    }
    rows = []
    for name, df in tables.items():
        pk = list(PK[name])
        dup = int(df.duplicated(pk).sum()) if not df.empty else 0
        e = exp.get(name)
        rows.append(
            {
                "table": name,
                "rows": len(df),
                "expected_rows": e if e is not None else "",
                "pk": ",".join(pk),
                "pk_duplicates": dup,
                "status": "PASS" if dup == 0 and (e is None or e == len(df)) else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def run(
    *,
    cfg: dict,
    run_id: str,
    workers: int = 1,
    tickers: list[str] | None = None,
    raw_dir: str | Path | None = None,
    out_root: str | Path | None = None,
    log: Any = print,
) -> dict[str, Any]:
    t0 = time.time()
    for k in THREAD_ENV:
        os.environ[k] = "1"
    panel = load_close_panel(raw_dir)
    if panel.data_version != cfg["expected_data_version"]:
        raise RuntimeError(f"data_version {panel.data_version} != expected {cfg['expected_data_version']}")
    r = percent_log_returns(panel.close)
    universe = list(reference()["ticker"])
    if len(universe) != cfg["expected_n_tickers"] or list(r.columns) != universe:
        raise RuntimeError("ticker universe differs from reference_close_sha256.csv")
    tick = tickers or universe
    if any(t not in universe for t in tick):
        raise ValueError("unknown ticker")
    root = Path(out_root) if out_root else REPO_ROOT / cfg["release"]["work_dir"]
    work = root / run_id
    work.mkdir(parents=True, exist_ok=True)
    meta = {"data_version": panel.data_version, "git_sha": git_sha(), "code_sha": code_sha()}
    jobs = [(t, r[t], cfg, str(work), meta) for t in tick]
    done: list[dict[str, Any]] = []
    if workers <= 1:
        for j in jobs:
            done.append(_worker_entry(j))
            log(f"{j[0]} done ({time.time() - t0:.0f}s)")
    else:
        env_backup = {k: os.environ.pop(k, None) for k in ("PYTHONPATH", "VIRTUAL_ENV", "LD_LIBRARY_PATH")}
        try:
            with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
                for d in ex.map(_worker_entry, jobs):
                    done.append(d)
                    log(f"{d['ticker']} done ({time.time() - t0:.0f}s)")
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v
    for d in done:
        if d["config_hash"] != config_hash(cfg) or d["code_sha"] != meta["code_sha"]:
            raise RuntimeError("worker output hash mismatch")
    tables = merge(work, tick, cfg)
    merged = work / "merged"
    merged.mkdir(exist_ok=True)
    hashes = {}
    for name, df in tables.items():
        data = frame_bytes(df)
        (merged / f"{name}.csv").write_bytes(data)
        hashes[f"{name}.csv"] = hashlib.sha256(data).hexdigest()
    integ = integrity(tables, tick, cfg)
    (merged / "integrity.csv").write_bytes(frame_bytes(integ))
    agg = hashlib.sha256("".join(f"{k}:{v}" for k, v in sorted(hashes.items())).encode()).hexdigest()
    import sklearn

    manifest = {
        "study_id": cfg["study_id"],
        "protocol_version": cfg["protocol_version"],
        "run_id": run_id,
        "n_workers": workers,
        "tickers": tick,
        "config_hash": config_hash(cfg),
        "data_version": panel.data_version,
        "close_hash_ok": panel.hash_ok,
        "input_sha_per_ticker": {
            d["ticker"]: d["input_sha"] for d in sorted(done, key=lambda x: x["ticker"])
        },
        "git_sha": meta["git_sha"],
        "code_sha": meta["code_sha"],
        "t11_reference_sha": "a346faf78ff47b2695fab438f7397d7958b8d655",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "uv_lock_sha256": hashlib.sha256((REPO_ROOT / "uv.lock").read_bytes()).hexdigest(),
            "thread_env": {k: os.environ.get(k) for k in THREAD_ENV},
        },
        "outputs_sha256": hashes,
        "aggregate_hash": agg,
        "integrity_pass": bool((integ.status == "PASS").all()),
        "runtime_seconds_excluded_from_hash": round(time.time() - t0, 1),
    }
    (merged / "run_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, default=str) + "\n"
    )
    log(
        f"merged → {merged} · aggregate {agg[:16]} · integrity {'PASS' if manifest['integrity_pass'] else 'FAIL'}"
    )
    return manifest


def numeric_max_diff(a: Path, b: Path) -> float:
    """두 병합 폴더의 같은 표에서 수치 열 최대 절대 차이 (행·열 정렬 동일 가정)."""
    worst = 0.0
    for name in (*TABLES, "diagnostic_profile"):
        x = pd.read_csv(io.BytesIO((a / f"{name}.csv").read_bytes()), dtype={"ticker": str})
        y = pd.read_csv(io.BytesIO((b / f"{name}.csv").read_bytes()), dtype={"ticker": str})
        if x.shape != y.shape or list(x.columns) != list(y.columns):
            return float("inf")
        num = x.select_dtypes("number").columns
        if len(num):
            d = np.nanmax(np.abs(x[num].to_numpy(float) - y[num].to_numpy(float)), initial=0.0)
            worst = max(worst, float(d))
    return worst
