"""백테스트 경계 — **스키마와 검증만** (상태: SCHEMA_ONLY, 성과 수치 없음).

파이프라인 (교체 가능한 단계): signal_adapter → entry_rule → exit_rule → cost_model → performance_metrics.
이 패키지는 각 단계의 입출력 형식과 시점 규칙만 고정한다. 실제 진입·청산 규칙과 성과는 W05 담당이 이 계약 위에서
구현한다. 여기에는 어떤 ETF 성과 수치도 없다.

시점 규칙: 경보 표의 ``available_until`` ≤ ``decision_at`` < ``fill_at``. 같은 종가로 신호를 만들고 같은 종가에 체결하는
가정(fill_at == decision_at)은 허용하지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADE_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "order_id",
    "ticker",
    "signal_at",
    "decision_at",
    "fill_at",
    "side",
    "qty",
    "fill_price",
    "fee",
    "slippage",
)


class TradeContractViolation(ValueError):
    """체결 계약 위반."""


def validate_trades(trades: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in TRADE_COLUMNS if c not in trades.columns]
    if missing:
        raise TradeContractViolation(f"missing columns: {missing}")
    if (trades["decision_at"] < trades["signal_at"]).any():
        raise TradeContractViolation("decision before the signal was available")
    if (trades["fill_at"] <= trades["decision_at"]).any():
        raise TradeContractViolation("fill_at must be strictly after decision_at (no same-bar fill)")
    if not trades["side"].isin(["buy", "sell"]).all():
        raise TradeContractViolation("side must be 'buy' or 'sell'")
    if (trades["qty"] <= 0).any() or (trades["fill_price"] <= 0).any():
        raise TradeContractViolation("qty and fill_price must be positive")
    if (trades[["fee", "slippage"]] < 0).any().any():
        raise TradeContractViolation("fee and slippage must be non-negative")
    if trades["order_id"].duplicated().any():
        raise TradeContractViolation("order_id must be unique")
    return trades


def round_trip_net_return(
    gross_return: np.ndarray | float, fee_bps: float, slippage_bps: float
) -> np.ndarray:
    """단순 왕복 비용 모형: 순수익률 = (1+g)·(1−c)² − 1, c = (fee+slippage)/1e4 (진입·청산 각 1회)."""
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError("costs must be non-negative")
    c = (fee_bps + slippage_bps) / 1e4
    return (1.0 + np.asarray(gross_return, float)) * (1.0 - c) ** 2 - 1.0


__all__ = ["TRADE_COLUMNS", "TradeContractViolation", "round_trip_net_return", "validate_trades"]
