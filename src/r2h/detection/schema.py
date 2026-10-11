"""탐지 출력 계약 v0.1 — 2조 CUSUM · 4조 BOCPD 가 같은 표로 교환하는 최소 스키마.

한 행 = 한 시점의 탐지기 출력. 점수(score)는 방법마다 의미가 다르다 (CUSUM 통계량 ≠ BOCPD 확률) —
방법 간 비교는 ``is_alarm`` 이진 경보와 사건 수준 매칭에서만 한다.

``mode``
  online   t 시점까지의 관측만 사용. ``available_until <= signal_at`` 이 반드시 성립해야 한다.
  posthoc  전체 표본을 본 뒤의 사후 검정(예: Lee·Kim·Lee 2020 CUSUM-of-squares). 변화점 위치는 ``signal_at`` 에,
           실제로 쓴 마지막 관측은 ``available_until`` 에 둔다 (> signal_at 가능). 온라인 평가에 섞지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

import numpy as np
import pandas as pd

Mode = Literal["online", "posthoc"]
MODES: tuple[str, ...] = ("online", "posthoc")

SIGNAL_COLUMNS: tuple[str, ...] = (
    "ticker",
    "signal_at",
    "score",
    "is_alarm",
    "method_id",
    "mode",
    "model_version",
    "data_version",
    "available_until",
    "params_hash",
)


class SignalContractViolation(ValueError):
    """탐지 출력 계약 위반."""


def params_hash(params: Mapping[str, Any]) -> str:
    """정렬된 JSON 의 sha256 앞 16자. 같은 파라미터면 실행 환경과 무관하게 같은 값."""
    body = json.dumps(dict(params), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def validate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """계약 검사 후 그대로 반환한다. 위반 시 ``SignalContractViolation``."""
    missing = [c for c in SIGNAL_COLUMNS if c not in df.columns]
    if missing:
        raise SignalContractViolation(f"missing columns: {missing}")
    bad_mode = sorted(set(df["mode"]) - set(MODES))
    if bad_mode:
        raise SignalContractViolation(f"unknown mode values: {bad_mode}")
    if df["is_alarm"].dtype != bool:
        raise SignalContractViolation("is_alarm must be bool dtype")
    score = df["score"].to_numpy(float)
    if np.isinf(score).any():
        raise SignalContractViolation("score must not be infinite (use NaN during warm-up)")
    if (df["is_alarm"] & np.isnan(score)).any():
        raise SignalContractViolation("alarm raised with undefined (NaN) score")
    online = df["mode"].eq("online")
    late = online & (df["available_until"] > df["signal_at"])
    if late.any():
        raise SignalContractViolation(
            f"future leakage: {int(late.sum())} online rows with available_until > signal_at"
        )
    if df.duplicated(["ticker", "method_id", "params_hash", "signal_at"]).any():
        raise SignalContractViolation("duplicate (ticker, method_id, params_hash, signal_at) rows")
    return df


def empty_signals() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object) for c in SIGNAL_COLUMNS})
