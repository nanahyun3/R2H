"""합성 시계열 — 정답 변화점을 알고 있는 테스트·예제용 데이터 (실제 시세 아님).

주의: 합성 데이터의 '정답 변화점'은 생성 과정에서 주입한 위치다. 금융 가격의 '급등 사건' 라벨과 의미가 다르다
(4조 합성 데이터의 change point 와도 정의가 같다고 가정하지 않는다).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class InjectedSurge:
    start: int  # 위치 (0-based)
    length: int  # 상승 drift 가 유지되는 일수
    drift: float  # 일간 평균 수익률 증가분


def business_calendar(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    """주말을 뺀 영업일 n 개 (휴장일은 반영하지 않음 — 합성 전용)."""
    return pd.bdate_range(start=start, periods=n)


def surge_series(
    n: int,
    surges: list[InjectedSurge],
    *,
    sigma: float = 0.01,
    seed: int = 0,
    start: str = "2020-01-01",
) -> tuple[pd.Series, pd.DatetimeIndex]:
    """iid N(0, σ²) 수익률에 지정 구간 drift 를 더한다. 반환 (일간 로그수익률, 영업일 calendar)."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, sigma, n)
    for s in surges:
        if s.start < 0 or s.start + s.length > n:
            raise ValueError("surge outside series")
        r[s.start : s.start + s.length] += s.drift
    cal = business_calendar(n, start)
    return pd.Series(r, index=cal, name="ret"), cal


def ground_truth_from_injections(
    calendar: pd.DatetimeIndex,
    surges: list[InjectedSurge],
    *,
    ticker: str,
    label_version: str = "synthetic-0.1",
) -> pd.DataFrame:
    """주입 위치를 정답 사건 표(``evaluation.GROUND_TRUTH_COLUMNS``)로 변환."""
    rows = [
        {
            "label_version": label_version,
            "event_id": f"{ticker}-syn-{k:03d}",
            "ticker": ticker,
            "event_start": calendar[s.start],
            "event_end": calendar[s.start + s.length - 1],
            "direction": 1,
            "threshold_definition": f"injected drift {s.drift} for {s.length}d",
            "created_from_window": "synthetic_generator",
        }
        for k, s in enumerate(surges)
    ]
    return pd.DataFrame(rows)
