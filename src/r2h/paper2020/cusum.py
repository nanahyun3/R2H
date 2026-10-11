"""Retrospective CUSUM-of-squares test from Lee et al. (2020), Section 3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
PAPER_CRITICAL_VALUE_5_PERCENT = 1.3397


class NonPositiveVariancePolicy(str, Enum):
    """Explicit handling for an SVR variance prediction outside its domain."""

    RAISE = "raise"
    CLIP = "clip"


class DegenerateTauPolicy(str, Enum):
    """Explicit handling when the residual-square variance is not positive."""

    RAISE = "raise"
    RETURN_NAN = "return_nan"


class ArgmaxTiePolicy(str, Enum):
    """The paper does not specify how equal change-point maxima are resolved."""

    FIRST = "first"
    LAST = "last"
    RAISE = "raise"


@dataclass(frozen=True)
class CUSUMResult:
    statistic: float
    reject: bool
    change_index_one_based: int | None
    centered_path: FloatArray
    tau_squared: float
    critical_value: float


def _finite_vector(values: ArrayLike, *, name: str) -> FloatArray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a nonempty one-dimensional array")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def standardized_residuals(
    observations: ArrayLike,
    variance_predictions: ArrayLike,
    *,
    nonpositive_policy: NonPositiveVariancePolicy,
    variance_floor: float | None = None,
) -> FloatArray:
    """Return ``y_t / sigma_hat_t`` with a declared positivity policy."""

    y = _finite_vector(observations, name="observations")
    variance = _finite_vector(variance_predictions, name="variance_predictions")
    if y.size != variance.size:
        raise ValueError("observations and variance_predictions must have equal length")
    invalid = variance <= 0.0
    if nonpositive_policy is NonPositiveVariancePolicy.RAISE:
        if np.any(invalid):
            bad = np.flatnonzero(invalid).tolist()
            raise ValueError(f"non-positive variance predictions at indices {bad}")
    elif nonpositive_policy is NonPositiveVariancePolicy.CLIP:
        if variance_floor is None or not np.isfinite(variance_floor) or variance_floor <= 0:
            raise ValueError("CLIP requires a finite positive variance_floor")
        variance = np.maximum(variance, variance_floor)
    else:
        raise ValueError(f"unsupported nonpositive policy: {nonpositive_policy!r}")
    return y / np.sqrt(variance)


def centered_square_path(residuals: ArrayLike) -> FloatArray:
    """Compute the unnormalised centered cumulative sum of squared residuals."""

    residual = _finite_vector(residuals, name="residuals")
    squared = residual**2
    n = residual.size
    return np.cumsum(squared) - (np.arange(1, n + 1) / n) * squared.sum()


def tau_squared(residuals: ArrayLike) -> float:
    """Paper variance estimator with denominator ``n`` (not ``n-1``)."""

    residual = _finite_vector(residuals, name="residuals")
    squared = residual**2
    return float(np.mean(residual**4) - np.mean(squared) ** 2)


def _argmax_one_based(path: FloatArray, policy: ArgmaxTiePolicy) -> int:
    absolute = np.abs(path)
    maximum = float(np.max(absolute))
    ties = np.flatnonzero(np.isclose(absolute, maximum, rtol=0.0, atol=0.0))
    if policy is ArgmaxTiePolicy.FIRST:
        return int(ties[0] + 1)
    if policy is ArgmaxTiePolicy.LAST:
        return int(ties[-1] + 1)
    if policy is ArgmaxTiePolicy.RAISE:
        if ties.size != 1:
            raise ValueError(f"change-point argmax is tied at one-based indices {(ties + 1).tolist()}")
        return int(ties[0] + 1)
    raise ValueError(f"unsupported argmax tie policy: {policy!r}")


def cusum_squares_test(
    residuals: ArrayLike,
    *,
    tie_policy: ArgmaxTiePolicy,
    degenerate_tau_policy: DegenerateTauPolicy,
    critical_value: float = PAPER_CRITICAL_VALUE_5_PERCENT,
) -> CUSUMResult:
    """Compute the paper's retrospective statistic and separate localization."""

    if not np.isfinite(critical_value) or critical_value <= 0:
        raise ValueError("critical_value must be finite and positive")
    residual = _finite_vector(residuals, name="residuals")
    path = centered_square_path(residual)
    tau2 = tau_squared(residual)
    if not np.isfinite(tau2) or tau2 <= 0.0:
        if degenerate_tau_policy is DegenerateTauPolicy.RAISE:
            raise ValueError(f"tau_squared must be positive; got {tau2!r}")
        if degenerate_tau_policy is DegenerateTauPolicy.RETURN_NAN:
            return CUSUMResult(
                statistic=float("nan"),
                reject=False,
                change_index_one_based=None,
                centered_path=path,
                tau_squared=tau2,
                critical_value=float(critical_value),
            )
        raise ValueError(f"unsupported degenerate tau policy: {degenerate_tau_policy!r}")

    statistic = float(np.max(np.abs(path)) / (np.sqrt(residual.size) * np.sqrt(tau2)))
    change_index = _argmax_one_based(path, tie_policy)
    return CUSUMResult(
        statistic=statistic,
        reject=bool(statistic >= critical_value),
        change_index_one_based=change_index,
        centered_path=path,
        tau_squared=tau2,
        critical_value=float(critical_value),
    )

