"""최종 3개 노트북, 원자료, 코드, 재계산 표, 그림의 SHA256 매니페스트 생성."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "t12_annual_expanding_v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    pointer = json.loads((ROOT / "outputs/t12/latest_repro.json").read_text())
    if pointer["mode"] != "EXECUTED":
        raise RuntimeError("새 01 full 실행의 완료 기록이 아닙니다")
    run_id = pointer["run_id"]
    result_dir = ROOT / "outputs/t12/notebook" / run_id / "results"
    figure_dir = ROOT / "outputs/t12/notebook" / run_id / "presentation"
    merged = ROOT / "outputs/t12/work" / run_id / "merged"
    if not (merged / "run_manifest.json").is_file():
        raise FileNotFoundError("완료된 01 병합 manifest가 없습니다")
    files: dict[str, str] = {}
    roots = [
        ROOT / "notebooks", ROOT / "data/raw", ROOT / "src/r2h/annual_expanding",
        ROOT / "src/r2h/paper2020", ROOT / "src/r2h/svrgarch_etf", ROOT / "scripts",
        result_dir, figure_dir, RESEARCH / "presentation",
    ]
    for folder in roots:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix not in (".pyc",):
                files[str(path.relative_to(ROOT))] = sha(path)
    for name in (
        "uv.lock", "configs/t12_annual_expanding_v2.json",
        "research/t12_annual_expanding_v2/PROTOCOL_LOCK.md",
        "research/t12_annual_expanding_v2/FINAL_REPRODUCTION_REPORT.md",
        ".gitattributes", "README.md", "FINAL_RESEARCH_CLOSURE.md", "HANDOVER_STATE.md",
    ):
        path = ROOT / name
        files[name] = sha(path)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "git_head_before_release_commit": head,
        "semantic": pointer["semantic"],
        "verdict": pointer["verdict"],
        "source_data_rule": "data/raw symlink target is read-only reference; each input file content hashed",
        "files_sha256": files,
    }
    out = RESEARCH / "FINAL_RELEASE_MANIFEST.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(files)} files → {out} · run={run_id} · Semantic/Verdict 지문 기록")


if __name__ == "__main__":
    main()
