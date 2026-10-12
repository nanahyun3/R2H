"""연초 SVR 분산모형 적합 · 검정연도 분산 예측 (PROTOCOL_LOCK L1–L3).

T11 ``fit_etf`` 의 70:30 전체 분할은 쓰지 않는다. Track B 원본 함수(``select_and_refit``,
``forecast_test_variance``)를 수정 없이 호출하고, 경계·선택 정책은 T11 과 같게 둔다.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..paper2020 import SVRFitPolicy
from ..paper2020.svr_garch import (
    FeatureScalingPolicy,
    SelectionTiePolicy,
    SVRGARCHFitResult,
    TestVarianceInputPolicy,
    VariancePredictionPolicy,
    forecast_test_variance,
    select_and_refit,
)
from ..paper2020.volatility_proxy import BoundaryPolicy, moving_square_proxy
from ..svrgarch_etf.model import GRID, M, P, Q
from .config import array_hash


@dataclass(frozen=True)
class AnnualFit:
    fit: SVRGARCHFitResult
    n_history: int
    n_inner_train: int
    n_inner_val: int
    val_mae: float
    history_hash: str
    model_hash: str

    @property
    def params(self) -> tuple[float, float, float]:
        p = self.fit.best_parameters
        return (p.C, p.paper_gamma_squared, p.epsilon)


def fit_annual(history: np.ndarray, n_inner_train: int) -> AnnualFit:
    """history: 학습 표본 (유효값, 시간순). 앞 n_inner_train 학습 · 나머지 검증 → grid 선택 → 전체 재적합."""
    y = np.asarray(history, float)
    if not np.all(np.isfinite(y)):
        raise ValueError("history must be finite")
    if not 0 < n_inner_train < y.size:
        raise ValueError("invalid inner split")
    fit = select_and_refit(
        y[:n_inner_train],
        y[n_inner_train:],
        parameter_grid=GRID,
        fit_policy=SVRFitPolicy(scaling=FeatureScalingPolicy.X_AND_Y),
        m=M,
        p=P,
        q=Q,
        validation_proxy_boundary=BoundaryPolicy.CARRY,
        validation_lag_boundary=BoundaryPolicy.CARRY,
        validation_variance_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
        tie_policy=SelectionTiePolicy.FIRST,
    )
    best = next(s for s in fit.scores if s.parameters == fit.best_parameters)
    h = array_hash(y)
    p = fit.best_parameters
    model_hash = hashlib.sha256(
        f"{h}|{n_inner_train}|{p.C}|{p.paper_gamma_squared}|{p.epsilon}".encode()
    ).hexdigest()[:16]
    return AnnualFit(
        fit=fit,
        n_history=y.size,
        n_inner_train=n_inner_train,
        n_inner_val=y.size - n_inner_train,
        val_mae=float(best.mae),
        history_hash=h,
        model_hash=model_hash,
    )


def with_context(fit: SVRGARCHFitResult, context: np.ndarray) -> SVRGARCHFitResult:
    """특징 문맥만 실제 직전 관측 경로로 교체 (모형 파라미터·scaler 불변, L2/C-06)."""
    ctx = np.asarray(context, float)
    return dataclasses.replace(
        fit,
        combined_observations=ctx,
        combined_proxy=moving_square_proxy(ctx, m=M, boundary_policy=BoundaryPolicy.RESET),
    )


def forecast_year(fit: SVRGARCHFitResult, context: np.ndarray, test: np.ndarray, policy: str) -> np.ndarray:
    """검정연도 예측분산 σ̂²_{t|t−1} (RAW, 비양수 허용). context = 검정연도 이전 유효 관측 전체."""
    f = with_context(fit, context)
    t = np.asarray(test, float)
    if policy == "A":
        pol = TestVarianceInputPolicy.OBSERVED_PROXY
    elif policy == "B":
        pol = TestVarianceInputPolicy.RECURSIVE_PREDICTION
    else:
        raise ValueError(policy)
    out = forecast_test_variance(
        f,
        t,
        m=M,
        p=P,
        q=Q,
        input_policy=pol,
        proxy_boundary=BoundaryPolicy.CARRY,
        lag_boundary=BoundaryPolicy.CARRY,
        prediction_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    if out.variance.size != t.size:
        raise AssertionError("CARRY forecast must cover every test day")
    return np.asarray(out.variance, float)


def insample_variance(fit: SVRGARCHFitResult, context: np.ndarray) -> np.ndarray:
    """model_y 를 사전 연도 경로 전체에 RESET 으로 적용한 재표준화용 σ̂² (index 0 = NaN). PREYEAR_RESTANDARDIZED."""
    ctx = np.asarray(context, float)
    out = forecast_test_variance(
        fit,
        ctx,
        m=M,
        p=P,
        q=Q,
        input_policy=TestVarianceInputPolicy.OBSERVED_PROXY,
        proxy_boundary=BoundaryPolicy.RESET,
        lag_boundary=BoundaryPolicy.RESET,
        prediction_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    v = np.full(ctx.size, np.nan)
    v[out.test_indices] = out.variance
    return v


def standardize(r: np.ndarray, var: np.ndarray) -> np.ndarray:
    """e = r/√v̂, 비양수·비유한 v̂ → NaN (T11 D3)."""
    v = np.asarray(var, float)
    ok = np.isfinite(v) & (v > 0)
    out = np.full(v.shape, np.nan)
    out[ok] = np.asarray(r, float)[ok] / np.sqrt(v[ok])
    return out


def baseline_variance(returns: pd.Series, window: int = 60, min_periods: int = 40) -> pd.Series:
    """기준선 σ²_{t−1}(60) — T11 ``baseline_residuals`` 와 같은 σ (ddof=1, shift 1)."""
    sigma = returns.rolling(window, min_periods=min_periods).std(ddof=1).shift(1)
    return (sigma.where(sigma > 0)) ** 2
