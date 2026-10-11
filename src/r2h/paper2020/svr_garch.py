"""Method-equivalent SVR-GARCH core for Lee, Kim & Lee (2020).

Every choice that the paper leaves unresolved is carried by an explicit policy
object.  In particular there is no default finite hyperparameter grid, boundary
continuation rule, positivity repair, or tie resolution.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from .cusum import NonPositiveVariancePolicy, standardized_residuals
from .volatility_proxy import (
    BoundaryPolicy,
    LaggedDesign,
    build_lagged_design,
    moving_square_proxy,
)


FloatArray = NDArray[np.float64]


class FeatureScalingPolicy(str, Enum):
    """Scaling lanes; e1071's documented default corresponds to X_AND_Y."""

    NONE = "none"
    X_ONLY = "x_only"
    X_AND_Y = "x_and_y"


class VariancePredictionPolicy(str, Enum):
    """Treatment of non-positive SVR outputs while they still represent variance."""

    RAW = "raw"
    RAISE = "raise"
    CLIP = "clip"


class SelectionTiePolicy(str, Enum):
    """The paper does not state how equal validation MAEs are resolved."""

    FIRST = "first"
    RAISE = "raise"


class TestVarianceInputPolicy(str, Enum):
    """How Equation (9)'s lagged variance inputs are formed during testing."""

    OBSERVED_PROXY = "observed_proxy"
    RECURSIVE_PREDICTION = "recursive_prediction"


@dataclass(frozen=True, order=True)
class SVRParameters:
    C: float
    paper_gamma_squared: float
    epsilon: float

    def __post_init__(self) -> None:
        values = (self.C, self.paper_gamma_squared, self.epsilon)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("SVR parameters must be finite")
        if self.C <= 0 or self.paper_gamma_squared <= 0 or self.epsilon < 0:
            raise ValueError("C and paper_gamma_squared must be positive; epsilon nonnegative")

    def is_inside_paper_ranges(self) -> bool:
        return (
            1.0 <= self.C <= 100.0
            and 0.1 <= self.paper_gamma_squared <= 1.0
            and 0.1 <= self.epsilon <= 1.0
        )


@dataclass(frozen=True)
class SVRFitPolicy:
    scaling: FeatureScalingPolicy
    tol: float = 1e-3
    shrinking: bool = True
    cache_size_mb: float = 200.0
    max_iter: int = -1

    def __post_init__(self) -> None:
        if not np.isfinite(self.tol) or self.tol <= 0:
            raise ValueError("tol must be finite and positive")
        if not np.isfinite(self.cache_size_mb) or self.cache_size_mb <= 0:
            raise ValueError("cache_size_mb must be finite and positive")
        if self.max_iter == 0 or self.max_iter < -1:
            raise ValueError("max_iter must be -1 or a positive integer")


class _Predictor(Protocol):
    def predict(self, X: ArrayLike) -> NDArray[np.float64]: ...


@dataclass(frozen=True)
class FittedVarianceModel:
    estimator: _Predictor
    parameters: SVRParameters
    fit_policy: SVRFitPolicy

    def predict_raw(self, X: ArrayLike) -> FloatArray:
        matrix = np.asarray(X, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] == 0:
            raise ValueError("X must be a nonempty two-dimensional matrix")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("X must contain only finite values")
        result = np.asarray(self.estimator.predict(matrix), dtype=float)
        if result.ndim != 1 or not np.all(np.isfinite(result)):
            raise ValueError("SVR returned invalid variance predictions")
        return result

    def predict_variance(
        self,
        X: ArrayLike,
        *,
        policy: VariancePredictionPolicy,
        variance_floor: float | None,
    ) -> FloatArray:
        prediction = self.predict_raw(X)
        invalid = prediction <= 0.0
        if policy is VariancePredictionPolicy.RAW:
            return prediction
        if policy is VariancePredictionPolicy.RAISE:
            if np.any(invalid):
                raise ValueError(
                    "non-positive SVR variance predictions at indices "
                    f"{np.flatnonzero(invalid).tolist()}"
                )
            return prediction
        if policy is VariancePredictionPolicy.CLIP:
            if variance_floor is None or not np.isfinite(variance_floor) or variance_floor <= 0:
                raise ValueError("CLIP requires a finite positive variance_floor")
            return np.maximum(prediction, variance_floor)
        raise ValueError(f"unsupported variance prediction policy: {policy!r}")


@dataclass(frozen=True)
class CandidateScore:
    parameters: SVRParameters
    mae: float
    validation_count: int


