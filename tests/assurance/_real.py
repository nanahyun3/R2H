"""A 레인 독립 검증 공용 도구 — r2h 코드를 쓰지 않고 원자료에서 수익률을 다시 만든다.

data/raw 가 없으면 이 모듈을 쓰는 테스트는 skip 한다 (CI·공개 저장소에는 원시 시세가 없다).
네트워크 경로를 쓰지 않는다. 쓰기는 하지 않는다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "research" / "t12_annual_expanding_v2" / "results"
REFERENCE = ROOT / "research" / "svr_garch_cusum_etf" / "reference_close_sha256.csv"
END = "2026-10-02"
# 독립 상수 — etf/data.py 의 DQ_EXCLUDE 와 같은 셀이어야 한다 (PROTOCOL_LOCK L1)
DQ = {"261240": ("2019-03-14", "2019-03-15")}


def have_raw() -> bool:
    ref = pd.read_csv(REFERENCE, dtype=str)
    return RAW.is_dir() and all((RAW / f"{t}.csv").exists() for t in ref["ticker"])


def tickers() -> list[str]:
    return list(pd.read_csv(REFERENCE, dtype=str)["ticker"])


def close_hash_ok(t: str) -> bool:
    ref = pd.read_csv(REFERENCE, dtype=str).set_index("ticker")
    f = pd.read_csv(RAW / f"{t}.csv", dtype=str)
    f = f[f["Date"] <= END]
    body = "\n".join(f["Date"] + "," + f["Close"])
    return hashlib.sha256(body.encode()).hexdigest() == ref.loc[t, "close_sha256"]


def returns_panel() -> pd.DataFrame:
    """공통 거래일 · 100·Δlog Close · DQ NaN — 독립 구현."""
    cols = {}
    for t in tickers():
        f = pd.read_csv(RAW / f"{t}.csv", dtype=str)
        f = f[f["Date"] <= END]
        cols[t] = pd.Series(f["Close"].astype(float).to_numpy(), index=pd.to_datetime(f["Date"]))
    close = pd.concat(cols, axis=1, join="inner").sort_index()
    r = 100.0 * np.log(close).diff().iloc[1:]
    for t, days in DQ.items():
        r.loc[pd.to_datetime(list(days)), t] = np.nan
    return r


def array_hash16(x: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, dtype="<f8")).tobytes()).hexdigest()[:16]
