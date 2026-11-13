import unittest

from validation import is_valid_symbol


class SymbolValidationTests(unittest.TestCase):
    def test_accepts_common_symbols(self):
        for symbol in ("AAPL", "MSFT", "SAP.DE", "BRK-B"):
            with self.subTest(symbol=symbol):
                self.assertTrue(is_valid_symbol(symbol))

    def test_rejects_invalid_symbols(self):
        for symbol in ("", "aapl", "1AAPL", "AAPL!", "A" * 16):
            with self.subTest(symbol=symbol):
                self.assertFalse(is_valid_symbol(symbol))


if __name__ == "__main__":
    unittest.main()
