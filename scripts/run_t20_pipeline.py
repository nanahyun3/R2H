"""11번 일괄 실행 (노트북 없이): 구간·바텀업·누적수익률·CUSUM → 그림 전부.

사용: R2H .venv/bin/python scripts/run_t20_pipeline.py — 노트북 경로와 결과·그림 바이트 동일 확인용 두 번째 경로.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.etf_shock import pipeline as P  # noqa: E402
from r2h.etf_shock.figures import Figures11  # noqa: E402


def main() -> None:
    res = P.run(ROOT)
    Figures11(res, ROOT).make_all()
    print("결과", len(P.results_digest(ROOT)), "개 CSV · 구간", len(res["intervals"]))


if __name__ == "__main__":
    main()
