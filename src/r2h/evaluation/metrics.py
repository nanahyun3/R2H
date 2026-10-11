"""사건 수준 지표 — 탐지율·오탐(ticker-year 당)·지연·미탐, 오탐 상한 하 탐지율.

지연 평균은 **탐지된 사건만**으로 계산하고 미탐 수를 함께 보고한다 (미탐을 지연 최대값으로 채우지 않는다).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EventMetrics:
    n_events: int
    n_detected: int
    n_missed: int
    recall: float
    n_fp: int
    n_duplicate: int
    n_suppressed: int
    fp_per_ticker_year: float
    alarm_precision: float
    delay_mean: float
    delay_median: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def event_metrics(alarms: pd.DataFrame, events: pd.DataFrame, ticker_years: float) -> EventMetrics:
    """``ticker_years`` = 평가 구간의 Σ_ticker (거래일 수 / 252). 0 이하이면 오류."""
    if ticker_years <= 0:
        raise ValueError("ticker_years must be positive")
    st = alarms["status"].value_counts()
    tp, fp = int(st.get("TP", 0)), int(st.get("FP", 0))
    n_ev = len(events)
    det = int(events["detected"].sum()) if n_ev else 0
    delays = events.loc[events["detected"], "delay"].astype(float) if n_ev else pd.Series(dtype=float)
    return EventMetrics(
        n_events=n_ev,
        n_detected=det,
        n_missed=n_ev - det,
        recall=det / n_ev if n_ev else float("nan"),
        n_fp=fp,
        n_duplicate=int(st.get("DUPLICATE", 0)),
        n_suppressed=int(st.get("SUPPRESSED", 0)),
        fp_per_ticker_year=fp / ticker_years,
        alarm_precision=tp / (tp + fp) if tp + fp else float("nan"),
        delay_mean=float(delays.mean()) if len(delays) else float("nan"),
        delay_median=float(delays.median()) if len(delays) else float("nan"),
    )


def recall_at_fp_cap(
    results: Iterable[tuple[float, EventMetrics]], fp_cap: float
) -> tuple[float, EventMetrics] | None:
    """(threshold, metrics) 목록 중 fp_per_ticker_year ≤ cap 에서 recall 최대 (동률이면 FP 가 적은 쪽, 그다음 작은
    threshold). 조건을 만족하는 설정이 없으면 None. **임계값 선택은 개발 구간에서만** 한다."""
    ok = [(t, m) for t, m in results if m.fp_per_ticker_year <= fp_cap and not np.isnan(m.recall)]
    if not ok:
        return None
    return max(ok, key=lambda tm: (tm[1].recall, -tm[1].fp_per_ticker_year, -tm[0]))
