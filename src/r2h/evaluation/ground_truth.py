"""사건 정답(Event Ground Truth) 계약 v0.1 — 오프라인 평가 전용.

정답 라벨은 탐지기와 독립된 정의로 만든다. 같은 CUSUM 출력으로 정답과 신호를 동시에 만들지 않는다.
미래 구간을 보고 만든 라벨(예: 향후 h 일 누적수익률)은 평가에만 쓰고 t 시점 feature 로 되돌리지 않는다.
**어떤 정의를 정답으로 쓸지는 교수·4조 승인 전 미정이다** (docs/decisions/OPEN_DECISIONS.md D-01).
"""

from __future__ import annotations

import pandas as pd

GROUND_TRUTH_COLUMNS: tuple[str, ...] = (
    "label_version",
    "event_id",
    "ticker",
    "event_start",
    "event_end",
    "direction",
    "threshold_definition",
    "created_from_window",
)


class GroundTruthViolation(ValueError):
    """정답 계약 위반."""


def validate_ground_truth(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in GROUND_TRUTH_COLUMNS if c not in df.columns]
    if missing:
        raise GroundTruthViolation(f"missing columns: {missing}")
    if df["event_id"].duplicated().any():
        raise GroundTruthViolation("event_id must be unique")
    if (df["event_end"] < df["event_start"]).any():
        raise GroundTruthViolation("event_end before event_start")
    if not df["direction"].isin([1, -1]).all():
        raise GroundTruthViolation("direction must be +1 (surge) or -1 (crash)")
    if len(df["label_version"].unique()) > 1:
        raise GroundTruthViolation("mixing label versions in one evaluation is not allowed")
    return df
