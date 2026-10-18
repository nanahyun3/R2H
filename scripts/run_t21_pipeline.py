"""12번 관측 파이프라인 — 원시 통계량 → 귀무표 부착 → 피처 원장(Parquet, Git 제외) → 결과 CSV (Git).

사용: R2H .venv/bin/python scripts/run_t21_pipeline.py [--calib outputs/t21/calib] [--null-tag main_null]
노트북 12 와 같은 함수를 부른다 (두 경로 결과 바이트 동일 확인용).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import report as RP  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", default="outputs/t21/calib")
    ap.add_argument("--null-tag", default="main_null")
    ap.add_argument("--results", default="research/k200_cusum_controlled_12/results")
    a = ap.parse_args()
    out = RP.run(ROOT, ROOT / a.calib, ROOT / "outputs" / "t21" / "mc" / a.null_tag, ROOT / a.results)
    print("결과 CSV", len(out["written"]), "개 · 원장 행", out["ledger_rows"])


if __name__ == "__main__":
    main()
