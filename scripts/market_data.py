"""Quant A1: Tageskurse von Alpaca (IEX) laden und lokal zwischenspeichern.

Ablage im Repository: scripts/market_data.py
Start aus dem Projekt-Hauptordner auf macOS:
    ./.venv/bin/python -m scripts.market_data

Dieser Prozess liest ausschließlich historische Marktdaten. Keine Orders.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY")
NY_TZ = ZoneInfo("America/New_York")


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "ATT03730.env")
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        print("FEHLER: ALPACA_API_KEY und ALPACA_SECRET_KEY fehlen in .env.", file=sys.stderr)
        return 1

    # Enddatum auf den heutigen NY-Tagesanfang legen: keine laufende Tageskerze.
    today_ny = datetime.now(NY_TZ).date()
    end_ny = datetime.combine(today_ny, datetime.min.time(), tzinfo=NY_TZ)
    start_ny = end_ny - timedelta(days=1100)

    try:
        client = StockHistoricalDataClient(api_key=key, secret_key=secret)
        request = StockBarsRequest(
            symbol_or_symbols=list(SYMBOLS),
            timeframe=TimeFrame.Day,
            start=start_ny,
            end=end_ny,
            feed=DataFeed.IEX,
        )
        raw = client.get_stock_bars(request).df
    except Exception as exc:
        print(f"FEHLER beim Alpaca-Datenabruf: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if raw is None or raw.empty:
        print("FEHLER: Alpaca hat keine Tageskurse geliefert.", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []

    for symbol in SYMBOLS:
        try:
            # Alpaca liefert bei mehreren Symbolen einen MultiIndex: symbol, timestamp.
            if isinstance(raw.index, pd.MultiIndex):
                if symbol not in raw.index.get_level_values("symbol"):
                    raise ValueError("keine Kursdaten geliefert")
                frame = raw.xs(symbol, level="symbol").copy()
            else:
                if len(SYMBOLS) != 1:
                    raise ValueError("unerwartetes Antwortformat (kein Symbol-MultiIndex)")
                frame = raw.copy()

            if frame.empty:
                raise ValueError("leerer Kursdatensatz")
            frame = frame.sort_index()
            for column in ("open", "high", "low", "close", "volume"):
                if column not in frame.columns:
                    raise ValueError(f"fehlende Spalte: {column}")

            # Bei Alpaca stehen Tageskerzen üblicherweise auf 00:00 UTC.
            # Deshalb ist das UTC-DATUM der Tageskerze entscheidend, NICHT
            # die Umrechnung dieses Zeitpunkts nach New York (Vortag!).
            timestamp = pd.to_datetime(frame.index, utc=True)
            trading_days = timestamp.date
            result = frame.loc[:, ["open", "high", "low", "close", "volume"]].copy()
            result.insert(0, "timestamp_ny", [day.isoformat() for day in trading_days])
            result = result[result["timestamp_ny"] < today_ny.isoformat()]
            result = result.drop_duplicates(subset=["timestamp_ny"], keep="last")
            result = result.sort_values("timestamp_ny")

            if len(result) < 220:
                raise ValueError(f"nur {len(result)} Tageskerzen; mindestens 220 erforderlich")
            if result[["open", "high", "low", "close", "volume"]].isna().any().any():
                raise ValueError("fehlende OHLCV-Werte")
            if (result[["open", "high", "low", "close"]] <= 0).any().any():
                raise ValueError("ungültige Preise")
            if (result["volume"] < 0).any():
                raise ValueError("ungültiges Volumen")
            if (result["high"] < result[["open", "low", "close"]].max(axis=1)).any():
                raise ValueError("High-Wert ist inkonsistent")
            if (result["low"] > result[["open", "high", "close"]].min(axis=1)).any():
                raise ValueError("Low-Wert ist inkonsistent")

            # Atomar ersetzen, damit beim Fehlschlag keine halbe CSV entsteht.
            target = DATA_DIR / f"{symbol}_1day.csv"
            temporary = target.with_suffix(".csv.tmp")
            result.to_csv(temporary, index=False)
            temporary.replace(target)
            print(f"OK {symbol}: {len(result)} Tage, letzter Handelstag {result['timestamp_ny'].iloc[-1]}")
        except Exception as exc:
            problems.append(symbol)
            print(f"FEHLER {symbol}: {exc}", file=sys.stderr)

    if problems:
        print("NICHT BESTANDEN: " + ", ".join(problems), file=sys.stderr)
        return 1
    print("Alle sechs CSV-Dateien in data/ gespeichert. Keine Orders gesendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
