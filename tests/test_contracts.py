from datetime import date, datetime, timezone
import pytest
from trading_bot.models import MarketBar, OrderIntent, Side, TradingSignal
from trading_bot.config import Settings


def test_marketbar_validates_ohlc_and_timezone():
    bar = MarketBar("AAPL", datetime(2026, 1, 5, tzinfo=timezone.utc), "1day", "alpaca-iex",
                    100, 105, 99, 103, 1000)
    assert bar.complete
    with pytest.raises(ValueError):
        MarketBar("AAPL", datetime(2026, 1, 5), "1day", "alpaca-iex",
                  100, 105, 99, 103, 1000)
    with pytest.raises(ValueError):
        MarketBar("AAPL", datetime(2026, 1, 5, tzinfo=timezone.utc), "1day", "alpaca-iex",
                  100, 101, 99, 103, 1000)


def test_live_mode_forbidden():
    with pytest.raises(ValueError):
        Settings("LIVE")
    assert Settings().mode == "DRY_RUN"


def test_hold_cannot_make_order():
    with pytest.raises(ValueError):
        OrderIntent("i1", "s1", "AAPL", Side.HOLD, 1)
    signal = TradingSignal("v2:2026-01-05:AAPL:BUY", "AAPL", Side.BUY,
                           date(2026, 1, 5), "v2", "Test")
    assert signal.side is Side.BUY
