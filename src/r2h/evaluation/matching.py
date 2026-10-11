"""경보 ↔ 정답 사건 매칭 (사건 수준 평가).

규칙 (v0.1 제안 — 값은 실험 config 로 명시하고, 교수·4조 합의 전 확정이 아니다):
1. **cooldown**: 같은 ticker 에서 직전에 *유지된* 경보로부터 ``cooldown`` 거래일 이내의 경보는 ``SUPPRESSED``
   (실시간으로도 구현 가능한 규칙이라 매칭 전에 적용한다).
2. **매칭 창**: 사건 e 에 대해 [start − pre_tolerance, start + max_delay] (거래일 위치 기준).
3. 한 경보가 여러 사건 창에 들면, 아직 탐지되지 않은 사건 중 start 가 가장 가까운 사건(동률이면 이른 사건)에 배정.
4. 사건마다 첫 배정 경보 = ``TP`` (지연 = 경보 위치 − start 위치), 같은 사건의 이후 경보 = ``DUPLICATE`` (FP 아님).
5. 어떤 창에도 들지 않는 경보 = ``FP``. 경보가 없는 사건 = 미탐(FN).

posthoc 출력은 온라인 평가에 넣을 수 없다 (``ValueError``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ALARM_STATUS = ("TP", "DUPLICATE", "FP", "SUPPRESSED")


@dataclass(frozen=True)
class MatchConfig:
    max_delay: int
    pre_tolerance: int = 0
    cooldown: int = 0
    direction: int | None = None  # 이 방향의 사건만 평가 (None = 전체)

    def __post_init__(self) -> None:
        if self.max_delay < 0 or self.pre_tolerance < 0 or self.cooldown < 0:
            raise ValueError("max_delay, pre_tolerance, cooldown must be >= 0")


def _positions(calendar: pd.DatetimeIndex, dates: pd.Series, what: str) -> np.ndarray:
    pos = calendar.get_indexer(pd.DatetimeIndex(dates))
    if (pos < 0).any():
        bad = pd.DatetimeIndex(dates)[pos < 0][:5].tolist()
        raise ValueError(f"{what} dates not on the trading calendar: {bad}")
    return pos


def match_alarms(
    signals: pd.DataFrame, events: pd.DataFrame, calendar: pd.DatetimeIndex, config: MatchConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """반환 (alarms, events): 경보별 상태표, 사건별 탐지 여부·지연 표."""
    if (signals["mode"] != "online").any():
        raise ValueError("posthoc signals cannot be scored with the online event-matching protocol")
    if not calendar.is_monotonic_increasing or calendar.has_duplicates:
        raise ValueError("calendar must be strictly increasing")
    ev = events if config.direction is None else events[events["direction"] == config.direction]
    al = signals.loc[signals["is_alarm"], ["ticker", "signal_at", "score"]].sort_values(
        ["ticker", "signal_at"]
    )

    alarm_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for ticker in sorted(set(al["ticker"]) | set(ev["ticker"])):
        a = al[al["ticker"] == ticker].reset_index(drop=True)
        e = ev[ev["ticker"] == ticker].sort_values("event_start").reset_index(drop=True)
        apos = _positions(calendar, a["signal_at"], "alarm")
        epos = _positions(calendar, e["event_start"], "event_start")
        detected_by: dict[int, int] = {}
        last_kept = None
        for i, p in enumerate(apos.tolist()):
            row: dict[str, object] = {
                "ticker": ticker,
                "signal_at": a["signal_at"].iat[i],
                "score": a["score"].iat[i],
                "event_id": None,
                "delay": np.nan,
            }
            if last_kept is not None and p - last_kept <= config.cooldown:
                row["status"] = "SUPPRESSED"
                alarm_rows.append(row)
                continue
            last_kept = p
            lo, hi = epos - config.pre_tolerance, epos + config.max_delay
            cand = np.flatnonzero((p >= lo) & (p <= hi)).tolist()
            if not cand:
                row["status"] = "FP"
            else:
                fresh = [j for j in cand if j not in detected_by]
                pool = fresh or cand
                j = min(pool, key=lambda k: (abs(p - epos[k]), epos[k]))
                row["event_id"] = e["event_id"].iat[j]
                if j in detected_by:
                    row["status"] = "DUPLICATE"
                else:
                    detected_by[j] = int(p - epos[j])
                    row["status"] = "TP"
                    row["delay"] = detected_by[j]
            alarm_rows.append(row)
        for j in range(len(e)):
            event_rows.append(
                {
                    "ticker": ticker,
                    "event_id": e["event_id"].iat[j],
                    "event_start": e["event_start"].iat[j],
                    "detected": j in detected_by,
                    "delay": detected_by.get(j, np.nan),
                }
            )
    alarms = pd.DataFrame(alarm_rows, columns=["ticker", "signal_at", "score", "status", "event_id", "delay"])
    events_out = pd.DataFrame(event_rows, columns=["ticker", "event_id", "event_start", "detected", "delay"])
    return alarms, events_out
