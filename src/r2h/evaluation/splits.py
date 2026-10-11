"""시간순 분할 — 개발/검증/관찰 고정 구간과 walk-forward.

실제 구간 경계(예: 2019–2024 개발 · 2025 검증 · 2026 관찰)는 교수 확인 전 미확정이므로 코드에 박지 않고
config 로 넘긴다 (docs/decisions/OPEN_DECISIONS.md D-03). 2026 은 기존 EDA 가 이미 본 데이터라 blind holdout 이 아니다.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from itertools import pairwise

import numpy as np
import pandas as pd


def chronological_split(
    index: pd.DatetimeIndex, bounds: Mapping[str, tuple[str, str]]
) -> dict[str, np.ndarray]:
    """``bounds`` = {이름: (시작, 끝)} (양끝 포함). 구간이 겹치거나 시간 순서가 뒤바뀌면 오류."""
    spans = sorted(((pd.Timestamp(a), pd.Timestamp(b), k) for k, (a, b) in bounds.items()))
    for (_, b1, k1), (a2, _, k2) in pairwise(spans):
        if a2 <= b1:
            raise ValueError(f"split {k1!r} overlaps {k2!r}")
    for a, b, k in spans:
        if b < a:
            raise ValueError(f"split {k!r} ends before it starts")
    return {k: np.flatnonzero((index >= a) & (index <= b)) for a, b, k in spans}


def walk_forward(
    n: int, *, train: int, test: int, step: int | None = None, embargo: int = 0, expanding: bool = False
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """위치 기반 walk-forward. 각 fold: train 끝 + embargo < test 시작 (embargo 거래일을 비운다)."""
    if min(train, test) < 1 or embargo < 0:
        raise ValueError("train, test >= 1 and embargo >= 0 required")
    step = test if step is None else step
    if step < 1:
        raise ValueError("step must be >= 1")
    start = 0
    while True:
        tr_lo = 0 if expanding else start
        tr_hi = start + train
        te_lo = tr_hi + embargo
        te_hi = te_lo + test
        if te_hi > n:
            return
        yield np.arange(tr_lo, tr_hi), np.arange(te_lo, te_hi)
        start += step
