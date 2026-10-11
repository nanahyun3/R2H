"""입력 관측(observation) 계약 v0.1 — 일봉 OHLCV long table 검증과 as-of 절단.

long table 한 행 = (ticker, date). 필수 열은 ``REQUIRED_COLUMNS``. 검증은 값을 고치지 않고 위반을 보고한다
(정렬·중복 제거·보간을 조용히 하지 않는다). 엄격 모드에서는 위반이 있으면 ``ContractViolation`` 을 던진다.

시점 규약: ``date`` 는 거래소 현지 거래일 라벨(timezone-naive, 자정)이다. 그 날 종가 이후에만 해당 행의 값을
쓸 수 있다. 해외 자산처럼 마감 시각이 다른 시계열은 ``observed_at`` (timezone-aware) 열로 실제 이용 가능 시점을
따로 둔다 — 같은 거래일 라벨이라도 이용 가능 시점은 다를 수 있다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("ticker", "date", "adj_close", "volume")
OPTIONAL_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "observed_at", "source")
PRICE_COLUMNS: tuple[str, ...] = ("adj_close", "open", "high", "low", "close")


class ContractViolation(ValueError):
    """관측 계약 위반 (strict 검증)."""


@dataclass(frozen=True)
class ValidationReport:
    n_rows: int
    n_tickers: int
    issues: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.issues


def validate_observations(df: pd.DataFrame, *, strict: bool = True) -> ValidationReport:
    """관측 long table 을 검사한다.

    검사 항목: 필수 열, ticker 문자열(선행 0 보존), date 가 timezone-naive datetime, (ticker, date) 중복,
    ticker 안 date 오름차순, 가격 NaN·±Inf·0 이하, volume 음수·Inf, ``observed_at`` 이 있으면 timezone-aware.
    """
    issues: list[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        issues.append(f"missing required columns: {missing}")
        return _finish(df, issues, strict)

    if not (pd.api.types.is_string_dtype(df["ticker"]) or pd.api.types.is_object_dtype(df["ticker"])):
        issues.append("ticker must be string dtype (leading zeros, e.g. '069500', must survive)")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        issues.append("date must be datetime64")
    elif isinstance(df["date"].dtype, pd.DatetimeTZDtype):
        issues.append("date must be timezone-naive trading-day label; put wall-clock time in observed_at")

    dup = df.duplicated(["ticker", "date"])
    if dup.any():
        issues.append(f"duplicate (ticker, date) rows: {int(dup.sum())}")

    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        for t, g in df.groupby("ticker", sort=True):
            if not g["date"].is_monotonic_increasing:
                issues.append(f"{t}: dates not sorted ascending")

    for col in (c for c in PRICE_COLUMNS if c in df.columns):
        v = pd.to_numeric(df[col], errors="coerce").to_numpy(float)
        n_nan, n_inf, n_nonpos = int(np.isnan(v).sum()), int(np.isinf(v).sum()), int((v <= 0).sum())
        if n_nan:
            issues.append(f"{col}: {n_nan} NaN")
        if n_inf:
            issues.append(f"{col}: {n_inf} infinite")
        if n_nonpos:
            issues.append(f"{col}: {n_nonpos} non-positive (log return undefined)")

    vol = pd.to_numeric(df["volume"], errors="coerce").to_numpy(float)
    if np.isinf(vol).any() or (vol < 0).any():
        issues.append("volume: negative or infinite values")

    if "observed_at" in df.columns and not isinstance(df["observed_at"].dtype, pd.DatetimeTZDtype):
        issues.append("observed_at must be timezone-aware datetime")

    return _finish(df, issues, strict)


def _finish(df: pd.DataFrame, issues: list[str], strict: bool) -> ValidationReport:
    n_t = int(df["ticker"].nunique()) if "ticker" in df.columns else 0
    report = ValidationReport(n_rows=len(df), n_tickers=n_t, issues=tuple(issues))
    if strict and issues:
        raise ContractViolation("; ".join(issues))
    return report


def to_wide(df: pd.DataFrame, value: str = "adj_close", tickers: Iterable[str] | None = None) -> pd.DataFrame:
    """long → wide (index=date, columns=ticker). 중복이 있으면 실패한다 (pivot 이 조용히 고르지 않게)."""
    if df.duplicated(["ticker", "date"]).any():
        raise ContractViolation("duplicate (ticker, date) rows — resolve explicitly before pivoting")
    wide = df.pivot(index="date", columns="ticker", values=value).sort_index()
    wide.columns = wide.columns.astype(str)
    if tickers is not None:
        wide = wide[list(tickers)]
    return wide


def slice_as_of(df: pd.DataFrame, as_of: pd.Timestamp | str, *, time_col: str = "date") -> pd.DataFrame:
    """``as_of`` 시점까지 관측 가능한 행만 남긴다 (경계 포함). wide(index 가 날짜)와 long 모두 지원."""
    ts = pd.Timestamp(as_of)
    if time_col in df.columns:
        col = df[time_col]
        if isinstance(col.dtype, pd.DatetimeTZDtype) and ts.tzinfo is None:
            raise ValueError("as_of must be timezone-aware when the time column is timezone-aware")
        return df.loc[col <= ts]
    if isinstance(df.index, pd.DatetimeIndex):
        return df.loc[df.index <= ts]
    raise ValueError(f"no time column {time_col!r} and index is not a DatetimeIndex")
