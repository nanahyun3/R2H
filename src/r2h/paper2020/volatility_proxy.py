"""Equation-faithful volatility proxy and lag design for Lee et al. (2020).

The paper's proxy at time ``t`` includes the current squared observation.  The
train/validation/test boundary behaviour is not stated in the paper, so callers
must choose it explicitly instead of inheriting a silent rolling convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


class BoundaryPolicy(str, Enum):
    """How a new chronological block may use observations from its predecessor."""

    RESET = "reset"
    CARRY = "carry"


@dataclass(frozen=True)
class LaggedDesign:
    """SVR design rows and their zero-based target indices in the current block."""

    X: FloatArray
    target: FloatArray
    target_indices: NDArray[np.int64]


def _finite_vector(values: ArrayLike, *, name: str, allow_empty: bool = False) -> FloatArray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not allow_empty and result.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def moving_square_proxy(
    observations: ArrayLike,
    *,
    m: int = 5,
    boundary_policy: BoundaryPolicy,
    history: ArrayLike | None = None,
) -> FloatArray:
    """Compute the paper's moving-average proxy ``sigma_tilde_t^2``.

    For a history of length smaller than ``m``, the expanding mean prescribed
    in Step 2 is used.  ``CARRY`` treats ``history`` and ``observations`` as one
    chronological series; ``RESET`` intentionally ignores preceding history.
    Only proxy values for ``observations`` are returned.
    """

    if not isinstance(m, int) or isinstance(m, bool) or m <= 0:
        raise ValueError("m must be a positive integer")
    current = _finite_vector(observations, name="observations", allow_empty=True)
    previous = (
        np.empty(0, dtype=float)
        if history is None
        else _finite_vector(history, name="history", allow_empty=True)
    )
    if boundary_policy is BoundaryPolicy.RESET:
        previous = np.empty(0, dtype=float)
    elif boundary_policy is not BoundaryPolicy.CARRY:
        raise ValueError(f"unsupported boundary policy: {boundary_policy!r}")

    joined = np.concatenate((previous, current))
    squared = joined**2
    prefix = np.concatenate(([0.0], np.cumsum(squared, dtype=float)))
    start_index = previous.size
    result = np.empty(current.size, dtype=float)
    for local_index, joined_index in enumerate(range(start_index, joined.size)):
        left = max(0, joined_index - m + 1)
        count = joined_index - left + 1
        result[local_index] = (prefix[joined_index + 1] - prefix[left]) / count
    return result


def build_lagged_design(
    observations: ArrayLike,
    variance_proxy: ArrayLike,
    *,
    p: int,
    q: int,
    boundary_policy: BoundaryPolicy,
    history_observations: ArrayLike | None = None,
    history_variance_proxy: ArrayLike | None = None,
) -> LaggedDesign:
    """Construct Equation (9), preserving oldest-to-newest feature order.

    Targets are the contemporaneous proxy values implied by Procedure Steps
    2--4.  That target interpretation is documented as an inference in B1.
    """

    if any(not isinstance(lag, int) or isinstance(lag, bool) or lag < 0 for lag in (p, q)):
        raise ValueError("p and q must be nonnegative integers")
    if p + q == 0:
        raise ValueError("at least one of p and q must be positive for SVR")

    current_y = _finite_vector(observations, name="observations", allow_empty=True)
    current_proxy = _finite_vector(variance_proxy, name="variance_proxy", allow_empty=True)
    if current_y.size != current_proxy.size:
        raise ValueError("observations and variance_proxy must have equal length")

    if boundary_policy is BoundaryPolicy.RESET:
        previous_y = np.empty(0, dtype=float)
        previous_proxy = np.empty(0, dtype=float)
    elif boundary_policy is BoundaryPolicy.CARRY:
        previous_y = (
            np.empty(0, dtype=float)
            if history_observations is None
            else _finite_vector(
                history_observations, name="history_observations", allow_empty=True
            )
        )
        previous_proxy = (
            np.empty(0, dtype=float)
            if history_variance_proxy is None
            else _finite_vector(
                history_variance_proxy, name="history_variance_proxy", allow_empty=True
            )
        )
        if previous_y.size != previous_proxy.size:
            raise ValueError("history observations and proxies must have equal length")
    else:
        raise ValueError(f"unsupported boundary policy: {boundary_policy!r}")

    all_y = np.concatenate((previous_y, current_y))
    all_proxy = np.concatenate((previous_proxy, current_proxy))
    offset = previous_y.size
    first_usable = max(p, q)
    rows: list[FloatArray] = []
    targets: list[float] = []
    indices: list[int] = []
    for local_index in range(current_y.size):
        global_index = offset + local_index
        if global_index < first_usable:
            continue
        y_lags = all_y[global_index - p : global_index] ** 2 if p else np.empty(0)
        proxy_lags = (
            all_proxy[global_index - q : global_index] if q else np.empty(0)
        )
        rows.append(np.concatenate((y_lags, proxy_lags)).astype(float, copy=False))
        targets.append(float(current_proxy[local_index]))
        indices.append(local_index)

    width = p + q
    X = np.vstack(rows) if rows else np.empty((0, width), dtype=float)
    return LaggedDesign(
        X=X,
        target=np.asarray(targets, dtype=float),
        target_indices=np.asarray(indices, dtype=np.int64),
    )

