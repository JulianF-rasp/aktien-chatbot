import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from scripts.check_market_data import SYMBOLS, check_market_data


class MarketDataCheckerTests(unittest.TestCase):
    def write_market_data(self, directory: Path) -> None:
        dates = pd.bdate_range(
            end=pd.Timestamp.now(tz="America/New_York")
            .normalize()
            .tz_localize(None),
            periods=220,
        )
        frame = pd.DataFrame(
            {
                "timestamp_ny": dates.strftime("%Y-%m-%d"),
                "open": 10.0,
                "high": 12.0,
                "low": 9.0,
                "close": 11.0,
                "volume": 1000,
            }
        )

        for symbol in SYMBOLS:
            frame.to_csv(directory / f"{symbol}_1day.csv", index=False)

    def test_accepts_all_six_valid_market_files(self):
        with TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            self.write_market_data(data_dir)
            output = io.StringIO()

            with redirect_stdout(output):
                errors = check_market_data(data_dir)

        self.assertEqual(errors, [])
        for symbol in SYMBOLS:
            self.assertIn(f"OK {symbol}:", output.getvalue())

    def test_reports_missing_market_files(self):
        with TemporaryDirectory() as temporary_directory:
            output = io.StringIO()

            with redirect_stdout(output):
                errors = check_market_data(Path(temporary_directory))

        self.assertEqual(errors, list(SYMBOLS))
        self.assertIn("No such file or directory", output.getvalue())


if __name__ == "__main__":
    unittest.main()
