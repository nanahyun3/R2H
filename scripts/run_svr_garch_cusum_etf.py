"""T11 오토런 — ``uv run python scripts/run_svr_garch_cusum_etf.py [--raw-dir DIR] [--allow-mismatch]``.

원시 시세는 ``--raw-dir`` (또는 환경변수 ``ETF_RAW_DIR``) 에서 읽고, 없으면 FinanceDataReader 로 받는다.
결과표는 ``research/svr_garch_cusum_etf/results/`` 에 쓴다.
"""

import argparse

from r2h.svrgarch_etf import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--allow-mismatch", action="store_true")
    ap.add_argument("--null-sims", type=int, default=100)
    a = ap.parse_args()
    run(a.out, raw_dir=a.raw_dir, allow_mismatch=a.allow_mismatch, null_sims=a.null_sims)
