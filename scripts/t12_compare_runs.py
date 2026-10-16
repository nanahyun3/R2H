"""T12 병렬 재현 동치 검사 (G6) — ``uv run python scripts/t12_compare_runs.py --ref seq_golden --runs par2 par4 par4_rerun``.

각 run 의 ``merged/`` 결과표를 기준 run 과 비교: 행 수 · 표별 sha256 · aggregate hash · 수치 최대 차이.
허용 오차는 0 (바이트 동일) — 다르면 FAIL 로 적고 원인을 조사한다 (무조건 PASS 금지, 명세 §5-7).
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from r2h.annual_expanding.config import REPO_ROOT, load_config
from r2h.annual_expanding.pipeline import TABLES, numeric_max_diff

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = load_config()
    work = REPO_ROOT / cfg["release"]["work_dir"]
    rows = []
    ref_m = json.loads((work / a.ref / "merged" / "run_manifest.json").read_text())
    for run in [a.ref, *a.runs]:
        m = json.loads((work / run / "merged" / "run_manifest.json").read_text())
        counts = {t: sum(1 for _ in open(work / run / "merged" / f"{t}.csv", encoding="utf-8")) - 1 for t in (*TABLES, "diagnostic_profile")}
        same = m["outputs_sha256"] == ref_m["outputs_sha256"]
        diff = 0.0 if run == a.ref else numeric_max_diff(work / a.ref / "merged", work / run / "merged")
        mism = [k for k in m["outputs_sha256"] if m["outputs_sha256"][k] != ref_m["outputs_sha256"].get(k)]
        rows.append(
            {
                "mode": "sequential" if m["n_workers"] == 1 else f"parallel_{m['n_workers']}",
                "n_workers": m["n_workers"],
                "run_id": run,
                "config_hash": m["config_hash"],
                "data_hash": m["data_version"],
                "code_sha": m["code_sha"],
                "git_sha": m["git_sha"],
                "row_counts": ";".join(f"{k}={v}" for k, v in counts.items()),
                "aggregate_hash": m["aggregate_hash"],
                "numeric_max_diff": diff,
                "hash_match": same,
                "mismatched_tables": ";".join(mism),
                "integrity_pass": m["integrity_pass"],
                "runtime_seconds": m["runtime_seconds_excluded_from_hash"],
                "status": "REFERENCE" if run == a.ref else ("PASS_BYTE_IDENTICAL" if same and m["integrity_pass"] else "FAIL"),
            }
        )
    df = pd.DataFrame(rows)
    out = Path(a.out) if a.out else work / "parallel_reproducibility.csv"
    df.to_csv(out, index=False, lineterminator="\n")
    print(df[["run_id", "mode", "aggregate_hash", "hash_match", "numeric_max_diff", "runtime_seconds", "status"]].to_string())
