"""Lee, Kim & Lee (2020) paper-faithful reconstruction core."""

from .cusum import (
    PAPER_CRITICAL_VALUE_5_PERCENT,
    ArgmaxTiePolicy,
    CUSUMResult,
    DegenerateTauPolicy,
    NonPositiveVariancePolicy,
    centered_square_path,
    cusum_squares_test,
    standardized_residuals,
    tau_squared,
)
from .svr_garch import (
    FeatureScalingPolicy,
    SVRFitPolicy,
    SVRGARCHProtocolSpec,
    SVRParameters,
    SelectionTiePolicy,
    TestVarianceInputPolicy,
    VariancePredictionPolicy,
    estimate_svr_garch_residuals,
    make_residual_estimator,
    paper_gamma_to_sklearn,
    select_and_refit,
)
from .volatility_proxy import (
    BoundaryPolicy,
    LaggedDesign,
    build_lagged_design,
    moving_square_proxy,
)

__all__ = [
    "PAPER_CRITICAL_VALUE_5_PERCENT",
    "ArgmaxTiePolicy",
    "BoundaryPolicy",
    "CUSUMResult",
    "DegenerateTauPolicy",
    "FeatureScalingPolicy",
    "LaggedDesign",
    "NonPositiveVariancePolicy",
    "SVRFitPolicy",
    "SVRGARCHProtocolSpec",
    "SVRParameters",
    "SelectionTiePolicy",
    "TestVarianceInputPolicy",
    "VariancePredictionPolicy",
    "build_lagged_design",
    "centered_square_path",
    "cusum_squares_test",
    "estimate_svr_garch_residuals",
    "make_residual_estimator",
    "moving_square_proxy",
    "paper_gamma_to_sklearn",
    "select_and_refit",
    "standardized_residuals",
    "tau_squared",
]
