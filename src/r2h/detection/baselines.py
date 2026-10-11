"""온라인 baseline 탐지기 (참조 구현).

상태: **REFERENCE — 합성 시계열 테스트만 통과**. 실제 ETF 에서 임계값을 튜닝하거나 성능을 측정하지 않았다.
2조 W04 CUSUM 의 최종 구현이 아니며, 계약(입력 → {시점, 점수, 탐지 여부})과 누수 방지 규약을 보여 주는 기준선이다.

- ``VolScaledThreshold``  z_t = r_t / σ_{t−1}(w) ≥ k (SA_ETF Track A P1 점수; P1 과 같게 하려면 ``min_periods=40``)
- ``PageCUSUM``           Page(1954) 단측 CUSUM. 과거 창의 평균·표준편차로 표준화한 수익률을 누적,
                          S_t = max(0, S_{t−1} + z_t − drift), S_t ≥ h 이면 경보 후 S 를 0 으로 재설정.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from ..features.price import rolling_volatility, vol_scaled_return
from .base import build_signal_frame


def _check_series(series: pd.Series) -> None:
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("series must have a DatetimeIndex")
    if not series.index.is_monotonic_increasing or series.index.has_duplicates:
        raise ValueError("series index must be strictly increasing")


@dataclass(frozen=True)
class VolScaledThreshold:
    """일간 수익률 시계열 입력. warm-up(σ 미정의) 구간은 score NaN · 경보 없음."""

    window: int = 60
    k: float = 3.0
    direction: Literal[1, -1] = 1
    min_periods: int | None = None
    method_id: str = "vol_scaled_threshold"
    model_version: str = "0.1.0"
    mode: Literal["online"] = "online"

    def params(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "k": self.k,
            "direction": self.direction,
            "min_periods": self.min_periods,
        }

    def run(self, series: pd.Series, *, ticker: str, data_version: str) -> pd.DataFrame:
        _check_series(series)
        z = vol_scaled_return(series.astype(float), self.window, min_periods=self.min_periods).to_numpy(float)
        z = z * self.direction
        alarm = np.nan_to_num(z, nan=-np.inf) >= self.k
        return build_signal_frame(
            self,
            ticker=ticker,
            data_version=data_version,
            signal_at=series.index,
            score=z,
            is_alarm=alarm,
            available_until=series.index,
        )


@dataclass(frozen=True)
class PageCUSUM:
    """단측 CUSUM (direction=+1 상승, −1 하락). 표준화는 [t−w, t−1] 창만 사용 (당일 제외)."""

    window: int = 60
    drift: float = 0.5
    threshold: float = 5.0
    direction: Literal[1, -1] = 1
    method_id: str = "page_cusum_reference"
    model_version: str = "0.1.0"
    mode: Literal["online"] = "online"

    def params(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: d[k] for k in ("window", "drift", "threshold", "direction")}

    def run(self, series: pd.Series, *, ticker: str, data_version: str) -> pd.DataFrame:
        _check_series(series)
        if self.threshold <= 0 or self.drift < 0:
            raise ValueError("threshold must be > 0 and drift >= 0")
        r = series.astype(float)
        mu = r.rolling(self.window, min_periods=self.window).mean().shift(1)
        sd = rolling_volatility(r, self.window, exclude_current=True)
        z = ((r - mu) / sd.where(sd > 0)).to_numpy(float) * self.direction
        s = np.full(z.size, np.nan)
        alarm = np.zeros(z.size, bool)
        acc = 0.0
        for i, zi in enumerate(z):
            if np.isnan(zi):  # warm-up 또는 결측: 누적을 진행하지 않고 상태 유지
                continue
            acc = max(0.0, acc + zi - self.drift)
            s[i] = acc
            if acc >= self.threshold:
                alarm[i] = True
                acc = 0.0
        return build_signal_frame(
            self,
            ticker=ticker,
            data_version=data_version,
            signal_at=series.index,
            score=s,
            is_alarm=alarm,
            available_until=series.index,
        )
