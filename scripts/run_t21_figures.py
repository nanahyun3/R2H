"""12번 그림 일괄 생성 — 관측 파이프라인을 다시 돌려(결정적) 결과 dict 로 F01–F12 를 그린다.

사용: R2H .venv/bin/python scripts/run_t21_figures.py  →  research/k200_cusum_controlled_12/figures/ (PNG 320dpi + SVG)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import figures as F  # noqa: E402
from r2h.k200_controlled import report as RP  # noqa: E402


def main() -> None:
    res = ROOT / "research/k200_cusum_controlled_12/results"
    out = RP.run(ROOT, ROOT / "outputs/t21/calib_n1", ROOT / "outputs/t21/mc/n1_null", res)
    caps = F.Figures12(out, ROOT).make_all()
    (res / "figure_captions.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1, default=str, sort_keys=True) + "\n", encoding="utf-8")
    print("그림", len(caps), "종")


if __name__ == "__main__":
    main()
