from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from trading_bot.data.csv_loader import load_daily_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY")


def check_market_data(data_dir: Path = DATA_DIR) -> list[str]:
    errors = []
    today = datetime.now(ZoneInfo("America/New_York")).date()

    print("=== PRUEFUNG UNSERER MARKTDATEN ===")

    for symbol in SYMBOLS:
        path = data_dir / f"{symbol}_1day.csv"

        try:
            frame = load_daily_csv(path)
            if len(frame) < 220:
                raise ValueError("Zu wenige Tageskerzen fuer EMA 200")

            last_timestamp = frame.index[-1]
            last_date = last_timestamp.date()
            last_close = frame["close"].iloc[-1]

            print(
                f"OK {symbol}: "
                f"{len(frame)} Kerzen | "
                f"Letzter Tag: {last_timestamp} | "
                f"Schlusskurs: {last_close:.2f}"
            )

            if (today - last_date).days > 7:
                print(
                    f"WARNUNG {symbol}: "
                    "Kursdaten moeglicherweise veraltet"
                )
        except (OSError, ValueError, pd.errors.ParserError) as error:
            errors.append(symbol)
            print(f"FEHLER {symbol}: {error}")

    return errors


def main() -> int:
    errors = check_market_data()
    print("\n=== ERGEBNIS ===")

    if errors:
        print("Fehlerhafte Instrumente:", ", ".join(errors))
        return 1

    print("Alle 6 Kursdateien erfolgreich geprueft.")
    print("Keine Orders gesendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
