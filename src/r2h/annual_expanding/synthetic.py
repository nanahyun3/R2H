"""합성 DGP 로 검정 타당성 측정 (PROTOCOL_LOCK L8). 정답(변화 유무·시점)은 **생성 과정에서만** 알려진다.

두 층:
1. 검출기 수준 — 표준화 잔차를 직접 생성 → 연간 사후 CUSUM · w60 이동창 (PURE/CARRY) 의 기각/경보 확률.
2. 파이프라인 수준 — 수익률 생성 → 연초 SVR 적합(27 grid) → 정책 A 잔차 → 같은 검정. 반복 수가 적다.

결과는 ``null_dgp_validation.csv`` (Size 는 H0 DGP 에서만, Power/Delay 는 변화 DGP 에서만 정의).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from .calibration import (
    critical_from_draws,
    draws_block,
    draws_iid,
    posthoc,
    rolling_with_context,
    summarize_alarms,
)
from .config import rng_for
from .fit import fit_annual, forecast_year, insample_variance, standardize


@dataclass(frozen=True)
class Scenario:
    """history: 사전 연도 잔차(보정 풀·warm 문맥), test: 검정연도 잔차, break_pos: 변화 시작 (없으면 None)."""

    history: np.ndarray
    test: np.ndarray
    break_pos: int | None


def _garch(n: int, rng: np.random.Generator, omega: float, alpha: float, beta: float) -> np.ndarray:
    h, x = np.empty(n), np.empty(n)
    h[0] = omega / (1 - alpha - beta)
    for t in range(n):
        if t:
            h[t] = omega + alpha * x[t - 1] ** 2 + beta * h[t - 1]
        x[t] = np.sqrt(h[t]) * rng.standard_normal()
    return x / np.sqrt(omega / (1 - alpha - beta))


def _t5(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_t(5, n) / np.sqrt(5 / 3)


DGP = Callable[[np.random.Generator, int, int], Scenario]


def _variance_break(mult: float) -> DGP:
    def f(rng: np.random.Generator, nh: int, n: int) -> Scenario:
        test = rng.standard_normal(n)
        k = n // 2
        test[k:] *= math.sqrt(mult)
        return Scenario(rng.standard_normal(nh), test, k)

    return f


def _stable(scale: float) -> DGP:
    def f(rng: np.random.Generator, nh: int, n: int) -> Scenario:
        return Scenario(rng.standard_normal(nh) * scale, rng.standard_normal(n) * scale, None)

    return f


def _heavy(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    return Scenario(_t5(nh, rng), _t5(n, rng), None)


def _garch_clustering(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    x = _garch(nh + n, rng, 0.05, 0.10, 0.85)
    return Scenario(x[:nh], x[nh:], None)


def _outlier(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    test = rng.standard_normal(n)
    test[n // 2] = 8.0
    return Scenario(rng.standard_normal(nh), test, None)


def _mean_only(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    test = rng.standard_normal(n)
    test[n // 2 :] += 0.5
    return Scenario(rng.standard_normal(nh), test, n // 2)


def _boundary(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    return Scenario(rng.standard_normal(nh), rng.standard_normal(n) * math.sqrt(2.0), 0)


def _equal_rv_constant(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    return Scenario(rng.standard_normal(nh), rng.standard_normal(n) * math.sqrt(2.5), None)


def _equal_rv_break(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    test = rng.standard_normal(n)
    k = n // 2
    test[k:] *= 2.0  # 분산 1 → 4, 연평균 분산 2.5 (위 상수 DGP 와 같은 연간 RV)
    return Scenario(rng.standard_normal(nh), test, k)


def _bias_constant(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    return Scenario(rng.standard_normal(nh), rng.standard_normal(n) * math.sqrt(2.0), None)


def _bias_drift(rng: np.random.Generator, nh: int, n: int) -> Scenario:
    return Scenario(rng.standard_normal(nh), rng.standard_normal(n) * np.sqrt(np.linspace(1.0, 2.0, n)), 0)


DETECTOR_DGPS: dict[str, tuple[DGP, str, str]] = {
    # 이름: (생성기, H0/BREAK, 설명)
    "stable_low_variance_no_change": (_stable(1.0), "H0", "iid N(0,1) history and test"),
    "stable_high_variance_no_change": (
        _stable(3.0),
        "H0",
        "iid N(0,9): high level, no change (negative control)",
    ),
    "stable_heavy_tail": (_heavy, "H0", "iid t5 (unit variance)"),
    "stable_garch_clustering": (_garch_clustering, "H0", "GARCH(1,1) a=.10 b=.85 residuals, no break"),
    "one_outlier_without_persistent_break": (_outlier, "H0", "N(0,1) + one 8-sigma day mid-year"),
    "variance_forecast_bias_constant": (
        _bias_constant,
        "H0",
        "test residual variance x2 all year (model bias)",
    ),
    "equal_yearly_rv_constant": (
        _equal_rv_constant,
        "H0",
        "test variance 2.5 constant (RV matched to break DGP)",
    ),
    "mean_only_break": (_mean_only, "BREAK", "mean +0.5 from mid-year, variance unchanged"),
    "variance_break_x1.5": (_variance_break(1.5), "BREAK", "variance x1.5 from mid-year"),
    "variance_break_x2": (_variance_break(2.0), "BREAK", "variance x2 from mid-year"),
    "variance_break_x3": (_variance_break(3.0), "BREAK", "variance x3 from mid-year"),
    "equal_yearly_rv_within_year_break": (
        _equal_rv_break,
        "BREAK",
        "variance 1 -> 4 mid-year (annual RV = const DGP)",
    ),
    "break_at_year_boundary": (
        _boundary,
        "BREAK_AT_BOUNDARY",
        "variance x2 from first test day (no within-year break)",
    ),
    "variance_forecast_bias_drift": (_bias_drift, "BREAK", "residual variance drifts 1 -> 2 across the year"),
}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def evaluate(sc: Scenario, *, w: int, cfg: dict, key: tuple, asym: float, reps: int) -> dict[str, Any]:
    """한 시나리오: 연간 사후 (점근·iid·block) + w 이동창 (PURE·CARRY, iid 임계값)."""
    q = cfg["calibration"]["pointwise_quantile"]
    gap = cfg["cusum"]["episode_gap_trading_days"]
    ph = posthoc(sc.test)
    n = int(ph["n_test_residuals"])
    c_iid = critical_from_draws(draws_iid(sc.history, n, reps, rng_for(*key, "a_iid")), q)
    c_blk = critical_from_draws(
        draws_block(sc.history, n, reps // 2, cfg["calibration"]["block_length"], rng_for(*key, "a_blk")), q
    )
    c_w = critical_from_draws(draws_iid(sc.history, w, reps, rng_for(*key, "w_iid")), q)
    stat = rolling_with_context(sc.history, sc.test, w)
    pure = np.arange(sc.test.size) >= w - 1
    sp = summarize_alarms(stat, pure, c_w, gap)
    sc_ = summarize_alarms(stat, np.ones(sc.test.size, bool), c_w, gap)
    T = float(ph["annual_T"])
    delay = None
    if sc.break_pos is not None and sp["first_alarm_pos"] is not None:
        after = np.flatnonzero((np.arange(sc.test.size) >= max(sc.break_pos, w - 1)) & pure & (stat >= c_w))
        delay = int(after[0] - sc.break_pos) if after.size else None
    return {
        "annual_T": T,
        "rej_asym": int(T >= asym),
        "rej_iid": int(T >= c_iid),
        "rej_block": int(T >= c_blk),
        "pure_any": int((sp["rolling_episodes"] or 0) > 0),
        "carry_any": int((sc_["rolling_episodes"] or 0) > 0),
        "carry_warm_any": int((summarize_alarms(stat, ~pure, c_w, gap)["rolling_episodes"] or 0) > 0),
        "delay": delay,
    }


def simulate_pipeline_returns(
    kind: str, rng: np.random.Generator, nh: int, n: int
) -> tuple[np.ndarray, int | None]:
    """파이프라인 수준 수익률 (% 단위, 일 변동성 약 1%). GARCH 귀무 / 연중 분산 ×2 / iid 귀무."""
    if kind == "pipeline_iid_normal_H0":
        return rng.standard_normal(nh + n), None
    x = _garch(nh + n, rng, 0.02, 0.08, 0.90)
    if kind == "pipeline_garch_H0":
        return x, None
    if kind == "pipeline_garch_variance_break_x2":
        k = nh + n // 2
        x[k:] *= math.sqrt(2.0)
        return x, n // 2
    raise ValueError(kind)


PIPELINE_DGPS: dict[str, str] = {
    "pipeline_iid_normal_H0": "H0",
    "pipeline_garch_H0": "H0",
    "pipeline_garch_variance_break_x2": "BREAK",
}


def pipeline_rep(kind: str, rep: int, cfg: dict) -> dict[str, Any]:
    """수익률 → 연초 SVR 적합 → A 잔차 (사전 연도 재표준화 풀) → evaluate."""
    syn = cfg["synthetic"]
    nh, n = syn["n_history"], syn["n_year"]
    key = (cfg["study_id"], "pipeline", kind, rep)
    x, brk = simulate_pipeline_returns(kind, rng_for(*key, "dgp"), nh, n)
    hist, test = x[:nh], x[nh:]
    n_tr = round(cfg["folds"]["inner_train_fraction"] * nh)
    af = fit_annual(hist, n_tr)
    e_test = standardize(test, forecast_year(af.fit, hist, test, "A"))
    pool = standardize(hist, insample_variance(af.fit, hist))
    sc = Scenario(pool, e_test, brk)
    out = evaluate(
        sc,
        w=60,
        cfg=cfg,
        key=key,
        asym=cfg["cusum"]["asymptotic_critical_5pct"],
        reps=cfg["calibration"]["iid_reps"] // 5,
    )
    out["nonpos_var_days"] = int(np.sum(~np.isfinite(e_test)))
    return out
