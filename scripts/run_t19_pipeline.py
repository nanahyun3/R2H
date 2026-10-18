"""10번 일괄 실행 (노트북 없이): 09 승계 검증 → 규칙·구간·비교 → 그림 G01–G16.

사용: R2H .venv/bin/python scripts/run_t19_pipeline.py
노트북 경로와 결과·그림이 바이트 동일한지 확인하는 두 번째 경로로 쓴다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.common_vol import pipeline as P  # noqa: E402
from r2h.common_vol.figures import Figures10  # noqa: E402


def main() -> None:
    res = P.run(ROOT)
    Figures10(res, ROOT).make_all()
    print("결과", len(P.results_digest(ROOT)), "개 CSV · 주분석 구간", int((res["intervals"]["period"] == "PRIMARY").sum()))


if __name__ == "__main__":
    main()
