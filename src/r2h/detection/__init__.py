"""탐지 인터페이스·출력 계약·참조 탐지기."""

from .base import Detector, build_signal_frame
from .baselines import PageCUSUM, VolScaledThreshold
from .posthoc import PosthocCUSUMSquares
from .schema import MODES, SIGNAL_COLUMNS, SignalContractViolation, params_hash, validate_signals

__all__ = [
    "MODES",
    "SIGNAL_COLUMNS",
    "Detector",
    "PageCUSUM",
    "PosthocCUSUMSquares",
    "SignalContractViolation",
    "VolScaledThreshold",
    "build_signal_frame",
    "params_hash",
    "validate_signals",
]
