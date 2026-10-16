"""W2 릴리스 매니페스트: 커밋 대상 파일·Git 제외 작업 파일·W1 보호 파일·실행 기록의 SHA256 을 한 JSON 으로 묶는다.

사용: R2H .venv/bin/python scripts/t14_release_manifest.py (05→06→07 실행 직후)
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/multihorizon_w2"
RELEASE_GLOBS = (
    "configs/t14_multihorizon_w2_v1.json",
    "notebooks/0[567]_*.ipynb",
    "src/r2h/multihorizon/*.py",
    "scripts/t14_*.py",
    "scripts/run_t14_notebooks.py",
    "tests/unit/test_multihorizon_w2.py",
    "research/multihorizon_w2/*.md",
    "research/multihorizon_w2/*.csv",
    "research/multihorizon_w2/*.txt",
    "research/multihorizon_w2/results/**/*.csv",
    "research/multihorizon_w2/results/**/*.json",
    "research/multihorizon_w2/results/*.json",
    "research/multihorizon_w2/figures/*",
    "research/multihorizon_w2/evidence/*",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    files = sorted(
        {
            p
            for g in RELEASE_GLOBS
            for p in ROOT.glob(g)
            if p.is_file() and p.name != "W2_RELEASE_MANIFEST.json"
        }
    )
    protected = list(csv.DictReader(open(BASE / "W1_PROTECTED_SHA256.csv", encoding="utf-8")))
    changed = [r["path"] for r in protected if sha(ROOT / r["path"]) != r["sha256_at_7205e91"]]
    final = json.loads((BASE / "results/07_final.json").read_text(encoding="utf-8"))
    work_ok = all(sha(ROOT / k) == v for k, v in final["work_files"].items())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest = {
        "study_id": "t14_multihorizon_w2",
        "protocol_version": "W2-lock-1",
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "base_commit_w1": "7205e91348c38584ecca74ea64e4bbc426730e86",
        "contract_freeze_commit": "1fbdb1d",
        "parent_of_release_commit": head,
        "python": platform.python_version(),
        "w1_protected_files": len(protected),
        "w1_protected_changed": changed,
        "git_excluded_work_files_match_07_final": work_ok,
        "git_excluded_work_files_sha256": final["work_files"],
        "release_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in files},
    }
    (BASE / "W2_RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("릴리스 파일", len(files), "개 · W1 보호 변경", changed, "· 작업 파일 해시 일치", work_ok)
    return 0 if not changed and work_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
