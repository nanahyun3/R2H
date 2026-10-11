"""탐지기 공통 인터페이스. 입력 = 한 ticker 의 시계열(DatetimeIndex), 출력 = ``schema.SIGNAL_COLUMNS`` 표."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from .schema import Mode, params_hash, validate_signals


@runtime_checkable
class Detector(Protocol):
    @property
    def method_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def mode(self) -> Mode: ...

    def params(self) -> dict[str, Any]: ...

    def run(self, series: pd.Series, *, ticker: str, data_version: str) -> pd.DataFrame: ...


def build_signal_frame(
    detector: Detector,
    *,
    ticker: str,
    data_version: str,
    signal_at: pd.Index,
    score: np.ndarray,
    is_alarm: np.ndarray,
    available_until: pd.Index,
) -> pd.DataFrame:
    """탐지기 구현이 공통으로 쓰는 출력 조립 + 계약 검사."""
    df = pd.DataFrame(
        {
            "ticker": ticker,
            "signal_at": pd.DatetimeIndex(signal_at),
            "score": np.asarray(score, float),
            "is_alarm": np.asarray(is_alarm, bool),
            "method_id": detector.method_id,
            "mode": detector.mode,
            "model_version": detector.model_version,
            "data_version": data_version,
            "available_until": pd.DatetimeIndex(available_until),
            "params_hash": params_hash(detector.params()),
        }
    )
    return validate_signals(df)
