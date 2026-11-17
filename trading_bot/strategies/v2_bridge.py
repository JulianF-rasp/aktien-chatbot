"""Adapter für die BISHERIGE strategy_v2.py (nicht verändern).

Erzeugt nur Signale aus Daten lokaler CSVs. Keine Broker-/Orderaufrufe.
"""
from datetime import date
from pathlib import Path
from collections.abc import Collection
import pandas as pd

from trading_bot.data.csv_loader import load_daily_csv
from trading_bot.models import TradingSignal, Side

WATCHLIST = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL")


def evaluate_prepared(
    rows: dict[str, pd.Series], market_is_positive: bool,
    bar_date: date, held_symbols: Collection[str] = (),
) -> list[TradingSignal]:
    """Deterministische Zuordnung vorberechneter V2-Indikatoren zu Signalen."""
    held = set(held_symbols)
    result = []
    for symbol, row in sorted(rows.items()):
        if symbol in held:
            side = Side.SELL if bool(row["exit_signal"]) else Side.HOLD
            reason = "EMA50-Ausstieg" if side is Side.SELL else "Position halten"
        elif market_is_positive and bool(row["entry_signal"]):
            side = Side.BUY
            reason = "Neuer V2-Ausbruch mit positivem SPY-Filter"
        else:
            side = Side.HOLD
            reason = "Marktfilter oder Einstiegssignal nicht erfüllt"
        # Signal-ID stabil über mehrere Läufe – wichtig gegen Doppelorders in späteren Sprints.
        result.append(TradingSignal(
            signal_id=f"swing-v2:{bar_date.isoformat()}:{symbol}:{side.value}",
            symbol=symbol, side=side, bar_date=bar_date,
            strategy_version="swing-v2", reason=reason,
        ))
    return result


def signals_from_saved_csv(
    root: str | Path = ".", held_symbols: Collection[str] = (),
    symbols: Collection[str] = WATCHLIST,
) -> list[TradingSignal]:
    # Bestehende V2 unverändert verwenden. Import hier, damit Contract-Tests offline laufen.
    from strategy_v2 import prepare, spy_market_filter

    data_dir = Path(root) / "data"
    prices = {symbol: prepare(load_daily_csv(data_dir / f"{symbol}_1day.csv"))
              for symbol in symbols}
    spy = prepare(load_daily_csv(data_dir / "SPY_1day.csv"))
    if not prices:
        raise ValueError("Watchlist darf nicht leer sein.")
    latest = [df.index[-1] for df in [*prices.values(), spy] if not df.empty]
    if len(latest) != len(prices) + 1 or len(set(latest)) != 1:
        raise ValueError("Fehlende oder unterschiedlich aktuelle Tageskerzen – Signale gesperrt.")
    day = latest[0]
    if len(spy) < 220 or any(len(df) < 220 for df in prices.values()):
        raise ValueError("Für EMA200 mindestens 220 Tageskerzen erforderlich.")
    filt = spy_market_filter(load_daily_csv(data_dir / "SPY_1day.csv"))
    if day not in filt.index:
        raise ValueError("SPY-Filter kann nicht dem Signalzeitpunkt zugeordnet werden.")
    rows = {symbol: df.loc[day] for symbol, df in prices.items()}
    return evaluate_prepared(rows, bool(filt.loc[day]), day, held_symbols)
