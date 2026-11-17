"""Alpaca-Datenpipeline für US-Aktien (Swing-Trading, Tageskerzen).

Lädt historische OHLCV-Daten, entfernt den laufenden Handelstag,
prüft Datenqualität und speichert CSV-Dateien unter data/.
Es werden keine Orders platziert.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY"]
LOOKBACK_DAYS = 730  # Kalendertage; ca. zwei Jahre Historie
DATA_DIR = Path(__file__).resolve().parent / "data"
NY_TZ = ZoneInfo("America/New_York")


def fetch_daily_bars(client: StockHistoricalDataClient, symbol: str) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=now - timedelta(days=LOOKBACK_DAYS),
        end=now,
        feed=DataFeed.IEX,
        adjustment="raw",
    )
    bars = client.get_stock_bars(request).df
    if bars.empty:
        raise ValueError("Keine Daten erhalten")

    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(symbol, level="symbol")

    bars = bars.sort_index().copy()
    bars.index = pd.to_datetime(bars.index, utc=True)
    bars.index = bars.index.tz_convert(NY_TZ)
    bars.index.name = "timestamp_ny"

    # Der aktuelle US-Handelstag wird vorsichtshalber ausgeschlossen,
    # da seine Tageskerze noch unvollständig sein könnte.
    today_ny = now.astimezone(NY_TZ).date()
    bars = bars[bars.index.date < today_ny]

    required = ["open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in bars.columns]
    if missing:
        raise ValueError(f"Fehlende Spalten: {missing}")

    bars = bars[required].copy()
    bars = bars[~bars.index.duplicated(keep="last")]
    bars = bars.dropna(subset=required)
    valid = (
        (bars[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (bars["volume"] >= 0)
        & (bars["high"] >= bars[["open", "close", "low"]].max(axis=1))
        & (bars["low"] <= bars[["open", "close", "high"]].min(axis=1))
    )
    bars = bars.loc[valid]
    if bars.empty:
        raise ValueError("Keine gültigen, abgeschlossenen Tageskerzen")
    return bars


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY fehlen in .env")

    client = StockHistoricalDataClient(key, secret)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fehler = []

    for symbol in SYMBOLS:
        try:
            df = fetch_daily_bars(client, symbol)
            output = DATA_DIR / f"{symbol}_1day.csv"
            df.to_csv(output, index_label="timestamp_ny")
            print(
                f"OK {symbol}: {len(df)} Kerzen | "
                f"letzter Tag: {df.index[-1].date()} | "
                f"Schlusskurs: {df['close'].iloc[-1]:.2f} USD | {output}"
            )
        except Exception as exc:
            fehler.append(symbol)
            print(f"FEHLER {symbol}: {exc}")

    print("Fertig. Es wurden keine Orders gesendet.")
    if fehler:
        raise SystemExit(
            f"Download unvollstaendig: {', '.join(fehler)}. "
            "Bitte die Fehlermeldungen oben pruefen."
        )
    print("Alle sechs Tageskursdateien (einschliesslich SPY) wurden gespeichert.")


if __name__ == "__main__":
    main()
