"""W3 릴리스 매니페스트: 계약·설정·코드·노트북·결과·그림·근거의 SHA256 (Git 포함 파일만)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBS = [
    "configs/t15_joint_cusum_w3_v1.json",
    "configs/t15_joint_cusum_w3_v2.json",
    "src/r2h/joint_cusum",
    "scripts/run_t15_mc.py",
    "scripts/t15_build_notebook.py",
    "scripts/run_t15_notebook.py",
    "scripts/t15_extension_decision.py",
    "scripts/t15_write_interpretation.py",
    "scripts/t15_release_manifest.py",
    "tests/unit/test_joint_cusum_w3.py",
    "notebooks/08_대표6종ETF_공동CUSUM_바텀업통계식별.ipynb",
    "research/joint_cusum_w3",
]


def main() -> None:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", *GLOBS],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    paths = sorted(
        p for p in out.stdout.decode().split("\0") if p and not p.endswith("W3_RELEASE_MANIFEST.json")
    )
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    mc = json.loads((ROOT / "outputs/t15/mc/inference_meta.json").read_text())
    rec = {
        "research_id": "R2H_W3_JOINT_CUSUM_08",
        "protocol": "W3-lock-2",
        "contract_commits": {"lock1": "9cdeccb", "lock2": "955d126"},
        "mc_completed_at": mc["completed_at"],
        "mc_outputs_git_excluded_sha256": mc["files"],
        "files": files,
    }
    (ROOT / "research/joint_cusum_w3/W3_RELEASE_MANIFEST.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("manifest", len(files), "files")


if __name__ == "__main__":
    main()
