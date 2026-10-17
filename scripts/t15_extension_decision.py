# ruff: noqa: E402
"""W3-lock-2 사전 연장 규칙 판정 (MC_REPS_FREEZE · 설정 monte_carlo.extension_rule).

주 경로 단계 또는 부분집합 Holm 판정 중 하나라도 INSUFFICIENT_MONTE_CARLO 이면, H0_EVALUATION (DCC) +25,000 반복을
정확히 1회 추가한다. 단 총 wall 시간이 24시간 예산 안일 때만. 결과는 research/joint_cusum_w3/MC_EXTENSION_DECISION.json.

사용: R2H .venv/bin/python scripts/t15_extension_decision.py   (전체 MC 체인 EXIT OK 뒤)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.joint_cusum import analysis as A
from r2h.joint_cusum.pipeline import load_cfg

LOG = ROOT / "outputs/t15/mc/official.log"
OUT = ROOT / "research/joint_cusum_w3/MC_EXTENSION_DECISION.json"


def elapsed_hours() -> float:
    """체인 START 부터 마지막 EXIT OK 까지 wall 시간 (로그 기준)."""
    lines = LOG.read_text(encoding="utf-8").splitlines()
    start = next(ln for ln in lines if ln.startswith("START "))
    end = [ln for ln in lines if ln.startswith("EXIT OK ")][-1]
    fmt = "%Y-%m-%d %H:%M:%S"
    t0 = datetime.strptime(start.split()[1] + " " + start.split()[2], fmt)
    t1 = datetime.strptime(end.split()[2] + " " + end.split()[3], fmt)
    return (t1 - t0).total_seconds() / 3600


def main() -> int:
    cfg = load_cfg()
    obs = A.load_obs(cfg, ROOT)
    val = A.null_validity(obs)
    _, cond_ok = A.conditional_null_check(obs)
    tests = A.test_tables(obs, val, cond_ok)
    st = tests["stage"].status.tolist()
    sb = tests["subset"].status.tolist()
    insufficient = [s for s in st + sb if s == "INSUFFICIENT_MONTE_CARLO"]
    hours = elapsed_hours()
    extra_hours = 25_000 / (74 * 60)  # G2 처리량 분당 74 기준
    need = bool(insufficient)
    allowed = hours + extra_hours <= cfg["monte_carlo"]["max_total_wall_hours"]
    decision = (
        "EXTEND_25000"
        if (need and allowed)
        else ("NOT_NEEDED" if not need else "INSUFFICIENT_BUDGET_NO_EXTENSION")
    )
    rec = {
        "decided_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rule": cfg["monte_carlo"]["extension_rule"],
        "insufficient_decisions": len(insufficient),
        "stage_status": dict(zip(tests["stage"].stage, st, strict=True)),
        "subset_insufficient": int(sum(s == "INSUFFICIENT_MONTE_CARLO" for s in sb)),
        "chain_wall_hours": round(hours, 2),
        "extension_wall_hours_estimate": round(extra_hours, 2),
        "decision": decision,
    }
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
