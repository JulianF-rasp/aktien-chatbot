import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


# -----------------------------
# Einstellungen
# -----------------------------

SYMBOL = "AAPL"          # z. B. AAPL, MSFT, TSLA
LOOKBACK_DAYS = 30       # Zeitraum der Historie
DATA_FEED = DataFeed.IEX # Kostenloser IEX-Feed

# Unterstützte Intervalle:
TIMEFRAMES = {
    "5min": TimeFrame(5, TimeFrameUnit.Minute),
    "15min": TimeFrame(15, TimeFrameUnit.Minute),
    "30min": TimeFrame(30, TimeFrameUnit.Minute),
    "60min": TimeFrame(1, TimeFrameUnit.Hour),
    "240min": TimeFrame(4, TimeFrameUnit.Hour),
    "1day": TimeFrame(1, TimeFrameUnit.Day),
    "1week": TimeFrame(1, TimeFrameUnit.Week),
    "1month": TimeFrame(1, TimeFrameUnit.Month),
}


# -----------------------------
# Alpaca-Verbindung
# -----------------------------

load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

if not api_key or not secret_key:
    raise ValueError("Alpaca API-Schlüssel fehlen in der .env-Datei.")

client = StockHistoricalDataClient(api_key, secret_key)


# -----------------------------
# Kursdaten abrufen
# -----------------------------

def get_bars(symbol: str, timeframe: TimeFrame, lookback_days: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    request = StockBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=timeframe,
        start=start,
        end=end,
        feed=DATA_FEED,
    )

    bars = client.get_stock_bars(request).df

    if bars.empty:
        return pd.DataFrame()

    # MultiIndex enthält Symbol und Zeitstempel
    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(symbol, level="symbol")

    return bars


# -----------------------------
# Alle Intervalle testen
# -----------------------------

for label, timeframe in TIMEFRAMES.items():
    print("\n" + "=" * 60)
    print(f"{SYMBOL} | Intervall: {label}")
    print("=" * 60)

    try:
        data = get_bars(SYMBOL, timeframe, LOOKBACK_DAYS)

        if data.empty:
            print("Keine Daten zurückgegeben.")
            continue

        # Zeitstempel lesbar anzeigen
        data.index = pd.to_datetime(data.index, utc=True)

        print(data.tail(10).to_string())

        # Jede Zeitreihe zusätzlich als CSV speichern
        filename = f"{SYMBOL}_{label}.csv"
        data.to_csv(filename)
        print(f"\nCSV gespeichert: {filename}")

    except Exception as error:
        print(f"Fehler bei {label}: {error}")