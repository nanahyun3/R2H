"""10번 산출물 지문 (RELEASE_MANIFEST.json) 생성."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/common_volatility_candidates_10"
NB = ROOT / "notebooks/10_ETF20종_공통고변동성_급변후보구간비교.ipynb"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name != "RELEASE_MANIFEST.json")
    files += [ROOT / "configs/t19_common_vol_candidates_v1.json", ROOT / "configs/t19_common_vol_candidates_v2.json"]
    files += sorted((ROOT / "src/r2h/common_vol").glob("*.py"))
    files += [ROOT / f"scripts/{n}" for n in ("t19_build_notebook.py", "run_t19_notebook.py", "run_t19_pipeline.py", "t19_release_manifest.py", "t19_infographics_light.py")]
    files += [ROOT / "tests/unit/test_common_vol_10.py", ROOT / "configs/t19_model_input_v1.json"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    man = {
        "study_id": "t19_common_volatility_candidates_10",
        "protocol_version": "10-lock-2",
        "design_status": "POST_HOC_EXPLORATORY",
        "base_commit": "172cbb3",
        "contract_commits": ["1ab42bd", "3b183f8", "1dceefa"],
        "parent_commit": head,
        "w4_verdict_unchanged": "VALID_ZERO_INTERVALS",
        "notebook": {"path": str(NB.relative_to(ROOT)), "sha256": sha(NB)},
        "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
    }
    (BASE / "RELEASE_MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("파일", len(man["files"]), "개 지문")


if __name__ == "__main__":
    main()
