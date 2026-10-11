import numpy as np
import pandas as pd
import pytest

from r2h.backtest import TradeContractViolation, round_trip_net_return, validate_trades

D = pd.bdate_range("2024-01-01", periods=5)


def trade(**over):
    base = {
        "experiment_id": ["e"],
        "order_id": ["o1"],
        "ticker": ["A"],
        "signal_at": [D[0]],
        "decision_at": [D[0]],
        "fill_at": [D[1]],
        "side": ["buy"],
        "qty": [1.0],
        "fill_price": [100.0],
        "fee": [0.0],
        "slippage": [0.0],
    }
    base.update(over)
    return pd.DataFrame(base)


def test_valid_trade():
    validate_trades(trade())


@pytest.mark.parametrize(
    "over, msg",
    [
        ({"fill_at": [D[0]]}, "strictly after"),
        ({"decision_at": [D[0] - pd.Timedelta(days=1)]}, "before the signal"),
        ({"side": ["hold"]}, "side"),
        ({"qty": [0.0]}, "positive"),
        ({"fee": [-1.0]}, "non-negative"),
    ],
)
def test_fill_lag_and_field_rules(over, msg):
    with pytest.raises(TradeContractViolation, match=msg):
        validate_trades(trade(**over))


def test_round_trip_costs():
    assert round_trip_net_return(0.0, 0, 0) == 0.0
    np.testing.assert_allclose(round_trip_net_return(0.0, 10, 5), (1 - 0.0015) ** 2 - 1)
    assert round_trip_net_return(0.05, 10, 5) < 0.05
    with pytest.raises(ValueError):
        round_trip_net_return(0.0, -1, 0)
