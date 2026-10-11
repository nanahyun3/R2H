"""사후(retrospective) CUSUM-of-squares 검정을 탐지 출력 계약에 싣는 어댑터.

검정 본체는 ``paper2020_cusum.py`` — SA_ETF Track B (Lee·Kim·Lee 2020, Entropy 22(5) 578, §3) 의 모듈을 바이트 그대로
옮긴 것이다 (sha256 은 docs/provenance). **이 검정은 표본 전체를 본 뒤 한 번 판정하는 사후 검정이다.**
온라인 경보가 아니므로 ``mode="posthoc"`` 로만 출력하고, 변화점 위치는 ``signal_at``, 실제로 사용한 마지막 관측은
``available_until`` (= 표본 끝) 에 둔다.

Track B 상태: METHOD_FIDELITY_UNRESOLVED — 원문 Tables 1–6 과 실증 통계량이 재현되지 않았다
(research/svr_garch_cusum_track_b.md). 여기서 이 검정을 써서 얻은 결과를 "원문 방법의 결과" 라고 부르지 않는다.
입력 잔차(표준화 잔차)를 만드는 SVR–GARCH 단계는 이식하지 않았다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from .base import build_signal_frame
from .paper2020_cusum import (
    PAPER_CRITICAL_VALUE_5_PERCENT,
    ArgmaxTiePolicy,
    DegenerateTauPolicy,
    cusum_squares_test,
)


@dataclass(frozen=True)
class PosthocCUSUMSquares:
    """표준화 잔차 시계열 → 1 행 (변화점 후보 1개, 통계량, 기각 여부)."""

    critical_value: float = PAPER_CRITICAL_VALUE_5_PERCENT
    method_id: str = "cusum_squares_lee2020_posthoc"
    model_version: str = "0.1.0"
    mode: Literal["posthoc"] = "posthoc"

    def params(self) -> dict[str, Any]:
        return {"critical_value": self.critical_value, "tie_policy": "first", "degenerate_tau": "raise"}

    def run(self, series: pd.Series, *, ticker: str, data_version: str) -> pd.DataFrame:
        if not isinstance(series.index, pd.DatetimeIndex) or not series.index.is_monotonic_increasing:
            raise ValueError("residual series needs an increasing DatetimeIndex")
        res = cusum_squares_test(
            series.to_numpy(float),
            tie_policy=ArgmaxTiePolicy.FIRST,
            degenerate_tau_policy=DegenerateTauPolicy.RAISE,
            critical_value=self.critical_value,
        )
        assert res.change_index_one_based is not None  # RAISE policy guarantees a location
        k = res.change_index_one_based - 1
        return build_signal_frame(
            self,
            ticker=ticker,
            data_version=data_version,
            signal_at=series.index[[k]],
            score=np.array([res.statistic]),
            is_alarm=np.array([res.reject]),
            available_until=series.index[[-1]],
        )
