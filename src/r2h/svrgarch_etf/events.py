"""비교 대상 사건 — Track A·EDA 의 공개 사건표 (SA_ETF ``codex/r2h-track-a@a3f9e9b``, sha256 고정).

| 사건 | 정의 | 시점 열 (D4) |
|---|---|---|
| P1 | r_t / σ_{t−1}(60) ≥ 3 (양방향, 그 ETF) | candidate_at (당일 종가에 확정) |
| P4_h{5,10,20} | 미래 h 일 누적수익률/(σ√h) ≥ 2.5 — "누적수익률 절대값 경계" (D9) | available_at |
| COMMON | EDA 공통충격일 (robust-z≥3 동반 ETF ≥ 5, universe) | candidate_at |
| C3 | 069500 대비 60일 rolling 상관 지속 부호전환 (\\|ρ\\|>0.1, 10일) — 8쌍만 | confirmed_at |
| HIVOL | 069500 20일 변동성 > expanding 75% 분위 (과거만, 최소 250관측) 국면 진입일 (D6) | 진입일 |
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from .data import REPO_ROOT

SOURCES = {
    "price_events": (
        "a3f9e9b14a6980c84d2d417c7024e97c3e0eeee5",
        "reports/r2h/research_a/a3/price_event_candidates.csv",
        "6a38e440e0a66de160007ee22888897f14d44d71660b6edf2b92cd9df84b944b",
    ),
    "corr_events": (
        "a3f9e9b14a6980c84d2d417c7024e97c3e0eeee5",
        "reports/r2h/research_a/a3/correlation_event_candidates.csv",
        "2d36800fa7e3ab27f93e97d045920ba872a83f45b705794f8bdb5567862d44d3",
    ),
}
FAMILIES = ("P1", "P4_h5", "P4_h10", "P4_h20", "COMMON", "C3", "HIVOL")


def load_source(key: str) -> pd.DataFrame:
    sha, path, expected = SOURCES[key]
    cache = REPO_ROOT / "outputs" / "cache" / f"{sha[:7]}__{path.replace('/', '__')}"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        url = f"https://raw.githubusercontent.com/Siegfriex/SA_ETF/{sha}/{path}"
        cache.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    got = hashlib.sha256(cache.read_bytes()).hexdigest()
    if got != expected:
        raise RuntimeError(f"sha256 mismatch for {key}: {got}")
    return pd.read_csv(cache, dtype={"series_id": str, "reference_series_id": str}, low_memory=False)


def event_table(close_069500: pd.Series) -> pd.DataFrame:
    """열: family, series_id (UNIVERSE = 전 종목 공통), date, direction."""
    pe = load_source("price_events")
    ce = load_source("corr_events")
    parts = []
    p1 = pe[pe.definition_id == "P1_vol_scaled"]
    parts.append(
        pd.DataFrame(
            {"family": "P1", "series_id": p1.series_id, "date": p1.candidate_at, "direction": p1.direction}
        )
    )
    for h in (5, 10, 20):
        p4 = pe[pe.definition_id == f"P4_cum_h{h}"]
        parts.append(
            pd.DataFrame(
                {
                    "family": f"P4_h{h}",
                    "series_id": p4.series_id,
                    "date": p4.available_at,
                    "direction": p4.direction,
                }
            )
        )
    cs = pe[pe.definition_id == "P5_common_shock"]
    parts.append(
        pd.DataFrame(
            {"family": "COMMON", "series_id": "UNIVERSE", "date": cs.candidate_at, "direction": cs.direction}
        )
    )
    c3 = ce[
        (ce.definition_id == "C3_sign_regime")
        & (ce.parameter_set == '{"band": 0.1, "persist": 10}')
        & (ce.method == "pearson")
        & (ce.window.astype(str) == "60")
    ]
    parts.append(
        pd.DataFrame(
            {"family": "C3", "series_id": c3.series_id, "date": c3.confirmed_at, "direction": c3.direction}
        )
    )
    hv = high_vol_entries(close_069500)
    parts.append(pd.DataFrame({"family": "HIVOL", "series_id": "UNIVERSE", "date": hv, "direction": 0}))
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out.drop_duplicates().reset_index(drop=True)


def high_vol_flag(close: pd.Series, window: int = 20, q: float = 0.75, min_obs: int = 250) -> pd.Series:
    """20일 연환산 변동성이 그 시점까지의 분포의 q 분위를 넘는가 (분위는 t−1 까지 값으로만)."""
    vol = np.log(close).diff().rolling(window).std() * np.sqrt(252)
    thr = vol.expanding(min_periods=min_obs).quantile(q).shift(1)
    return (vol > thr).fillna(False)


def high_vol_entries(close: pd.Series) -> pd.DatetimeIndex:
    f = high_vol_flag(close)
    return pd.DatetimeIndex(f.index[f & ~f.shift(1, fill_value=False)])


def positions(index: pd.DatetimeIndex, dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """날짜 → index 위치 (index 밖 날짜는 버린다)."""
    pos = index.get_indexer(pd.DatetimeIndex(dates))
    return np.unique(pos[pos >= 0])


def family_dates(events: pd.DataFrame, family: str, ticker: str) -> pd.DatetimeIndex:
    e = events[(events.family == family) & (events.series_id.isin([ticker, "UNIVERSE"]))]
    return pd.DatetimeIndex(e["date"])


def resolve_root(path: str | Path | None = None) -> Path:
    return Path(path) if path else REPO_ROOT
