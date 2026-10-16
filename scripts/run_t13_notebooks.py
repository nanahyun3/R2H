"""03→04를 독립 커널에서 순차 재실행하고 단계별 로그를 남긴다.

사용: R2H .venv/bin/python scripts/run_t13_notebooks.py
실패 노트북은 nbconvert가 원본 실행 출력을 덮지 않으며, 로그에 원인을 남긴다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ("03_대표4종_검정창선정_심층연구.ipynb", "04_전체20종_검정창일반화_강건성연구.ipynb")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("03", "04"), help="해당 노트북만 실행 (04는 완료된 03 필요)")
    args = parser.parse_args()
    names = [name for name in NOTEBOOKS if not args.only or name.startswith(args.only)]
    run_dir = ROOT / "research/window_study_w1/evidence"
    run_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("LD_LIBRARY_PATH", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    # 커널 명세의 argv 가 "python" 이므로 PATH 첫 항목을 이 인터프리터로 고정하고 user-site 를 끈다.
    # (2026-10-16 Codex 실행은 user-site 의 numpy 2.5.0/pandas 3.0.3 커널로 돌았다.)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONNOUSERSITE"] = "1"
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    record: list[dict] = []
    for name in names:
        start = datetime.now(UTC)
        t0 = time.monotonic()
        path = ROOT / "notebooks" / name
        cmd = [sys.executable, "-m", "jupyter", "execute", "--inplace", "--timeout=7200", str(path)]
        print("시작:", name, start.isoformat(), flush=True)
        proc = subprocess.run(
            cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=7500, check=False
        )
        log = run_dir / f"{name[:2]}_execution.log"
        log.write_text(proc.stdout + "\n[STDERR]\n" + proc.stderr, encoding="utf-8")
        status = "PASS" if proc.returncode == 0 else "FAIL"
        record.append(
            {
                "notebook": name,
                "status": status,
                "start_utc": start.isoformat(),
                "end_utc": datetime.now(UTC).isoformat(),
                "seconds": round(time.monotonic() - t0, 2),
                "returncode": proc.returncode,
                "log": str(log.relative_to(ROOT)),
                "command": cmd,
            }
        )
        (run_dir / "execution_record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(status, name, "초:", record[-1]["seconds"], "로그:", log, flush=True)
        if proc.returncode:
            print(proc.stderr[-5000:], file=sys.stderr)
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
