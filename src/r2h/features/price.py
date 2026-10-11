"""과거 정보만 쓰는 가격·거래량 feature.

규약: 모든 함수는 index 를 보존하고, 행 t 의 값은 t 이하 관측만으로 계산된다 (t 종가 이후 이용 가능).
'당일을 제외한 과거 통계'가 필요한 경우(예: r_t 를 직전 변동성으로 나누기)는 ``shift(1)`` 을 함수 안에서 명시한다.
warm-up 구간(관측 수 < min_periods)은 NaN 이다. 0 분모는 NaN 으로 두고 Inf 를 만들지 않는다.

알려진 한계: rolling 표준편차는 pandas 의 누적합 알고리즘을 그대로 쓴다 (Track A 와 비트 동일 parity 유지).
pandas 는 시계열 전체에 걸친 누적합을 쓰므로, 창의 산포가 그때까지 나온 가장 큰 |r| 보다 수 자릿수 이상 작으면
(예: 0.1 크기 수익률 뒤 1e-12 크기 수익률만 남은 창) σ 의 상대오차가 커지고 그 잔차는 pandas 버전마다 다르다.
실제 ETF 20종 패널에서 2-pass 계산과의 최대 상대차는 4.8e-14 였다 (docs/provenance/PARITY.md).

원본: SA_ETF Track A ``src/r2h/research_a/data.py::log_returns`` (logdiff 산식) 와
``price_events.py`` P1 ``r_t / σ_{t-1}(60)`` 정의. 출처 sha256 은 docs/provenance 참조.
"""

from __future__ import annotations

from typing import TypeVar, cast

import numpy as np
import pandas as pd

Frame = TypeVar("Frame", pd.Series, pd.DataFrame)


def log_returns(close: Frame) -> Frame:
    """r_t = ln C_t − ln C_{t−1}. 첫 행은 NaN 으로 남긴다 (행을 지우지 않아 index 가 원 시계열과 같다).

    0 이하 가격은 로그가 정의되지 않으므로 실패한다 (보정하지 않음).
    """
    values = close.to_numpy(dtype=float)
    if (values[~np.isnan(values)] <= 0).any():
        raise ValueError("non-positive price — log return undefined")
    # np.log on a pandas object returns the same pandas type (__array_ufunc__); numpy stubs type it as ndarray.
    return cast(Frame, np.log(close.astype(float))).diff()


def _mp(window: int, min_periods: int | None) -> int:
    if window < 1:
        raise ValueError("window must be >= 1")
    mp = window if min_periods is None else min_periods
    if not 1 <= mp <= window:
        raise ValueError("min_periods must be in [1, window]")
    return mp


def rolling_volatility(
    r: Frame, window: int, *, min_periods: int | None = None, exclude_current: bool = False
) -> Frame:
    """창 [t−w+1, t] 의 표본표준편차(ddof=1). ``exclude_current=True`` 면 [t−w, t−1] (= shift(1))."""
    out = r.rolling(window, min_periods=_mp(window, min_periods)).std(ddof=1)
    return out.shift(1) if exclude_current else out


def moving_average(x: Frame, window: int, *, min_periods: int | None = None) -> Frame:
    """창 [t−w+1, t] 단순이동평균."""
    return x.rolling(window, min_periods=_mp(window, min_periods)).mean()


def volume_ratio(volume: Frame, window: int, *, min_periods: int | None = None) -> Frame:
    """volume_t / mean(volume_{t−w..t−1}). 직전 평균이 0 이면 NaN."""
    base = volume.astype(float).rolling(window, min_periods=_mp(window, min_periods)).mean().shift(1)
    return volume.astype(float) / base.where(base > 0)


def vol_scaled_return(r: Frame, window: int = 60, *, min_periods: int | None = None) -> Frame:
    """z_t = r_t / σ_{t−1}(window). σ 는 당일을 제외한다. σ = 0 (상수 수익률 창) 이면 NaN.

    SA_ETF Track A 가격 사건 P1 의 점수와 같다 — 원본은 ``min_periods=40`` 을 쓰므로 같은 값을 얻으려면
    ``vol_scaled_return(r, 60, min_periods=40)`` (P1: z_t ≥ k 급등, ≤ −k 급락).
    """
    sigma = rolling_volatility(r, window, min_periods=min_periods, exclude_current=True)
    return r / sigma.where(sigma > 0)
