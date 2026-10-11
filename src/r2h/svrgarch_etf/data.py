"""T11 입력 데이터 — ETF 20종 종가 패널 (원시 시세는 저장소 밖).

얻는 방법 (우선순위):
1. 환경변수 ``ETF_RAW_DIR`` 의 ``<ticker>.csv`` (SA_ETF ``scripts/collect_raw.py`` 형식, 열 ``Date, Close`` 사용)
2. ``FinanceDataReader.DataReader(ticker, "2019-01-01", "2026-10-02")`` 로 다시 받아 ``outputs/cache/raw/`` 에 저장

어느 쪽이든 **종가 해시**(``Date,Close`` 텍스트 줄의 sha256)를 ``reference_close_sha256.csv`` 와 대조한다.
FDR 은 분배를 소급 조정하므로 나중에 받으면 종가가 바뀔 수 있다. 다르면 ``DataVersionDiffers`` 로 멈춘다
(``allow_mismatch=True`` 로 강행하면 결과에 ``DATA_VERSION_DIFFERS`` 를 표시해야 한다).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
STUDY_DIR = REPO_ROOT / "research" / "svr_garch_cusum_etf"
REFERENCE = STUDY_DIR / "reference_close_sha256.csv"
START, END = "2019-01-01", "2026-10-02"
# 261240 의 이상치 2일 (Track A dq_trim_canonical 과 같은 셀) — 수익률에서 제외한다.
DQ_EXCLUDE: dict[str, tuple[str, ...]] = {"261240": ("2019-03-14", "2019-03-15")}
KOSPI200_GROUP: tuple[str, ...] = ("069500", "102110", "122630", "114800")


class DataVersionDiffers(RuntimeError):
    """받은 종가가 기준 해시와 다르다."""


def close_sha256(frame: pd.DataFrame) -> str:
    """``Date,Close`` 원문 텍스트(문자열로 읽은 값) 줄들의 sha256."""
    body = "\n".join(frame["Date"].astype(str) + "," + frame["Close"].astype(str))
    return hashlib.sha256(body.encode()).hexdigest()


def reference() -> pd.DataFrame:
    return pd.read_csv(REFERENCE, dtype=str)


def _fetch(ticker: str, cache_dir: Path) -> Path:
    import FinanceDataReader as fdr  # optional extra: research

    path = cache_dir / f"{ticker}.csv"
    if not path.exists():
        frame = fdr.DataReader(ticker, START, END)
        frame.index.name = "Date"
        frame.to_csv(path)
    return path


@dataclass(frozen=True)
class ClosePanel:
    close: pd.DataFrame  # index=Date, columns=ticker (공통 거래일)
    source: str
    hash_ok: dict[str, bool]

    @property
    def data_version(self) -> str:
        ref = reference().set_index("ticker")["close_sha256"]
        tag = "" if all(self.hash_ok.values()) else "DATA_VERSION_DIFFERS:"
        body = "\n".join(f"{t}:{ref[t]}" for t in sorted(self.close.columns))
        return tag + hashlib.sha256(body.encode()).hexdigest()[:16]


def load_close_panel(
    raw_dir: str | Path | None = None, *, allow_mismatch: bool = False, cache_dir: str | Path | None = None
) -> ClosePanel:
    """종가 패널을 만들고 해시를 검증한다. 공통 거래일만 남긴다 (Track A 와 같은 규칙)."""
    ref = reference()
    raw_dir = raw_dir or os.environ.get("ETF_RAW_DIR") or None
    cache = Path(cache_dir) if cache_dir else REPO_ROOT / "outputs" / "cache" / "raw"
    if raw_dir is None:
        cache.mkdir(parents=True, exist_ok=True)
    cols, ok = {}, {}
    for t in ref["ticker"]:
        path = Path(raw_dir) / f"{t}.csv" if raw_dir else _fetch(t, cache)
        frame = pd.read_csv(path, dtype=str)
        frame = frame[frame["Date"] <= END]
        ok[t] = close_sha256(frame) == ref.set_index("ticker").loc[t, "close_sha256"]
        series = pd.Series(
            frame["Close"].astype(float).to_numpy(), index=pd.to_datetime(frame["Date"]), name=t
        )
        if series.index.has_duplicates:
            raise ValueError(f"{t}: duplicate dates")
        cols[t] = series
    bad = [t for t, v in ok.items() if not v]
    if bad and not allow_mismatch:
        raise DataVersionDiffers(
            f"close hash differs from reference for {bad} — data revised since 2026-10-02 snapshot"
        )
    close = pd.DataFrame(cols).sort_index().dropna()
    close.index.name = "Date"
    return ClosePanel(
        close=close, source="local raw dir (ETF_RAW_DIR)" if raw_dir else "FinanceDataReader", hash_ok=ok
    )


def percent_log_returns(close: pd.DataFrame) -> pd.DataFrame:
    """100·Δlog Close (Track B 관례). 첫 행 제거. DQ 셀은 NaN."""
    if (close <= 0).to_numpy().any():
        raise ValueError("non-positive close")
    logp = pd.DataFrame(np.log(close.to_numpy(float)), index=close.index, columns=close.columns)
    r = 100.0 * logp.diff().iloc[1:]
    for t, days in DQ_EXCLUDE.items():
        if t in r.columns:
            r.loc[pd.to_datetime(list(days)), t] = np.nan
    return r
