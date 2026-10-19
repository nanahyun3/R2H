"""노트북 12B 를 새 커널에서 실행하고 실행 기록을 남긴다 (12B-lock-1).

사용: R2H .venv/bin/python scripts/run_t22_notebook.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "12B_KODEX200_CUSUM_시장변수_연환산변동성_정렬비교.ipynb"


def main() -> int:
    run_dir = ROOT / "research/k200_cusum_overlay_12b/evidence"
    run_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("LD_LIBRARY_PATH", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    # 커널 명세의 argv 가 "python" 이므로 PATH 첫 항목을 이 인터프리터로 고정하고 user-site 를 끈다.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONNOUSERSITE"] = "1"
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    start = datetime.now(UTC)
    t0 = time.monotonic()
    path = ROOT / "notebooks" / NAME
    cmd = [sys.executable, "-m", "jupyter", "execute", "--inplace", "--timeout=3600", str(path)]
    print("시작:", NAME, start.isoformat(), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=4000, check=False)
    log = run_dir / "12B_execution.log"
    log.write_text(proc.stdout + "\n[STDERR]\n" + proc.stderr, encoding="utf-8")
    rec = {
        "notebook": NAME,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "start_utc": start.isoformat(),
        "end_utc": datetime.now(UTC).isoformat(),
        "seconds": round(time.monotonic() - t0, 2),
        "returncode": proc.returncode,
        "log": str(log.relative_to(ROOT)),
        "python": sys.executable,
    }
    (run_dir / "execution_record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(rec["status"], "초:", rec["seconds"], "로그:", log, flush=True)
    if proc.returncode:
        print(proc.stderr[-5000:], file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
