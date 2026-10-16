"""05→06→07 을 독립 커널에서 순차 재실행하고 단계별 로그를 남긴다.

사용: R2H .venv/bin/python scripts/run_t14_notebooks.py
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
NOTEBOOKS = (
    "05_개별ETF_다중기간_변동성국면연구.ipynb",
    "06_노출군집_공통변동성구간_연구.ipynb",
    "07_가격반응_ETF상대움직임_CNN인계.ipynb",
)
T12_FROZEN = ROOT.parents[1] / "1016" / "R2H_T12_Final"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", choices=("05", "06", "07"), help="해당 노트북만 실행 (뒤 단계는 앞 단계 결과 필요)"
    )
    args = parser.parse_args()
    names = [
        name
        for name in NOTEBOOKS
        if (not args.only or name.startswith(args.only)) and (ROOT / "notebooks" / name).is_file()
    ]
    run_dir = ROOT / "research/multihorizon_w2/evidence"
    run_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("LD_LIBRARY_PATH", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    # 커널 명세의 argv 가 "python" 이므로 PATH 첫 항목을 이 인터프리터로 고정하고 user-site 를 끈다.
    # (2026-10-16 Codex 실행은 user-site 의 numpy 2.5.0/pandas 3.0.3 커널로 돌았다.)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONNOUSERSITE"] = "1"
    env["T12_FROZEN_ROOT"] = str(T12_FROZEN)  # 계약 §1: 새 위치에서는 형제 기본 경로가 없으므로 명시
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