@dataclass(frozen=True)
class SVRGARCHFitResult:
    model: FittedVarianceModel
    best_parameters: SVRParameters
    scores: tuple[CandidateScore, ...]
    combined_observations: FloatArray
    combined_proxy: FloatArray


@dataclass(frozen=True)
class TestVarianceForecast:
    variance: FloatArray
    test_indices: NDArray[np.int64]


@dataclass(frozen=True)
class SVRGARCHProtocolSpec:
    """All paper-stated values and unresolved implementation policies."""

    parameter_grid: tuple[SVRParameters, ...]
    fit_policy: SVRFitPolicy
    validation_proxy_boundary: BoundaryPolicy
    validation_lag_boundary: BoundaryPolicy
    validation_variance_policy: VariancePredictionPolicy
    selection_tie_policy: SelectionTiePolicy
    test_variance_input_policy: TestVarianceInputPolicy
    test_proxy_boundary: BoundaryPolicy
    test_lag_boundary: BoundaryPolicy
    residual_nonpositive_policy: NonPositiveVariancePolicy
    variance_floor: float | None
    m: int = 5
    p: int = 1
    q: int = 1

    def __post_init__(self) -> None:
        if not self.parameter_grid:
            raise ValueError("parameter_grid must be explicitly provided and nonempty")
        if len(set(self.parameter_grid)) != len(self.parameter_grid):
            raise ValueError("parameter_grid must not contain duplicate points")
        if self.m <= 0 or self.p < 0 or self.q < 0 or self.p + self.q == 0:
            raise ValueError("require m>0, p>=0, q>=0, and p+q>0")
        clipping = (
            self.validation_variance_policy is VariancePredictionPolicy.CLIP
            or self.residual_nonpositive_policy is NonPositiveVariancePolicy.CLIP
        )
        if clipping and (
            self.variance_floor is None
            or not np.isfinite(self.variance_floor)
            or self.variance_floor <= 0
        ):
            raise ValueError("a finite positive variance_floor is required by CLIP policy")


def paper_gamma_to_sklearn(paper_gamma_squared: float) -> float:
    """Map the paper width to sklearn's RBF exponent coefficient."""

    if not np.isfinite(paper_gamma_squared) or paper_gamma_squared <= 0:
        raise ValueError("paper_gamma_squared must be finite and positive")
    return 1.0 / (2.0 * float(paper_gamma_squared))


def _finite_vector(values: ArrayLike, *, name: str) -> FloatArray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a nonempty one-dimensional array")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _make_estimator(parameters: SVRParameters, policy: SVRFitPolicy) -> _Predictor:
    svr = SVR(
        kernel="rbf",
        C=parameters.C,
        gamma=paper_gamma_to_sklearn(parameters.paper_gamma_squared),
        epsilon=parameters.epsilon,
        tol=policy.tol,
        shrinking=policy.shrinking,
        cache_size=policy.cache_size_mb,
        max_iter=policy.max_iter,
    )
    if policy.scaling is FeatureScalingPolicy.NONE:
        return svr
    x_scaled: _Predictor = Pipeline(
        [("x_scaler", StandardScaler()), ("svr", svr)]
    )
    if policy.scaling is FeatureScalingPolicy.X_ONLY:
        return x_scaled
    if policy.scaling is FeatureScalingPolicy.X_AND_Y:
        return TransformedTargetRegressor(
            regressor=x_scaled,
            transformer=StandardScaler(),
        )
    raise ValueError(f"unsupported scaling policy: {policy.scaling!r}")


def fit_svr_variance(
    X: ArrayLike,
    target_proxy: ArrayLike,
    *,
    parameters: SVRParameters,
    fit_policy: SVRFitPolicy,
) -> FittedVarianceModel:
    matrix = np.asarray(X, dtype=float)
    target = _finite_vector(target_proxy, name="target_proxy")
    if matrix.ndim != 2 or matrix.shape[0] != target.size or matrix.shape[1] == 0:
        raise ValueError("X must be 2-D, nonzero-width, and row-aligned with target_proxy")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("X must contain only finite values")
    estimator = _make_estimator(parameters, fit_policy)
    estimator.fit(matrix, target)  # type: ignore[attr-defined]
    return FittedVarianceModel(estimator, parameters, fit_policy)


def chronological_split(
    observations: ArrayLike, *, train_size: int, validation_size: int
) -> tuple[FloatArray, FloatArray]:
    values = _finite_vector(observations, name="observations")
    if train_size <= 0 or validation_size <= 0:
        raise ValueError("train_size and validation_size must be positive")
    if train_size + validation_size != values.size:
        raise ValueError("train_size + validation_size must equal observations length")
    return values[:train_size].copy(), values[train_size:].copy()


