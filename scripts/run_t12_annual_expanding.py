"""T12 v2 실행 — ``uv run python scripts/run_t12_annual_expanding.py [--workers N] [--tickers ...] [--run-id ID]``.

원시 시세는 ``--raw-dir`` (또는 ``ETF_RAW_DIR``; 기본 ``data/raw``) 에서 읽고 종가 해시가 기준과 다르면 멈춘다.
출력: ``outputs/t12/work/<run_id>/`` (일별 캐시 포함, git 제외). ``--publish`` 면 병합 결과표를
``research/t12_annual_expanding_v2/results/`` 로 복사한다 (일별 파일 제외).
"""

import os

# BLAS/OpenMP 스레드 과다 생성 방지 — numpy import 전에 고정 (PROTOCOL_LOCK L9)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"

import argparse  # noqa: E402
import shutil  # noqa: E402

from r2h.annual_expanding.config import REPO_ROOT, load_config  # noqa: E402
from r2h.annual_expanding.pipeline import run  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="T12 v2 annual expanding SVR-GARCH CUSUM diagnostics")
    ap.add_argument("--config", default=None)
    ap.add_argument("--raw-dir", default=os.environ.get("ETF_RAW_DIR") or str(REPO_ROOT / "data" / "raw"))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--tickers", nargs="*", default=None)
    ap.add_argument("--run-id", default="dev")
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    cfg = load_config(a.config)
    cpu = os.cpu_count() or 1
    workers = max(1, min(a.workers, cfg["parallel"]["default_max_workers"], cpu))
    m = run(cfg=cfg, run_id=a.run_id, workers=workers, tickers=a.tickers, raw_dir=a.raw_dir)
    if a.publish:
        if not m["integrity_pass"] or a.tickers:
            raise SystemExit("publish requires a full-universe run with integrity PASS")
        src = REPO_ROOT / cfg["release"]["work_dir"] / a.run_id / "merged"
        dst = REPO_ROOT / cfg["release"]["results_dir"]
        dst.mkdir(parents=True, exist_ok=True)
        for p in sorted(src.iterdir()):
            shutil.copy2(p, dst / p.name)
        print(f"published {len(list(src.iterdir()))} files → {dst}")
