"""미래 정보 누수 검사 — t 이후 관측을 바꿔도 t 이하의 feature·신호가 변하지 않아야 한다 (prefix 불변성)."""

import numpy as np
import pandas as pd
import pytest

from r2h.detection import PageCUSUM, VolScaledThreshold
from r2h.features import (
    log_returns,
    moving_average,
    rolling_corr,
    rolling_volatility,
    vol_scaled_return,
    volume_ratio,
)

N = 260
IDX = pd.bdate_range("2023-01-02", periods=N)
CUT = 180


def series(seed: int) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(0, 0.01, N), index=IDX)


def perturb_future(s: pd.Series, seed: int = 99) -> pd.Series:
    out = s.copy()
    out.iloc[CUT + 1 :] = np.random.default_rng(seed).normal(0, 0.05, N - CUT - 1)
    return out


FEATURES = {
    "rolling_volatility": lambda r: rolling_volatility(r, 20),
    "rolling_volatility_excl": lambda r: rolling_volatility(r, 20, exclude_current=True),
    "moving_average": lambda r: moving_average(r, 20),
    "vol_scaled_return": lambda r: vol_scaled_return(r, 60),
    "volume_ratio": lambda r: volume_ratio(r.abs() * 1e6, 20),
    "log_returns": lambda r: log_returns(100 * np.exp(r.cumsum())),
}


@pytest.mark.parametrize("name", sorted(FEATURES))
def test_feature_prefix_invariance(name):
    f = FEATURES[name]
    a, b = f(series(1)), f(perturb_future(series(1)))
    pd.testing.assert_series_equal(a.iloc[: CUT + 1], b.iloc[: CUT + 1])


def test_rolling_corr_prefix_invariance():
    x, y = series(1), series(2)
    a = rolling_corr(x, y, 30)
    b = rolling_corr(perturb_future(x), perturb_future(y, 7), 30)
    pd.testing.assert_frame_equal(a.iloc[: CUT + 1], b.iloc[: CUT + 1])


@pytest.mark.parametrize(
    "det", [VolScaledThreshold(window=40, k=2.0), PageCUSUM(window=40, drift=0.2, threshold=3.0)]
)
def test_online_detector_prefix_invariance(det):
    a = det.run(series(5), ticker="S", data_version="v")
    b = det.run(perturb_future(series(5)), ticker="S", data_version="v")
    pd.testing.assert_frame_equal(a.iloc[: CUT + 1], b.iloc[: CUT + 1])
    assert (a["available_until"] <= a["signal_at"]).all()


@pytest.mark.parametrize(
    "det", [VolScaledThreshold(window=40, k=2.0), PageCUSUM(window=40, drift=0.2, threshold=3.0)]
)
def test_truncated_run_equals_prefix_of_full_run(det):
    """t 시점까지 잘라 실행한 결과 = 전체 실행의 앞부분 (온라인 재현 조건)."""
    s = series(8)
    full = det.run(s, ticker="S", data_version="v")
    cut = det.run(s.iloc[: CUT + 1], ticker="S", data_version="v")
    pd.testing.assert_frame_equal(full.iloc[: CUT + 1].reset_index(drop=True), cut.reset_index(drop=True))
