"""Gezielte Regressionstests für den A3/ECO-A2-Audit (offline, keine Broker)."""
import numpy as np
import pandas as pd
import pytest
from trading_bot.backtesting import engine


def bars(n=210):
    idx = pd.bdate_range('2025-01-01', periods=n)
    c = np.linspace(100, 120, n)
    return pd.DataFrame({'open': c, 'high': c+1, 'low': c-1,
                         'close': c, 'volume': np.full(n, 1000)}, index=idx)


def fake_signals(monkeypatch, entry_days=(-2,), atr=2.0, exit_days=()):
    def make(df):
        out = df.copy()
        out['entry_signal'] = False
        out['exit_signal'] = False
        out['atr14'] = atr
        for day in entry_days:
            out.loc[out.index[day], 'entry_signal'] = True
        for day in exit_days:
            out.loc[out.index[day], 'exit_signal'] = True
        return out
    monkeypatch.setattr(engine, 'prepare', make)
    monkeypatch.setattr(engine, 'spy_market_filter', lambda df: pd.Series(True, index=df.index))


def test_missing_calendar_day_fails_closed(monkeypatch):
    fake_signals(monkeypatch)
    stock = bars().drop(bars().index[35])
    with pytest.raises(ValueError, match='Handelstage'):
        engine.run_backtest({'AAPL': stock}, bars())


@pytest.mark.parametrize('col,val', [('close', float('inf')), ('open', float('nan')),
                                     ('high', -10.0), ('volume', -1.0)])
def test_invalid_bars_rejected(monkeypatch, col, val):
    fake_signals(monkeypatch)
    a = bars()
    a.loc[a.index[35], col] = val
    with pytest.raises(ValueError):
        engine.run_backtest({'AAPL': a}, bars())


def test_duplicate_dates_rejected(monkeypatch):
    fake_signals(monkeypatch)
    a = bars()
    a.index = a.index.where(np.arange(len(a)) != 40, a.index[39])
    with pytest.raises(ValueError, match='Datumsindex'):
        engine.run_backtest({'AAPL': a}, bars())


def test_nonpositive_stop_rejects_entry(monkeypatch):
    fake_signals(monkeypatch, atr=100.0)
    _, eq = engine.run_backtest({'AAPL': bars()}, bars())
    assert (eq.positions == 0).all()


def test_cost_inclusive_stop_risk_budget(monkeypatch):
    fake_signals(monkeypatch, atr=0.12)
    cfg = engine.BacktestConfig(initial_cash=25000, risk_per_trade=.0025,
                                cost_bps=200, max_position_fraction=1.0)
    a = bars()
    a.loc[a.index[-1], 'low'] = a.loc[a.index[-1], 'open'] - 0.05
    _, eq = engine.run_backtest({'AAPL': a}, bars(), cfg)
    assert eq.iloc[-1]['positions'] == 1
    # Infer shares from open position valuation at final close (no extra price changes).
    op = bars().iloc[-1]['open']
    qty = round(eq.iloc[-1]['positions_value'] / op)
    stop = op - cfg.stop_atr_multiplier * 0.12
    risk_per_share = op * 1.02 - stop * 0.98
    assert qty * risk_per_share <= 25000 * .0025 + 1e-7


def test_portfolio_limits(monkeypatch):
    fake_signals(monkeypatch, atr=1)
    cfg = engine.BacktestConfig(initial_cash=25000, risk_per_trade=.0025,
                                max_positions=3, max_total_risk_fraction=.01,
                                max_invested_fraction=.60)
    data = {s: bars() for s in ('AAPL','MSFT','NVDA','AMZN','GOOGL')}
    _, eq = engine.run_backtest(data, bars(), cfg)
    assert eq.iloc[-1].positions <= 3
    assert eq.iloc[-1].positions_value <= 25000*.60 + .01


def test_next_day_entry_and_gap_stop(monkeypatch):
    fake_signals(monkeypatch, entry_days=(-3,), atr=1)
    a = bars()
    a.loc[a.index[-1], ['open','high','low','close']] = [90,91,89,90]
    trades, eq = engine.run_backtest({'AAPL':a}, bars())
    assert eq.iloc[-3].positions == 0
    assert eq.iloc[-2].positions == 1
    assert trades.iloc[0]['reason'] == 'ATR_STOP'
    assert trades.iloc[0]['exit_price'] == 90


def test_invalid_config():
    with pytest.raises(ValueError):
        engine.BacktestConfig(initial_cash=float('nan'))
    with pytest.raises(ValueError):
        engine.BacktestConfig(max_positions=0)
