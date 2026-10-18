"""W4 (T18) 계산·그림 일괄 실행 — 결과표·그림·캡션 수치·결과 지문을 쓴다.

사용: R2H .venv/bin/python scripts/run_t18_pipeline.py [--no-figures]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.peer_shock.figures import W4Figures  # noqa: E402
from r2h.peer_shock.pipeline import results_digest, run  # noqa: E402


def main() -> int:
    res = run(ROOT)
    out = ROOT / "research/peer_relative_shock_w4"
    if "--no-figures" not in sys.argv:
        caps = W4Figures(res, ROOT).make_all()
        (out / "results/figure_captions.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1, default=str, sort_keys=True) + "\n", encoding="utf-8")
    (out / "evidence/results_digest.json").write_text(json.dumps(results_digest(ROOT), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res["final"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
