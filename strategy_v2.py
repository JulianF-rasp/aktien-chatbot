"""Rekonstruierte Swing-V2-Strategie (kein Original aus der Git-Historie).

Long-only; Indikatoren werden ausschließlich aus Tageskerzen berechnet.
Die Handelssignale gelten erst nach Abschluss der jeweiligen Tageskerze.
Keine Brokeranbindung, keine Orders.
"""
from __future__ import annotations

import pandas as pd

REQUIRED = ("open", "high", "low", "close", "volume")


def _check_prices(prices: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED) - set(prices.columns)
    if missing:
        raise ValueError(f"Fehlende Kursfelder: {sorted(missing)}")
    if prices.empty:
        raise ValueError("Kursdaten sind leer")
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("Handelstage muessen sortiert und eindeutig sein")
    df = prices.copy()
    for col in REQUIRED:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if df[list(REQUIRED)].isna().any().any():
        raise ValueError("NaN-Werte in Kursdaten")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Nicht-positive Kurswerte")
    if (df["volume"] < 0).any():
        raise ValueError("Negatives Volumen")
    if (df["high"] < df[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError("OHLC: high ist zu niedrig")
    if (df["low"] > df[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("OHLC: low ist zu hoch")
    return df


def prepare(prices: pd.DataFrame) -> pd.DataFrame:
    """Berechnet V2-Features ohne Lookahead.

    Eingänge: sortierter DataFrame mit open, high, low, close, volume.
    Ausgänge: EMA20/50/200, ATR14, vorheriges 20-Tage-Hoch,
    entry_signal, exit_signal. Signale gelten am Schluss des jeweiligen Tages.
    """
    df = _check_prices(prices)
    close = df["close"]
    for period in (20, 50, 200):
        df[f"ema{period}"] = close.ewm(span=period, adjust=False, min_periods=period).mean()
    prev_close = close.shift(1)
    true_range = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(),
         (df["low"] - prev_close).abs()], axis=1,
    ).max(axis=1)
    df["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["previous_20d_high"] = df["high"].shift(1).rolling(20, min_periods=20).max()
    trend = (close > df["ema200"]) & (df["ema20"] > df["ema50"]) & (df["ema50"] > df["ema200"])
    breakout = close > df["previous_20d_high"]
    # Frischer Ausbruch: Vortag war noch nicht ueber seinem damaligen 20d-Hoch.
    fresh_breakout = breakout & ~breakout.shift(1, fill_value=False)
    ready = df[["ema20", "ema50", "ema200", "atr14", "previous_20d_high"]].notna().all(axis=1)
    df["entry_signal"] = (trend & fresh_breakout & ready).fillna(False).astype(bool)
    df["exit_signal"] = (ready & (close < df["ema50"])).fillna(False).astype(bool)
    return df


def spy_market_filter(prices: pd.DataFrame) -> pd.Series:
    """SPY-Filter: Schlusskurs ueber EMA200 (bei ausreichender Historie)."""
    df = prepare(prices)
    return (df["ema200"].notna() & (df["close"] > df["ema200"])).astype(bool).rename("spy_market_positive")
