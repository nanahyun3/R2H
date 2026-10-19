"""12B 릴리스 — 산출물 지문 · G0 (12번 보호) · 단위 시험 · 재현성 기록 → RELEASE_MANIFEST.json.

재현성: 노트북 경로(run_t22_notebook)로 다시 계산한 결과·그림이 커밋된 스크립트 경로 결과와 바이트 동일한지 git 으로 확인한다.
사용: PYTHONNOUSERSITE=1 <R2H .venv>/bin/python scripts/t22_release.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/k200_cusum_overlay_12b"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main() -> int:
    prot = [ln.split(maxsplit=1) for ln in (BASE / "evidence/PROTECTED_12_SHA256.txt").read_text().splitlines()]
    bad = [p for h, p in prot if sha(ROOT / p) != h]
    inputs = [ln.split(maxsplit=1) for ln in (BASE / "evidence/INPUT_SHA256.txt").read_text().splitlines()]
    bad_in = [p for h, p in inputs if sha(ROOT / p) != h]
    env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONNOUSERSITE": "1", "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin"}
    t = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/unit/test_k200_overlay_align.py", "tests/unit/test_k200_overlay_compare.py",
                        "tests/unit/test_k200_overlay_response.py"], cwd=ROOT, capture_output=True, text=True, env=env)
    (BASE / "evidence/test_results.txt").write_text(t.stdout[-3000:], encoding="utf-8")
    # 노트북 실행 뒤 추적 산출물이 커밋본과 같은지 (results·figures·evidence 의 계산 파일)
    tracked_changed = [ln for ln in git("status", "--porcelain", "--", "research/k200_cusum_overlay_12b/results", "research/k200_cusum_overlay_12b/figures").splitlines() if ln.strip()]
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name != "RELEASE_MANIFEST.json")
    files += [ROOT / "notebooks/12B_KODEX200_CUSUM_시장변수_연환산변동성_정렬비교.ipynb", ROOT / "configs/t22_k200_overlay_v1.json"]
    files += sorted((ROOT / "src/r2h/k200_overlay").glob("*.py")) + sorted((ROOT / "scripts").glob("*t22*.py"))
    outputs = sorted((ROOT / "outputs/t22").glob("*.parquet"))
    rec = json.loads((BASE / "evidence/execution_record.json").read_text(encoding="utf-8"))
    man = {
        "study": "12B", "contract": "12B-lock-1", "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "base_commit_12": "c8998a6a3e9f70dbc18675d8a4b67c0999a0e03b", "head_before_release": git("rev-parse", "HEAD").strip(),
        "G0_protected_12_files": len(prot), "G0_changed": bad, "inputs_changed": bad_in,
        "tests": t.stdout.strip().splitlines()[-1] if t.stdout.strip() else t.stderr[-200:],
        "notebook_execution": {k: rec[k] for k in ("status", "seconds", "start_utc")},
        "reproducibility_notebook_vs_script": "BYTE_IDENTICAL" if not tracked_changed else tracked_changed,
        "git_tracked_files": {str(p.relative_to(ROOT)): sha(p) for p in files},
        "local_outputs_git_excluded": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in outputs},
        "lfs_or_external_storage": "none",
    }
    (BASE / "RELEASE_MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (BASE / "evidence/reproducibility.json").write_text(json.dumps({"notebook_vs_script": man["reproducibility_notebook_vs_script"], "notebook": man["notebook_execution"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in man.items() if k not in ("git_tracked_files", "local_outputs_git_excluded")}, ensure_ascii=False, indent=1))
    ok = not bad and not bad_in and t.returncode == 0 and not tracked_changed and rec["status"] == "PASS"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
