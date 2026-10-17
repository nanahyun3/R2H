"""MC p 값·해상도·다중검정·판정 상태 (계약 §7, D2·D16).

귀무 반복에서 통계량이 NaN (예: E 가 비어 C_Sk 를 못 만든 반복) 이면 '초과하지 않음' 으로 센다 —
통계량을 "C 또는 −∞" 로 정의한 것과 같아 MC 검정의 타당성이 유지된다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

CI_LEVEL = 0.99
MIN_TAIL_COUNT = 10  # 가족 해상도 규칙: B × 가장 엄격한 기준 ≥ 10


@dataclass(frozen=True)
class MCP:
    obs: float
    k: int  # #{null ≥ obs}
    B: int
    p: float  # (1+k)/(B+1)
    ci_low: float  # Clopper–Pearson 99% (k/B)
    ci_high: float
    at_floor: bool  # k == 0 → p 는 '≤ 1/(B+1)' 로만 보고

    def label(self) -> str:
        return f"≤ {self.p:.2g}" if self.at_floor else f"{self.p:.4g}"


def clopper_pearson(k: int, n: int, level: float = CI_LEVEL) -> tuple[float, float]:
    a = 1 - level
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def mc_pvalue(obs: float, null: np.ndarray) -> MCP | None:
    """관측이 NaN 이면 None (NOT_ESTIMABLE)."""
    if not np.isfinite(obs):
        return None
    null = np.asarray(null, float)
    B = null.size
    k = int(np.sum(np.where(np.isfinite(null), null, -np.inf) >= obs))
    lo, hi = clopper_pearson(k, B)
    return MCP(float(obs), k, B, (1 + k) / (B + 1), lo, hi, k == 0)


def decide(m: MCP | None, threshold: float) -> str:
    """단일 결정: 99% 구간이 기준을 포함하면 INSUFFICIENT_MONTE_CARLO."""
    if m is None:
        return "NOT_ESTIMABLE"
    if m.ci_low <= threshold <= m.ci_high:
        return "INSUFFICIENT_MONTE_CARLO"
    return "SIGNIFICANT" if m.p <= threshold else "NOT_SIGNIFICANT"


def family_resolution_ok(B: int, strictest: float) -> bool:
    return B * strictest >= MIN_TAIL_COUNT


def fixed_sequence(stage_status: list[str]) -> list[str]:
    """고정 순서: 첫 비기각(또는 판정 불가) 이후 단계는 확증 지위가 없다 → 'CHAIN_STOPPED:<원 상태>'."""
    out, open_ = [], True
    for s in stage_status:
        if open_:
            out.append(s)
            if s != "SIGNIFICANT_H0B":
                open_ = False
        else:
            out.append(f"CHAIN_STOPPED:{s}")
    return out


def holm(pvals: dict[str, MCP | None], alpha: float, valid: dict[str, bool]) -> dict[str, str]:
    """Holm 단계 하강. 무효 귀무·추정 불가 가설은 순위에서 빼고 상태만 붙인다.

    단계 기준 α/(m−j) 에 대해 99% CI 가 기준을 포함하면 INSUFFICIENT_MONTE_CARLO 로 멈춘다.
    """
    out: dict[str, str] = {}
    live = []
    for h, m in pvals.items():
        if m is None:
            out[h] = "NOT_ESTIMABLE"
        elif not valid[h]:
            out[h] = "NULL_MODEL_INVALID"
        else:
            live.append((m.p, h))
    live.sort()
    mtot = len(live)
    stopped = False
    for j, (_, h) in enumerate(live):
        if stopped:
            out[h] = "NOT_SIGNIFICANT"
            continue
        thr = alpha / (mtot - j)
        d = decide(pvals[h], thr)
        if d == "SIGNIFICANT":
            out[h] = "SIGNIFICANT_H0B"
        else:
            out[h] = d
            stopped = True
    return out


def minp_adjusted(
    obs: dict[str, float], null: np.ndarray, names: list[str], valid: dict[str, bool]
) -> dict[str, float]:
    """Westfall–Young 단일단계 minP (민감도). null: (B, m). 각 반복의 귀무 p 는 다른 반복들 대비 순위로 만든다."""
    cols = [j for j, h in enumerate(names) if valid[h] and np.isfinite(obs[h])]
    X = np.where(np.isfinite(null), null, -np.inf)[:, cols]
    B = X.shape[0]
    # 반복 b 의 귀무 p_j = (1 + #{b' ≠ b : X_b'j ≥ X_bj}) / B  (자기 자신 제외 순위)
    ranks = np.empty_like(X)
    for c in range(X.shape[1]):
        v = X[:, c]
        order = np.sort(v)
        ge = B - np.searchsorted(order, v, side="left")  # 자기 포함 개수
        ranks[:, c] = ge / B
    minp = ranks.min(axis=1)
    out: dict[str, float] = {}
    for c_i, j in enumerate(cols):
        h = names[j]
        k = int(np.sum(X[:, c_i] >= obs[h]))
        p_raw = (1 + k) / (B + 1)
        out[h] = float((1 + np.sum(minp <= p_raw)) / (B + 1))
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(c - h), float(c + h)
