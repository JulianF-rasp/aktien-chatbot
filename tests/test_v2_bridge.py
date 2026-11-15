from datetime import date
import pandas as pd
from trading_bot.models import Side
from trading_bot.strategies.v2_bridge import evaluate_prepared


def test_bridge_buy_sell_hold_with_same_contract():
    rows = {
        'AAPL': pd.Series({'entry_signal': True, 'exit_signal': False}),
        'MSFT': pd.Series({'entry_signal': False, 'exit_signal': True}),
        'NVDA': pd.Series({'entry_signal': True, 'exit_signal': False}),
    }
    signals = evaluate_prepared(rows, True, date(2026, 7, 1), held_symbols={'MSFT', 'NVDA'})
    assert {s.symbol: s.side for s in signals} == {
        'AAPL': Side.BUY, 'MSFT': Side.SELL, 'NVDA': Side.HOLD,
    }
    assert len({s.signal_id for s in signals}) == len(signals)
    assert evaluate_prepared(rows, True, date(2026, 7, 1), held_symbols={'MSFT', 'NVDA'}) == signals


def test_market_filter_blocks_new_buys_but_not_sells():
    rows = {
        'AAPL': pd.Series({'entry_signal': True, 'exit_signal': False}),
        'MSFT': pd.Series({'entry_signal': False, 'exit_signal': True}),
    }
    signals = evaluate_prepared(rows, False, date(2026, 7, 1), held_symbols={'MSFT'})
    assert {s.symbol: s.side for s in signals} == {'AAPL': Side.HOLD, 'MSFT': Side.SELL}
