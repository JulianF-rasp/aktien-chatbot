"""Backtestregression ohne Netzwerk oder Broker."""
import numpy as np
import pandas as pd
import pytest
from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.backtesting.performance import summarize


def prices(n=260, breakout=False):
    dates = pd.bdate_range('2025-01-01', periods=n)
    close = np.linspace(100, 150, n)
    if breakout:
        close[-3] += 15
        close[-2] += 16
        close[-1] += 17
    return pd.DataFrame({
        'open':close.copy(), 'high':close+1, 'low':close-1,
        'close':close, 'volume':np.ones(n)*1000,
    }, index=dates)


def test_no_trade_on_signal_day(monkeypatch):
    from trading_bot.backtesting import engine
    a = prices()
    b = prices()
    def fake_prepare(df):
        x = df.copy()
        x['entry_signal'] = False
        x['exit_signal'] = False
        x['atr14'] = 2.0
        x.loc[x.index[-2], 'entry_signal'] = True
        return x
    monkeypatch.setattr(engine, 'prepare', fake_prepare)
    monkeypatch.setattr(engine, 'spy_market_filter', lambda df: pd.Series(True, index=df.index))
    trades, equity = run_backtest({'AAPL':a}, b)
    # Einstieg erfolgt erst am letzten Tag: keine Vorwegnahme des Signals.
    assert equity.iloc[-2]['positions'] == 0
    assert equity.iloc[-1]['positions'] == 1
    assert trades.empty


def test_spy_filter_blocks_entries(monkeypatch):
    from trading_bot.backtesting import engine
    a = prices()
    def fake_prepare(df):
        x = df.copy()
        x['entry_signal'] = True
        x['exit_signal'] = False
        x['atr14'] = 2.0
        return x
    monkeypatch.setattr(engine, 'prepare', fake_prepare)
    monkeypatch.setattr(engine, 'spy_market_filter', lambda df: pd.Series(False, index=df.index))
    trades, equity = run_backtest({'AAPL':a}, a)
    assert trades.empty
    assert (equity['positions'] == 0).all()


def test_stop_gap_fills_at_open(monkeypatch):
    from trading_bot.backtesting import engine
    a = prices()
    # Entry signal on penultimate-2 day -> buy penultimate day;
    # following day opens below stop, conservative gap fill.
    a.loc[a.index[-1], ['open','high','low','close']] = [90, 91, 89, 90]
    def fake_prepare(df):
        x = df.copy()
        x['entry_signal'] = False
        x['exit_signal'] = False
        x['atr14'] = 2.0
        x.loc[x.index[-3], 'entry_signal'] = True
        return x
    monkeypatch.setattr(engine, 'prepare', fake_prepare)
    monkeypatch.setattr(engine, 'spy_market_filter', lambda df: pd.Series(True, index=df.index))
    trades, equity = run_backtest({'AAPL':a}, prices())
    assert len(trades) == 1
    assert trades.iloc[0]['reason'] == 'ATR_STOP'
    assert trades.iloc[0]['exit_price'] == 90


def test_position_limit(monkeypatch):
    from trading_bot.backtesting import engine
    a = prices()
    def fake_prepare(df):
        x = df.copy()
        x['entry_signal'] = False
        x['exit_signal'] = False
        x['atr14'] = 0.1
        x.loc[x.index[-2], 'entry_signal'] = True
        return x
    monkeypatch.setattr(engine, 'prepare', fake_prepare)
    monkeypatch.setattr(engine, 'spy_market_filter', lambda df: pd.Series(True, index=df.index))
    _, equity = run_backtest({'AAPL':a}, a)
    # Maximal 20% des Equity am Entry-Open inkl. Kosten (Tagesbewegung kann Wert danach verschieben)
    assert equity.iloc[-1]['positions_value'] <= 10_000.01


def test_performance():
    trades = pd.DataFrame([{'pnl': 10.0}, {'pnl': -5.0}])
    equity = pd.DataFrame({'equity':[100.,110.,105.], 'positions':[0,0,0]})
    d = summarize(trades, equity)
    assert d['profit_factor'] == 2
    assert d['max_drawdown_pct'] == pytest.approx(-4.545, abs=0.001)
