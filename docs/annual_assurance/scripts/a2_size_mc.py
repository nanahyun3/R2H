"""A-2 Q4 — 1.3397 의 유한표본 size 와 점근 근거 (독립 구현, r2h 미사용).

T = max_k |Σ_{s≤k} e² − (k/n)Σe²| / (√n·τ̂), τ̂² = mean(e⁴) − mean(e²)²
- 귀무 DGP: iid N(0,1), iid t5 (단위분산), GARCH(1,1) 군집 (모형이 군집을 못 잡은 잔차)
- n: 실제 검정연도 길이 184 · 242 · 245 · 248 와 대표본 1000 · 5000
- seed: np.random.default_rng([20261016, n, dgp_id]) — 결과를 본 뒤 바꾸지 않는다

실행: <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a2_size_mc.py > docs/annual_assurance/out/a2_size_mc.txt
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import kolmogorov
from scipy.stats import kstwobign

C_PAPER = 1.3397


def cusum_T(x: np.ndarray) -> np.ndarray:
    """행 = 표본. 독립 구현."""
    n = x.shape[1]
    s = x**2
    path = np.cumsum(s, axis=1) - (np.arange(1, n + 1) / n) * s.sum(axis=1, keepdims=True)
    tau2 = (x**4).mean(axis=1) - (s.mean(axis=1)) ** 2
    return np.abs(path).max(axis=1) / (np.sqrt(n) * np.sqrt(tau2))


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def garch(reps: int, n: int, rng: np.random.Generator, a=0.10, b=0.85, burn=200) -> np.ndarray:
    om = 1 - a - b
    h = np.full(reps, 1.0)
    x = np.empty((reps, n + burn))
    z = rng.standard_normal((reps, n + burn))
    prev = np.zeros(reps)
    for t in range(n + burn):
        h = om + a * prev**2 + b * h
        prev = np.sqrt(h) * z[:, t]
        x[:, t] = prev
    return x[:, burn:]


def main() -> None:
    print(f"Kolmogorov: P(sup|B|>1.3397) = {kolmogorov(C_PAPER):.4f} ; exact asymptotic q95 = {kstwobign.ppf(0.95):.4f}")
    print("dgp n reps size@1.3397 [wilson95] size@1.3581 q95_finite")
    dgps = {
        "iid_normal": lambda rng, r, n: rng.standard_normal((r, n)),
        "iid_t5": lambda rng, r, n: rng.standard_t(5, (r, n)) / math.sqrt(5 / 3),
        "garch_a.10_b.85": lambda rng, r, n: garch(r, n, rng),
    }
    plan = [(d, n) for d in ("iid_normal",) for n in (184, 242, 245, 248, 1000, 5000)]
    plan += [("iid_t5", 245), ("iid_t5", 184), ("garch_a.10_b.85", 245), ("garch_a.10_b.85", 184)]
    for i, (d, n) in enumerate(plan):
        reps = 20000 if n <= 1000 else 4000
        rng = np.random.default_rng([20261016, n, list(dgps).index(d)])
        T = cusum_T(dgps[d](rng, reps, n))
        k = int((T >= C_PAPER).sum())
        lo, hi = wilson(k, reps)
        print(
            f"{d} {n} {reps} {k / reps:.4f} [{lo:.4f},{hi:.4f}] "
            f"{float((T >= kstwobign.ppf(0.95)).mean()):.4f} {float(np.quantile(T, 0.95)):.4f}"
        )


if __name__ == "__main__":
    main()
