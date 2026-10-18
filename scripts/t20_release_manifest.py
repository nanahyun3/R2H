"""11번 산출물 지문 (RELEASE_MANIFEST.json) 생성."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/etf_shock_bottomup_11"
NB = ROOT / "notebooks/11_대표6종ETF_개별급변구간_바텀업_누적수익률_CUSUM.ipynb"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name != "RELEASE_MANIFEST.json")
    files += [ROOT / "configs/t20_etf_shock_bottomup_v1.json", ROOT / "tests/unit/test_etf_shock_11.py"]
    files += sorted((ROOT / "src/r2h/etf_shock").glob("*.py"))
    files += [ROOT / f"scripts/{n}" for n in ("t20_build_notebook.py", "run_t20_notebook.py", "run_t20_pipeline.py", "t20_release_manifest.py")]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    man = {"study_id": "t20_etf_shock_bottomup_11", "protocol_version": "11-lock-1", "design_status": "DESCRIPTIVE_EXPLORATORY",
           "base_commit": "20f19fb", "contract_commit": "b7c3197", "parent_commit": head,
           "notebook": {"path": str(NB.relative_to(ROOT)), "sha256": sha(NB)},
           "files": {str(p.relative_to(ROOT)): sha(p) for p in files}}
    (BASE / "RELEASE_MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("파일", len(man["files"]), "개 지문")


if __name__ == "__main__":
    main()
