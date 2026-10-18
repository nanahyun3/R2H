"""12번 합성·귀무 MC — 경로별 SVR 파이프라인 잔차를 outputs/t21/mc/<tag>/ 에 저장 (Git 제외).

사용: R2H .venv/bin/python scripts/run_t21_mc.py --tag pilot --reps-null 100 --reps-hold 0 --reps-scen 20 --workers 12
진행 상황은 <out>/progress.json 에 주기적으로 기록한다 (완료 수 · 경과 · 예상 종료).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import mc as MC  # noqa: E402
from r2h.k200_controlled import synth as S  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reps-null", type=int, default=1000)
    ap.add_argument("--reps-hold", type=int, default=500)
    ap.add_argument("--reps-scen", type=int, default=500)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    cfg = C.load_cfg()
    m = C.load_market(cfg, ROOT)
    g = S.dgp_for(m, cfg)
    out = ROOT / "outputs" / "t21" / "mc" / a.tag
    out.mkdir(parents=True, exist_ok=True)
    seed = cfg["seed"]
    common = (seed, g, m.dates, m.eval_start, "2021-03-02", "2025-09-30", [2020, 2021, 2022, 2023, 2024])
    jobs = [("null_cal", i, "S00_null") for i in range(a.reps_null)]
    jobs += [("null_hold", i, "S00_null") for i in range(a.reps_hold)]
    jobs += [("scen", i, sc) for sc in S.SCENARIOS for i in range(a.reps_scen)]
    (out / "dgp.json").write_text(
        json.dumps({"garch_t_2019": g.__dict__, "n_jobs": len(jobs), "args": vars(a)}, default=str, indent=1),
        encoding="utf-8",
    )
    t0 = time.monotonic()
    start = datetime.now(UTC)
    shard = 100  # 체크포인트 단위 (§2.3): 조각마다 저장, 재실행 시 완료 조각은 건너뜀
    fails, done = [], 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for s0 in range(0, len(jobs), shard):
            sd = out / f"shard_{s0 // shard:04d}"
            if (sd / "DONE").exists():
                done += min(shard, len(jobs) - s0)
                continue
            part = jobs[s0 : s0 + shard]
            futs = {ex.submit(MC.run_path, (st, i, sc, *common)): (st, i, sc) for st, i, sc in part}
            res = []
            for f in as_completed(futs):
                try:
                    res.append(f.result())
                except Exception as err:  # 실패 경로는 성공으로 세지 않는다
                    fails.append({"job": futs[f], "error": repr(err)})
            MC.save_results(res, sd)
            (sd / "DONE").write_text(str(len(res)), encoding="utf-8")
            done += len(part)
            el = time.monotonic() - t0
            eta = start + timedelta(seconds=el / max(1, done) * len(jobs))
            (out / "progress.json").write_text(
                json.dumps({"done": done, "total": len(jobs), "failed": len(fails), "elapsed_s": round(el, 1),
                            "eta_utc": eta.isoformat(), "updated_utc": datetime.now(UTC).isoformat()}, indent=1),
                encoding="utf-8",
            )
    MC.merge_shards(out)
    (out / "failures.json").write_text(json.dumps(fails, default=str, indent=1), encoding="utf-8")
    print("완료", done, "실패", len(fails), "초", round(time.monotonic() - t0, 1))


if __name__ == "__main__":
    main()
