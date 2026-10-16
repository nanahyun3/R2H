"""A-3 §2 — base 정책 연간 T: T11 yearly_blocks vs T12 annual_posthoc (같은 계산인지 확인).

실행 (W 루트에서): PYTHONPATH=src <R2H>/.venv/bin/python docs/annual_assurance/scripts/a3_t11_t12_base_check.py
읽기만 한다. 결과는 표준출력에 쓴다.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
y = pd.read_csv(ROOT / "research/svr_garch_cusum_etf/results/yearly_blocks.csv", dtype={"ticker": str})
p = pd.read_csv(ROOT / "research/t12_annual_expanding_v2/results/annual_posthoc.csv", dtype={"ticker": str})
p = p[(p.calibration_method == "asymptotic") & (p.policy == "base")]
m = p.merge(y[y.rtype == "base"], on=["ticker", "year"])
print("rows", len(m))
print("max_rel_diff_T", float(np.nanmax(np.abs(m.annual_T - m["T"]) / m["T"])))
print("n_equal", int((m.n_test_residuals == m.n).sum()))
print("reject_equal", int((m.annual_reject == m.reject_asymptotic).sum()))
print("khat_equal", int((m.khat_argmax_date == m.khat_date).sum()))
print(m.groupby("year").annual_reject.sum().to_string())
