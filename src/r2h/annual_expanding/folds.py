"""연간 expanding fold 정의 (PROTOCOL_LOCK L1·L2).

검정연도 y 의 학습 이력 = date < y-01-01 인 유효 수익률. 전략별로 학습 표본만 바뀐다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

STRATEGIES: tuple[str, ...] = ("expanding", "trailing_2y", "frozen_2019")


@dataclass(frozen=True)
class AnnualFold:
    ticker: str
    test_year: int
    history_strategy: str
    train_start: pd.Timestamp | None
    train_end: pd.Timestamp | None
    test_start: pd.Timestamp | None
    test_end: pd.Timestamp | None
    n_history: int
    n_inner_train: int
    n_inner_val: int
    n_test: int
    status: str  # PILOT_SHORT_HISTORY · PRIMARY · PARTIAL_NON_BLIND · INSUFFICIENT_HISTORY · SKIP_* · IDENTICAL_TO_EXPANDING


def year_status(year: int, cfg: dict) -> str:
    f = cfg["folds"]
    if year in f["pilot_short_history_years"]:
        return "PILOT_SHORT_HISTORY"
    if year in f["partial_nonblind_years"]:
        return "PARTIAL_NON_BLIND"
    return "PRIMARY"


def training_mask(dates: pd.DatetimeIndex, year: int, strategy: str, cfg: dict) -> np.ndarray:
    """전략별 학습 표본 위치 (dates 는 유효 수익률 날짜). 검정연도 이후 날짜는 어떤 전략에도 들어가지 않는다."""
    first = cfg["folds"]["initial_train_calendar_year"]
    pre = np.asarray(dates < pd.Timestamp(f"{year}-01-01"))
    if strategy == "expanding":
        return pre
    if strategy == "trailing_2y":
        return pre & np.asarray(dates >= pd.Timestamp(f"{year - 2}-01-01"))
    if strategy == "frozen_2019":
        return np.asarray(dates < pd.Timestamp(f"{first + 1}-01-01"))
    raise ValueError(strategy)


def strategy_state(year: int, strategy: str, cfg: dict) -> str:
    """구조적으로 정해지는 전략 상태 (계산 전)."""
    first = cfg["folds"]["initial_train_calendar_year"]
    if strategy == "expanding":
        return "COMPUTE"
    if strategy == "trailing_2y":
        if year - first < 2:
            return "SKIP_INSUFFICIENT_HISTORY"
        return "IDENTICAL_TO_EXPANDING" if year - first == 2 else "COMPUTE"
    if strategy == "frozen_2019":
        return "IDENTICAL_TO_EXPANDING" if year == first + 1 else "COMPUTE"
    raise ValueError(strategy)


def inner_split(n: int, cfg: dict) -> tuple[int, int]:
    n_train = round(cfg["folds"]["inner_train_fraction"] * n)
    return n_train, n - n_train


def build_fold(ticker: str, returns: pd.Series, year: int, strategy: str, cfg: dict) -> AnnualFold:
    """returns: 공통 거래일 index (NaN 포함). 유효값만 학습에 쓴다."""
    valid = returns.dropna()
    dates = pd.DatetimeIndex(valid.index)
    test = dates[(dates >= pd.Timestamp(f"{year}-01-01")) & (dates < pd.Timestamp(f"{year + 1}-01-01"))]
    state = strategy_state(year, strategy, cfg)
    if state.startswith("SKIP"):
        return AnnualFold(ticker, year, strategy, None, None, None, None, 0, 0, 0, len(test), state)
    tr = dates[training_mask(dates, year, strategy, cfg)]
    n_tr, n_val = inner_split(len(tr), cfg)
    status = year_status(year, cfg)
    if n_tr < cfg["folds"]["min_inner_train_n"] or n_val < cfg["folds"]["min_inner_val_n"]:
        status = "INSUFFICIENT_HISTORY"
    if len(test) == 0:
        status = "NO_TEST_DATA"
    if state == "IDENTICAL_TO_EXPANDING":
        status = "IDENTICAL_TO_EXPANDING"
    return AnnualFold(
        ticker=ticker,
        test_year=year,
        history_strategy=strategy,
        train_start=tr[0] if len(tr) else None,
        train_end=tr[-1] if len(tr) else None,
        test_start=test[0] if len(test) else None,
        test_end=test[-1] if len(test) else None,
        n_history=len(tr),
        n_inner_train=n_tr,
        n_inner_val=n_val,
        n_test=len(test),
        status=status,
    )
