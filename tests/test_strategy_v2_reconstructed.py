"""Offline-Tests fuer rekonstruierte V2-Strategie."""
import numpy as np
import pandas as pd
import pytest
from strategy_v2 import prepare, spy_market_filter


def prices(count=260):
    idx = pd.date_range("2025-01-02", periods=count, freq="B").date
    close = pd.Series(np.linspace(100.0, 180.0, count), index=idx)
    return pd.DataFrame({"open": close - 0.2, "high": close + 1,
                         "low": close - 1, "close": close,
                         "volume": 100000}, index=idx)


def test_indicators_warm_up_and_no_nan_signals():
    df = prepare(prices())
    assert not df["ema200"].first_valid_index() == df.index[0]
    assert df["ema200"].notna().sum() == len(df) - 199
    assert df["entry_signal"].dtype == bool
    assert df["exit_signal"].dtype == bool
    assert not df["entry_signal"].iloc[:199].any()


def test_breakout_is_fresh_not_repeated():
    df = prepare(prices())
    # Steigende Kurse koennen Ausbrueche machen, jedoch keine Endlos-BUY-Kette.
    assert not bool(df["entry_signal"].iloc[-1]) or not bool(df["entry_signal"].iloc[-2])
    assert not (df["entry_signal"] & df["entry_signal"].shift(1, fill_value=False)).any()


def test_spy_filter_returns_aligned_booleans():
    p = prices()
    filt = spy_market_filter(p)
    assert filt.index.equals(p.index)
    assert filt.dtype == bool
    assert not filt.iloc[:199].any()
    assert filt.iloc[-1]


def test_exit_on_drop_below_ema50():
    p = prices()
    p.loc[p.index[-1], ["open", "high", "low", "close"]] = [80, 81, 79, 80]
    df = prepare(p)
    assert df["exit_signal"].iloc[-1]
    assert not df["entry_signal"].iloc[-1]


def test_rejects_invalid_ohlc():
    p = prices()
    p.loc[p.index[0], "high"] = 0
    with pytest.raises(ValueError):
        prepare(p)
