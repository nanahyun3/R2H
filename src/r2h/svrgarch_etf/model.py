"""T11 SVR–GARCH 적합·잔차 — Track B 이식 모듈(``r2h.paper2020``)을 ETF 수익률에 그대로 적용한다.

분할 (시간순, 사전 등록): 앞 70% = 적합 구간 → 그 안을 다시 70% 학습 / 30% 검증 (원문 Step 1–5, grid 27점, MAE 선택)
→ 뒤 30% = 검정 구간. 원문(전체 50/50 → 적합구간 내부 70/30)과 다른 **T11 프로토콜**이다.

잔차 경로
- 정책 A (관측 proxy, 1차): 고정된 ĝ 에 (y²_{t−1}, σ̃²_{t−1}) 를 넣는다 — t 이전 관측만 쓰므로
  경로 전체가 과거 정보만으로 계산된다.
  적합 구간은 in-sample (ĝ 가 그 구간으로 추정됨 = 파라미터 look-ahead), 검정 구간은 out-of-sample.
- 정책 B (재귀 예측, 민감도): 검정 구간에서만 σ̂² 를 재귀로 넣는다 (원문 미명시 — Track B UNRESOLVED).
- 기준선 (모형 없음): ε = r_t / σ_{t−1}(60)  (Track A P1 점수, min_periods 40).
비양수 σ̂² 는 그날 잔차만 NaN (D3).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..paper2020 import (
    ArgmaxTiePolicy,
    DegenerateTauPolicy,
    FeatureScalingPolicy,
    SelectionTiePolicy,
    SVRFitPolicy,
    SVRParameters,
    TestVarianceInputPolicy,
    cusum_squares_test,
)
from ..paper2020.svr_garch import VariancePredictionPolicy, forecast_test_variance, select_and_refit
from ..paper2020.volatility_proxy import BoundaryPolicy

FIT_FRACTION = 0.70
TRAIN_FRACTION_OF_FIT = 0.70
GRID = tuple(
    SVRParameters(C=c, paper_gamma_squared=g2, epsilon=e)
    for c, g2, e in itertools.product((1.0, 10.0, 100.0), (0.1, 0.5, 1.0), (0.1, 0.5, 1.0))
)
M, P, Q = 5, 1, 1


@dataclass(frozen=True)
class EtfFit:
    ticker: str
    dates: pd.DatetimeIndex  # 유효 수익률 날짜 (NaN 제외)
    returns: np.ndarray
    n_fit: int
    n_train: int
    params: SVRParameters
    val_mae: float
    var_a: np.ndarray  # 정책 A σ̂² (index 0 은 lag 없음 → NaN)
    var_b_test: np.ndarray  # 정책 B σ̂² (검정 구간만)
    proxy: np.ndarray  # σ̃²_t (관측 proxy, 전체)

    @property
    def split_date(self) -> pd.Timestamp:
        return self.dates[self.n_fit]

    def residuals(self, policy: str = "A") -> np.ndarray:
        """표준화 잔차. A: 전 구간, B: 적합 구간은 A·검정 구간은 B. 비양수 분산 → NaN."""
        var = self.var_a.copy()
        if policy == "B":
            var[self.n_fit :] = self.var_b_test
        elif policy != "A":
            raise ValueError(policy)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = self.returns / np.sqrt(np.where(var > 0, var, np.nan))
        return out


def fit_etf(ticker: str, returns: pd.Series) -> EtfFit:
    r = returns.dropna()
    y = r.to_numpy(float)
    n_fit = round(FIT_FRACTION * y.size)
    n_train = round(TRAIN_FRACTION_OF_FIT * n_fit)
    fit = select_and_refit(
        y[:n_train],
        y[n_train:n_fit],
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
    # 정책 A 전 구간: RESET 경계로 전체 시계열에 고정 ĝ 적용 (검정 구간 값은 CARRY 프로토콜과 같다 — 아래 검사)
    full = forecast_test_variance(
        fit,
        y,
        m=M,
        p=P,
        q=Q,
        input_policy=TestVarianceInputPolicy.OBSERVED_PROXY,
        proxy_boundary=BoundaryPolicy.RESET,
        lag_boundary=BoundaryPolicy.RESET,
        prediction_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    var_a = np.full(y.size, np.nan)
    var_a[full.test_indices] = full.variance
    test_a = forecast_test_variance(
        fit,
        y[n_fit:],
        m=M,
        p=P,
        q=Q,
        input_policy=TestVarianceInputPolicy.OBSERVED_PROXY,
        proxy_boundary=BoundaryPolicy.CARRY,
        lag_boundary=BoundaryPolicy.CARRY,
        prediction_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    if not np.allclose(test_a.variance, var_a[n_fit:][test_a.test_indices], rtol=1e-12, atol=1e-12):
        raise AssertionError(
            f"{ticker}: whole-series policy A differs from paper CARRY protocol on the test block"
        )
    test_b = forecast_test_variance(
        fit,
        y[n_fit:],
        m=M,
        p=P,
        q=Q,
        input_policy=TestVarianceInputPolicy.RECURSIVE_PREDICTION,
        proxy_boundary=BoundaryPolicy.CARRY,
        lag_boundary=BoundaryPolicy.CARRY,
        prediction_policy=VariancePredictionPolicy.RAW,
        variance_floor=None,
    )
    from ..paper2020.volatility_proxy import moving_square_proxy

    proxy = moving_square_proxy(y, m=M, boundary_policy=BoundaryPolicy.RESET)
    best = min(fit.scores, key=lambda s: s.mae)
    return EtfFit(
        ticker=ticker,
        dates=pd.DatetimeIndex(r.index),
        returns=y,
        n_fit=n_fit,
        n_train=n_train,
        params=fit.best_parameters,
        val_mae=float(best.mae),
        var_a=var_a,
        var_b_test=test_b.variance,
        proxy=proxy,
    )


def baseline_residuals(returns: pd.Series, window: int = 60, min_periods: int = 40) -> pd.Series:
    """모형 없는 기준선 ε = r_t / σ_{t−1}(60). σ = 0 → NaN."""
    sigma = returns.rolling(window, min_periods=min_periods).std(ddof=1).shift(1)
    return returns / sigma.where(sigma > 0)


def fullsample_test(fit: EtfFit, policy: str) -> dict[str, object]:
    """검정 구간(뒤 30%) 사후 CUSUM-of-squares. 비양수 분산일은 제외하고 건수를 기록 (D3)."""
    e = fit.residuals(policy)[fit.n_fit :]
    n_nonpos = int(np.isnan(e).sum())
    out: dict[str, object] = {
        "ticker": fit.ticker,
        "policy": policy,
        "n_test": int(e.size),
        "n_nonpos_var": n_nonpos,
        "test_start": fit.dates[fit.n_fit].date(),
        "test_end": fit.dates[-1].date(),
    }
    # D3: 비양수 분산일은 그날만 빼고 검정한다 (건수는 n_nonpos_var 로 기록)
    keep = np.flatnonzero(np.isfinite(e))
    res = cusum_squares_test(
        e[keep], tie_policy=ArgmaxTiePolicy.FIRST, degenerate_tau_policy=DegenerateTauPolicy.RAISE
    )
    if res.change_index_one_based is None:
        raise ValueError("CUSUM change location undefined")
    out.update(
        status="ok",
        T=res.statistic,
        reject=res.reject,
        khat_date=fit.dates[fit.n_fit + keep[res.change_index_one_based - 1]].date(),
    )
    return out