def _validation_design(
    train: FloatArray,
    validation: FloatArray,
    *,
    m: int,
    p: int,
    q: int,
    proxy_boundary: BoundaryPolicy,
    lag_boundary: BoundaryPolicy,
) -> tuple[LaggedDesign, FloatArray, FloatArray]:
    train_proxy = moving_square_proxy(
        train, m=m, boundary_policy=BoundaryPolicy.RESET
    )
    validation_proxy = moving_square_proxy(
        validation,
        m=m,
        boundary_policy=proxy_boundary,
        history=train,
    )
    design = build_lagged_design(
        validation,
        validation_proxy,
        p=p,
        q=q,
        boundary_policy=lag_boundary,
        history_observations=train,
        history_variance_proxy=train_proxy,
    )
    return design, train_proxy, validation_proxy


def select_and_refit(
    train: ArrayLike,
    validation: ArrayLike,
    *,
    parameter_grid: Iterable[SVRParameters],
    fit_policy: SVRFitPolicy,
    m: int,
    p: int,
    q: int,
    validation_proxy_boundary: BoundaryPolicy,
    validation_lag_boundary: BoundaryPolicy,
    validation_variance_policy: VariancePredictionPolicy,
    variance_floor: float | None,
    tie_policy: SelectionTiePolicy,
) -> SVRGARCHFitResult:
    """Apply Procedure Steps 1--5 using an explicitly supplied finite grid."""

    train_y = _finite_vector(train, name="train")
    validation_y = _finite_vector(validation, name="validation")
    candidates = tuple(parameter_grid)
    if not candidates:
        raise ValueError("parameter_grid must be nonempty")
    if len(set(candidates)) != len(candidates):
        raise ValueError("parameter_grid contains duplicate points")

    validation_design, train_proxy, validation_proxy = _validation_design(
        train_y,
        validation_y,
        m=m,
        p=p,
        q=q,
        proxy_boundary=validation_proxy_boundary,
        lag_boundary=validation_lag_boundary,
    )
    train_design = build_lagged_design(
        train_y,
        train_proxy,
        p=p,
        q=q,
        boundary_policy=BoundaryPolicy.RESET,
    )
    if train_design.X.shape[0] == 0 or validation_design.X.shape[0] == 0:
        raise ValueError("train and validation blocks must contain usable lagged rows")

    fitted: list[tuple[CandidateScore, FittedVarianceModel]] = []
    for parameters in candidates:
        model = fit_svr_variance(
            train_design.X,
            train_design.target,
            parameters=parameters,
            fit_policy=fit_policy,
        )
        prediction = model.predict_variance(
            validation_design.X,
            policy=validation_variance_policy,
            variance_floor=variance_floor,
        )
        mae = float(np.mean(np.abs(prediction - validation_design.target)))
        fitted.append(
            (
                CandidateScore(parameters, mae, validation_design.target.size),
                model,
            )
        )

    minimum = min(score.mae for score, _ in fitted)
    tied = [item for item in fitted if np.isclose(item[0].mae, minimum, rtol=0, atol=0)]
    if len(tied) > 1 and tie_policy is SelectionTiePolicy.RAISE:
        raise ValueError(f"validation MAE tie among {[item[0].parameters for item in tied]}")
    if tie_policy not in (SelectionTiePolicy.FIRST, SelectionTiePolicy.RAISE):
        raise ValueError(f"unsupported selection tie policy: {tie_policy!r}")
    best_parameters = tied[0][0].parameters

    combined = np.concatenate((train_y, validation_y))
    combined_proxy = moving_square_proxy(
        combined, m=m, boundary_policy=BoundaryPolicy.RESET
    )
    combined_design = build_lagged_design(
        combined,
        combined_proxy,
        p=p,
        q=q,
        boundary_policy=BoundaryPolicy.RESET,
    )
    final_model = fit_svr_variance(
        combined_design.X,
        combined_design.target,
        parameters=best_parameters,
        fit_policy=fit_policy,
    )
    return SVRGARCHFitResult(
        model=final_model,
        best_parameters=best_parameters,
        scores=tuple(score for score, _ in fitted),
        combined_observations=combined,
        combined_proxy=combined_proxy,
    )


