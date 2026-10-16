"""A-2 Q8 — 2020 vs 2026 기각 차이를 '시장구조' 로 말할 수 있는가: 교란 요인 표.

결과표만 읽는다 (seq_golden 사본) + 독립 MC (n=184 vs 248 의 검정력 차이).
seed: np.random.default_rng([20261016, n, 2]) — 결과를 본 뒤 바꾸지 않는다.

실행: <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a2_2020_vs_2026.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "research" / "t12_annual_expanding_v2" / "results"
C = 1.3397


def cusum_T(x: np.ndarray) -> np.ndarray:
    n = x.shape[1]
    s = x**2
    path = np.cumsum(s, axis=1) - (np.arange(1, n + 1) / n) * s.sum(axis=1, keepdims=True)
    tau2 = (x**4).mean(axis=1) - s.mean(axis=1) ** 2
    return np.abs(path).max(axis=1) / (np.sqrt(n) * np.sqrt(tau2))


def main() -> None:
    ph = pd.read_csv(RES / "annual_posthoc.csv", dtype={"ticker": str})
    ab = pd.read_csv(RES / "annual_history_ablation.csv", dtype={"ticker": str})
    vol = pd.read_csv(RES / "annual_vol_diagnostics.csv", dtype={"ticker": str})
    fm = pd.read_csv(RES / "fold_manifest.csv", dtype={"ticker": str})
    print("## 기각 수 /20 (연간, 방법별)")
    t = ph[ph.year.isin([2020, 2026])].copy()
    t["rej"] = t.annual_reject.map({True: 1, False: 0, "True": 1, "False": 0})
    print(t.pivot_table(index=["calibration_method"], columns=["year", "policy"], values="rej", aggfunc="sum").to_string())
    print("\n## 같은 2019 모형 (frozen_2019) 을 2026 에 적용했을 때 — 2020 fold 와 모형이 같다")
    a = ab[(ab.year == 2026) & (ab.h_status == "COMPUTED")]
    print(a.groupby(["history_strategy", "policy"]).annual_reject_asymptotic.apply(lambda s: int(s.astype(bool).sum())).unstack().to_string())
    print("\n## 표본·이력·변동성")
    e = fm[(fm.history_strategy == "expanding") & fm.year.isin([2020, 2026])]
    print(e.groupby("year")[["n_train_history", "n_test"]].median().to_string())
    v = vol[vol.year.isin([2020, 2026])]
    print(v.groupby("year")[["rv_ann_pct", "rv_ratio", "rv_prior_quantile"]].median().round(3).to_string())
    b = ph[(ph.calibration_method == "asymptotic") & (ph.policy == "base")]
    r20 = set(b[(b.year == 2020) & b.annual_reject.astype(bool)].ticker)
    r26 = set(b[(b.year == 2026) & b.annual_reject.astype(bool)].ticker)
    print(f"base 기각 ETF: 2020 {len(r20)} · 2026 {len(r26)} · 둘 다 {len(r20 & r26)} · 2026 만 {sorted(r26 - r20)}")
    print("\n## n 효과 (독립 MC, iid 정규, 연중 분산 ×k 변화 시점 = n/2, 20,000회)")
    for k in (1.0, 1.5, 2.0):
        out = []
        for n in (184, 248):
            rng = np.random.default_rng([20261016, n, 2])
            x = rng.standard_normal((20000, n))
            x[:, n // 2 :] *= np.sqrt(k)
            out.append(float((cusum_T(x) >= C).mean()))
        print(f"분산×{k}: 거부율 n=184 {out[0]:.3f} · n=248 {out[1]:.3f}")


if __name__ == "__main__":
    main()
