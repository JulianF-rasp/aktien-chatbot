"""Offline-Tests für strategy.py; benötigen keine API-Schlüssel."""
import unittest
import numpy as np
import pandas as pd
from strategy import calculate_indicators, generate_signal


class StrategyTests(unittest.TestCase):
    def test_indicators_are_calculated(self):
        close = np.linspace(100, 160, 260) + np.sin(np.arange(260)) * 2
        df = pd.DataFrame({
            "open": close - 0.5, "high": close + 1,
            "low": close - 1, "close": close, "volume": 10000,
        }, index=pd.date_range("2025-01-01", periods=260, freq="B"))
        result = calculate_indicators(df)
        for column in ("ema20", "ema50", "ema200", "rsi14", "atr14"):
            self.assertTrue(pd.notna(result[column].iloc[-1]), column)
        self.assertTrue(0 <= result["rsi14"].iloc[-1] <= 100)
        self.assertGreater(result["atr14"].iloc[-1], 0)

    def test_buy_signal_without_position(self):
        row = pd.Series({"close": 110, "ema20": 105, "ema50": 100,
                         "ema200": 90, "rsi14": 55, "atr14": 3})
        self.assertEqual(generate_signal(row)[0], "BUY")
        self.assertEqual(generate_signal(row, has_position=True, entry_price=100)[0], "HOLD")

    def test_sell_signal_with_position(self):
        row = pd.Series({"close": 90, "ema20": 96, "ema50": 100,
                         "ema200": 85, "rsi14": 35, "atr14": 3})
        self.assertEqual(generate_signal(row, has_position=True, entry_price=100)[0], "SELL")
        self.assertEqual(generate_signal(row, has_position=False)[0], "HOLD")

    def test_not_enough_history(self):
        df = pd.DataFrame({"open": [10], "high": [11], "low": [9],
                           "close": [10], "volume": [100]})
        with self.assertRaises(ValueError):
            calculate_indicators(df)


if __name__ == "__main__":
    unittest.main(verbosity=2)