def forecast_test_variance(
    fit: SVRGARCHFitResult,
    test: ArrayLike,
    *,
    m: int,
    p: int,
    q: int,
    input_policy: TestVarianceInputPolicy,
    proxy_boundary: BoundaryPolicy,
    lag_boundary: BoundaryPolicy,
    prediction_policy: VariancePredictionPolicy,
    variance_floor: float | None,
) -> TestVarianceForecast:
    """Forecast the test block under a declared, paper-unresolved update rule."""

    test_y = _finite_vector(test, name="test")
    if input_policy is TestVarianceInputPolicy.OBSERVED_PROXY:
        test_proxy = moving_square_proxy(
            test_y,
            m=m,
            boundary_policy=proxy_boundary,
            history=fit.combined_observations,
        )
        design = build_lagged_design(
            test_y,
            test_proxy,
            p=p,
            q=q,
            boundary_policy=lag_boundary,
            history_observations=fit.combined_observations,
            history_variance_proxy=fit.combined_proxy,
        )
        prediction = fit.model.predict_variance(
            design.X,
            policy=prediction_policy,
            variance_floor=variance_floor,
        )
        return TestVarianceForecast(prediction, design.target_indices)

    if input_policy is TestVarianceInputPolicy.RECURSIVE_PREDICTION:
        if proxy_boundary is not BoundaryPolicy.CARRY or lag_boundary is not BoundaryPolicy.CARRY:
            raise ValueError("recursive testing requires CARRY proxy and lag boundaries")
        y_history = list(map(float, fit.combined_observations))
        variance_history = list(map(float, fit.combined_proxy))
        predictions: list[float] = []
        for observation in test_y:
            if len(y_history) < p or len(variance_history) < q:
                raise ValueError("insufficient history for recursive test features")
            y_lags = np.square(y_history[-p:]) if p else np.empty(0)
            variance_lags = np.asarray(variance_history[-q:], dtype=float) if q else np.empty(0)
            X = np.concatenate((y_lags, variance_lags)).reshape(1, -1)
            prediction = float(
                fit.model.predict_variance(
                    X,
                    policy=prediction_policy,
                    variance_floor=variance_floor,
                )[0]
            )
            predictions.append(prediction)
            y_history.append(float(observation))
            variance_history.append(prediction)
        return TestVarianceForecast(
            np.asarray(predictions, dtype=float),
            np.arange(test_y.size, dtype=np.int64),
        )

    raise ValueError(f"unsupported test input policy: {input_policy!r}")


def estimate_svr_garch_residuals(
    train: ArrayLike,
    validation: ArrayLike,
    test: ArrayLike,
    *,
    spec: SVRGARCHProtocolSpec,
    seed: int,
) -> FloatArray:
    """High-level simulation adapter returning standardized test residuals.

    ``seed`` is accepted for injection compatibility and validated, but libsvm
    SVR is deterministic for this configuration and consumes no RNG state.
    """

    if not isinstance(seed, (int, np.integer)) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    fit = select_and_refit(
        train,
        validation,
        parameter_grid=spec.parameter_grid,
        fit_policy=spec.fit_policy,
        m=spec.m,
        p=spec.p,
        q=spec.q,
        validation_proxy_boundary=spec.validation_proxy_boundary,
        validation_lag_boundary=spec.validation_lag_boundary,
        validation_variance_policy=spec.validation_variance_policy,
        variance_floor=spec.variance_floor,
        tie_policy=spec.selection_tie_policy,
    )
    forecast = forecast_test_variance(
        fit,
        test,
        m=spec.m,
        p=spec.p,
        q=spec.q,
        input_policy=spec.test_variance_input_policy,
        proxy_boundary=spec.test_proxy_boundary,
        lag_boundary=spec.test_lag_boundary,
        prediction_policy=(
            VariancePredictionPolicy.CLIP
            if spec.residual_nonpositive_policy is NonPositiveVariancePolicy.CLIP
            else VariancePredictionPolicy.RAISE
        ),
        variance_floor=spec.variance_floor,
    )
    test_y = _finite_vector(test, name="test")
    selected_y = test_y[forecast.test_indices]
    residuals = standardized_residuals(
        selected_y,
        forecast.variance,
        nonpositive_policy=spec.residual_nonpositive_policy,
        variance_floor=spec.variance_floor,
    )
    if residuals.size != test_y.size:
        raise ValueError(
            "simulation residual adapter requires one residual per test observation; "
            "choose CARRY test lag boundaries or use forecast_test_variance directly"
        )
    return residuals


def make_residual_estimator(
    spec: SVRGARCHProtocolSpec,
) -> Callable[[ArrayLike, ArrayLike, ArrayLike], FloatArray]:
    """Bind a protocol spec and return a simulation-injection compatible callable."""

    def residual_estimator(
        train: ArrayLike,
        validation: ArrayLike,
        test: ArrayLike,
        *,
        seed: int,
    ) -> FloatArray:
        return estimate_svr_garch_residuals(
            train, validation, test, spec=spec, seed=seed
        )

    return residual_estimator

