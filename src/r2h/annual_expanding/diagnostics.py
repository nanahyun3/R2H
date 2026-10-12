"""V · M · N 축 진단 통계 (PROTOCOL_LOCK L6). numpy/scipy 만 쓴다 (statsmodels 미의존, C-08).

이 함수들은 서술 통계·검정 통계를 계산할 뿐이며, 어느 것도 원인 판정을 하지 않는다.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

ANN = np.sqrt(252.0)


# ── V ────────────────────────────────────────────────────────────────────────────
def annual_rv(r: np.ndarray) -> float:
    """사후 실현 연환산 변동성 √252·sd(r) (%p.a., ddof=1). 유효 2개 미만 → NaN."""
    x = np.asarray(r, float)
    x = x[np.isfinite(x)]
    return float(ANN * np.std(x, ddof=1)) if x.size >= 2 else float("nan")


def prior_quantile(value: float, prior_path: np.ndarray) -> float:
    """value 이하인 사전 관측 비율. 사전 관측 없음 → NaN."""
    p = np.asarray(prior_path, float)
    p = p[np.isfinite(p)]
    if p.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(np.mean(p <= value))


# ── M ────────────────────────────────────────────────────────────────────────────
def forecast_metrics(r: np.ndarray, v: np.ndarray) -> dict[str, Any]:
    """r: 수익률(%), v: 예측분산(%²). 둘 다 같은 날짜 집합 — 호출 측이 eligible 을 고른다."""
    r = np.asarray(r, float)
    v = np.asarray(v, float)
    n = r.size
    if n == 0:
        return {
            "n_eligible": 0,
            "oos_qlike": np.nan,
            "oos_sqproxy_mae": np.nan,
            "oos_sqproxy_rmse": np.nan,
            "mean_sq_standardized_residual": np.nan,
            "var_standardized_residual": np.nan,
            "mean_standardized_residual": np.nan,
        }
    r2 = r**2
    e = r / np.sqrt(v)
    return {
        "n_eligible": int(n),
        "oos_qlike": float(np.mean(np.log(v) + r2 / v)),
        "oos_sqproxy_mae": float(np.mean(np.abs(r2 - v))),
        "oos_sqproxy_rmse": float(np.sqrt(np.mean((r2 - v) ** 2))),
        "mean_sq_standardized_residual": float(np.mean(e**2)),
        "var_standardized_residual": float(np.var(e, ddof=1)) if n > 1 else np.nan,
        "mean_standardized_residual": float(np.mean(e)),
    }


# ── N ────────────────────────────────────────────────────────────────────────────
def acf(x: np.ndarray, lag: int) -> float:
    """표본 자기상관 (평균 제거, 분모 n·γ0 — 표준 ACF 정의)."""
    x = np.asarray(x, float)
    n = x.size
    if n <= lag + 1:
        return float("nan")
    d = x - x.mean()
    g0 = float(np.dot(d, d))
    if g0 <= 0:
        return float("nan")
    return float(np.dot(d[lag:], d[:-lag]) / g0)


def ljung_box(x: np.ndarray, lag: int) -> tuple[float, float]:
    """Ljung–Box Q(lag) 와 χ²(lag) p 값."""
    x = np.asarray(x, float)
    n = x.size
    if n <= lag + 1:
        return float("nan"), float("nan")
    rho = np.array([acf(x, k) for k in range(1, lag + 1)])
    if not np.all(np.isfinite(rho)):
        return float("nan"), float("nan")
    q = float(n * (n + 2) * np.sum(rho**2 / (n - np.arange(1, lag + 1))))
    return q, float(stats.chi2.sf(q, lag))


def arch_lm(e: np.ndarray, lag: int) -> tuple[float, float]:
    """Engle ARCH-LM: e² 를 상수 + lag 개 과거 e² 에 회귀, LM = n_eff·R², χ²(lag)."""
    e2 = np.asarray(e, float) ** 2
    n = e2.size
    if n <= 2 * lag + 2:
        return float("nan"), float("nan")
    y = e2[lag:]
    X = np.column_stack([np.ones(n - lag)] + [e2[lag - k : n - k] for k in range(1, lag + 1)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    tss = float(np.sum((y - y.mean()) ** 2))
    if tss <= 0:
        return float("nan"), float("nan")
    r2 = 1.0 - float(np.sum(resid**2)) / tss
    lm = (n - lag) * r2
    return float(lm), float(stats.chi2.sf(lm, lag))


def residual_stats(e: np.ndarray, cfg: dict) -> dict[str, Any]:
    """유효 잔차(NaN 제거된 시간순 배열) 진단. 결측 위치는 시간 간격이 무시된다는 점을 n_eff 와 함께 기록."""
    x = np.asarray(e, float)
    x = x[np.isfinite(x)]
    d = cfg["diagnostics"]
    out: dict[str, Any] = {"n_eff": int(x.size)}
    if x.size < 30:
        return out | {"status": "NOT_ESTIMABLE"}
    q = np.quantile(x, [0.01, 0.05, 0.5, 0.95, 0.99])
    lb_e = ljung_box(x, d["ljungbox_lag"])
    lb_e2 = ljung_box(x**2, d["ljungbox_lag"])
    arch = arch_lm(x, d["archlm_lag"])
    half = x.size // 2
    m1, m2 = float(np.mean(x[:half] ** 2)), float(np.mean(x[half:] ** 2))
    out.update(
        mean_e=float(x.mean()),
        var_e=float(np.var(x, ddof=1)),
        skew_e=float(stats.skew(x)),
        excess_kurtosis=float(stats.kurtosis(x, fisher=True)),
        q01=float(q[0]),
        q05=float(q[1]),
        q50=float(q[2]),
        q95=float(q[3]),
        q99=float(q[4]),
        tail_freq_abs_gt3=float(np.mean(np.abs(x) > d["tail_abs_threshold"])),
        acf_e_lag1=acf(x, 1),
        **{f"acf_e2_lag{k}": acf(x**2, k) for k in d["acf_lags"]},
        ljungbox_e_stat=lb_e[0],
        ljungbox_e_p=lb_e[1],
        ljungbox_e2_stat=lb_e2[0],
        ljungbox_e2_p=lb_e2[1],
        archlm_stat=arch[0],
        archlm_p=arch[1],
        e2_ratio_h2_over_h1_exploratory=m2 / m1 if m1 > 0 else float("nan"),
    )
    return out


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg q 값. NaN 은 NaN 으로 둔다 (가족 크기 = 유효 p 수)."""
    p = np.asarray(p, float)
    out = np.full(p.shape, np.nan)
    ok = np.isfinite(p)
    m = int(ok.sum())
    if m == 0:
        return out
    pv = p[ok]
    order = np.argsort(pv, kind="mergesort")
    ranked = pv[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    res = np.empty(m)
    res[order] = np.minimum(q, 1.0)
    out[ok] = res
    return out
