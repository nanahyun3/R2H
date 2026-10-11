"""합성 데이터 end-to-end: 생성 → 검증 → feature → 탐지 → 매칭 → 지표, 두 번 실행해 같은지 확인."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from r2h.evaluation import validate_ground_truth
from r2h.synthetic import InjectedSurge, ground_truth_from_injections, surge_series

ROOT = Path(__file__).resolve().parents[2]


def test_ground_truth_is_built_independently_of_detector():
    surges = [InjectedSurge(300, 10, 0.02), InjectedSurge(700, 10, 0.02)]
    r, cal = surge_series(1000, surges, seed=1)
    gt = validate_ground_truth(ground_truth_from_injections(cal, surges, ticker="SYN"))
    assert gt["event_start"].tolist() == [cal[300], cal[700]]
    assert np.isfinite(r).all()


def test_example_script_runs_and_is_deterministic(tmp_path):
    outs = []
    for k in range(2):
        out = tmp_path / f"run{k}.json"
        subprocess.run(
            [sys.executable, str(ROOT / "examples" / "synthetic_demo.py"), "--out", str(out)], check=True
        )
        outs.append(json.loads(out.read_text()))
    assert outs[0] == outs[1]
    res = outs[0]["results"]
    assert {r["method_id"] for r in res} == {"vol_scaled_threshold", "page_cusum_reference"}
    for r in res:
        assert 0.0 <= r["metrics"]["recall"] <= 1.0
