"""최종 노트북 00→01→02를 서로 다른 새 커널에서 순차 실행한다.

실행: ``python scripts/run_t12_final_notebooks.py``. 원자료는 ``data/raw``의
고정 파일이며 네트워크 재다운로드를 사용하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = (
    "00_환경과_데이터_검증.ipynb",
    "01_연간확장_실험재현.ipynb",
    "02_가설검증_강건성_심층해석.ipynb",
)


def main() -> int:
    default_jupyter = ROOT.parents[1] / "1012_Annual_SVR–GARCH-CUSUM" / "R2H" / ".venv" / "bin" / "jupyter"
    jupyter = Path(os.environ.get("T12_JUPYTER", str(default_jupyter)))
    if not jupyter.is_file():
        raise FileNotFoundError(f"T12_JUPYTER 실행 파일 없음: {jupyter}")
    if not (ROOT / "data" / "raw" / "MANIFEST.csv").is_file():
        raise FileNotFoundError("data/raw 고정 원자료가 없습니다")
    out = ROOT / "outputs" / "t12" / "final"
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    run_id = os.environ.get("T12_NB_RUN_ID", "final_" + started.strftime("%Y%m%dT%H%M%SZ"))
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("LD_LIBRARY_PATH", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PATH"] = str(jupyter.parent) + os.pathsep + os.defpath
    env["T12_NB_RUN_ID"] = run_id
    env.pop("T12_NB_REUSE_RUN_ID", None)
    report: dict = {"started_utc": started.isoformat(), "run_id": run_id, "notebooks": []}
    log = out / f"{run_id}.log"
    for name in NOTEBOOKS:
        path = ROOT / "notebooks" / name
        t0 = datetime.now(UTC)
        command = [str(jupyter), "execute", "--inplace", "--timeout=3600", str(path)]
        with log.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{t0.isoformat()}] START {name}\n")
            stream.flush()
            process = subprocess.Popen(
                command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                stream.write(line)
            code = process.wait()
            t1 = datetime.now(UTC)
            stream.write(f"[{t1.isoformat()}] END {name} exit={code}\n")
        item = {
            "name": name,
            "started_utc": t0.isoformat(),
            "ended_utc": t1.isoformat(),
            "duration_s": (t1 - t0).total_seconds(),
            "exit_code": code,
        }
        if code == 0:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        report["notebooks"].append(item)
        report["ended_utc"] = t1.isoformat()
        report["status"] = "PASS" if code == 0 and len(report["notebooks"]) == 3 else "FAIL" if code else "IN_PROGRESS"
        (out / f"{run_id}_reproduction_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if code:
            print(f"실패: {name}; 중간 산출물은 발표·배포하지 않습니다.", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
