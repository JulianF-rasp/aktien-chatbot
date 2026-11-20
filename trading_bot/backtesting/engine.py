"""Long-only Tageskerzen-Portfolio-Backtest ohne Brokerzugriff.

Zeitmodell:
- Signal vom Schlusskurs an Tag t wird frühestens am Open von t+1 ausgeführt.
- Ausstiegssignal ebenso am nächsten Open.
- Stop wird intraday anhand des Tages-Low simuliert; Gap durch den Stop
  führt zu Ausführung am Open statt zu einem unrealistischen Stop-Kurs.
- Fester Stop ab Einstieg; kein nachträglicher Lookahead.
- Kosten: Kostenaufschlag auf jeden Kauf, Abschlag auf jeden Verkauf.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
from typing import Mapping

import pandas as pd
from strategy_v2 import prepare, spy_market_filter

SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL")


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 50_000.0
    risk_per_trade: float = 0.005
    max_position_fraction: float = 0.20
    stop_atr_multiplier: float = 2.5
    cost_bps: float = 5.0
    max_positions: int = 5
    max_total_risk_fraction: float = 1.0
    max_invested_fraction: float = 1.0

    def __post_init__(self):
        if not math.isfinite(self.initial_cash) or self.initial_cash <= 0 or not (0 < self.risk_per_trade <= 1) or not math.isfinite(self.risk_per_trade):
            raise ValueError("Ungueltiges Startkapital oder Risiko")
        if (not (0 < self.max_position_fraction <= 1)
                or not math.isfinite(self.max_position_fraction)
                or not math.isfinite(self.stop_atr_multiplier)
                or self.stop_atr_multiplier <= 0):
            raise ValueError("Ungueltige Positionsgrenze oder ATR-Multiplikator")
        if not math.isfinite(self.cost_bps) or not (0 <= self.cost_bps < 10000):
            raise ValueError("Ungueltige Ausfuehrungskosten")
        if (not isinstance(self.max_positions, int) or isinstance(self.max_positions, bool)
                or self.max_positions < 1 or not (0 < self.max_total_risk_fraction <= 1)
                or not math.isfinite(self.max_total_risk_fraction)
                or not (0 < self.max_invested_fraction <= 1)
                or not math.isfinite(self.max_invested_fraction)):
            raise ValueError("Ungueltige Portfoliolimits")


@dataclass
class Position:
    shares: int
    entry_date: str
    entry_price: float  # roher Open-Preis, ohne Kosten
    initial_atr: float
    stop_price: float
    entry_cash_out: float  # einschliesslich Kaufkosten


def _validate_raw_bars(df: pd.DataFrame, label: str) -> None:
    """Fail-closed: ungültige Bars/Datumsindizes vor der Strategie zurückweisen."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError(f"{label}: keine Kursdaten")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"{label}: DatetimeIndex erforderlich")
    if df.index.hasnans or df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError(f"{label}: Datumsindex unsortiert, doppelt oder leer")
    required = ("open", "high", "low", "close", "volume")
    if any(col not in df.columns for col in required):
        raise ValueError(f"{label}: OHLCV-Spalten fehlen")
    bars = df.loc[:, required].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(bars.to_numpy(dtype=float)).all():
        raise ValueError(f"{label}: fehlende/unendliche Kurswerte")
    if (bars[["open", "high", "low", "close"]] <= 0).any().any() or (bars["volume"] < 0).any():
        raise ValueError(f"{label}: negative oder nicht-positive Kurswerte")
    if (bars["high"] < bars[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError(f"{label}: OHLC High unplausibel")
    if (bars["low"] > bars[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError(f"{label}: OHLC Low unplausibel")


def run_backtest(
    prices_by_symbol: Mapping[str, pd.DataFrame],
    spy_prices: pd.DataFrame,
    cfg: BacktestConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gibt (trades, equity) zurueck; erwartet ISO-Datumsindex je DataFrame."""
    cfg = cfg or BacktestConfig()
    if not prices_by_symbol:
        raise ValueError("Keine Aktienkurse")
    _validate_raw_bars(spy_prices, "SPY")
    for symbol, raw in prices_by_symbol.items():
        _validate_raw_bars(raw, symbol)
        # Kalender strikt: fehlende Bars koennen Stopps oder Ausfuehrungen verbergen.
        if not raw.index.equals(spy_prices.index):
            raise ValueError(f"{symbol}: Handelstage weichen vom SPY-Kalender ab")
    stock = {s: prepare(df) for s, df in prices_by_symbol.items()}
    spy_filter = spy_market_filter(spy_prices)

    # Nur Handelstage verwenden, an denen alle Aktien und SPY Kurse haben.
    # So werden Datenluecken nicht durch Vorwaertsfuellen kaschiert.
    dates = spy_prices.index
    for df in stock.values():
        dates = dates.intersection(df.index)
    dates = dates.sort_values()
    if len(dates) < 2:
        raise ValueError("Zu wenige gemeinsame Handelstage")

    stock = {s: df.loc[dates] for s, df in stock.items()}
    spy_filter = spy_filter.loc[dates]
    cash = float(cfg.initial_cash)
    positions: dict[str, Position] = {}
    trade_records: list[dict] = []
    equity_records: list[dict] = []
    pending_entries: dict[str, float] = {}  # Signal-ATR vom Vortag
    pending_exits: set[str] = set()
    factor = cfg.cost_bps / 10000.0
    last_close: dict[str, float] = {}

    def sell(symbol: str, date: str, raw_price: float, reason: str):
        nonlocal cash
        p = positions.pop(symbol)
        proceeds = p.shares * raw_price * (1 - factor)
        cash += proceeds
        trade_records.append({
            "symbol": symbol, "entry_date": p.entry_date, "exit_date": date,
            "shares": p.shares, "entry_price": p.entry_price,
            "exit_price": raw_price, "stop_price": p.stop_price,
            "entry_cash_out": round(p.entry_cash_out, 8),
            "exit_cash_in": round(proceeds, 8),
            "pnl": round(proceeds - p.entry_cash_out, 8), "reason": reason,
        })

    for i, dt in enumerate(dates):
        day = str(dt)[:10]
        # Vortagssignale: zuerst Exit am Open, dann neue Einstiege.
        for s in sorted(pending_exits):
            if s in positions:
                sell(s, day, float(stock[s].loc[dt, "open"]), "EMA50_EXIT")
        pending_exits.clear()

        # Risiko und Positionsgroesse anhand des bekannten gestrigen ATR.
        # Aktueller Portfoliowert zum Open nur anhand heutiger Open-Kurse.
        opening_equity = cash + sum(
            p.shares * float(stock[s].loc[dt, "open"]) for s, p in positions.items()
        )
        planned_risk = sum(
            p.shares * (p.entry_price * (1 + factor) - p.stop_price * (1 - factor))
            for p in positions.values()
        )
        invested_value = sum(
            p.shares * float(stock[s].loc[dt, "open"]) for s, p in positions.items()
        )
        for s in sorted(pending_entries):
            if s in positions or len(positions) >= cfg.max_positions:
                continue
            op = float(stock[s].loc[dt, "open"])
            atr = pending_entries[s]
            stop_distance = cfg.stop_atr_multiplier * atr
            if not (math.isfinite(atr) and atr > 0 and math.isfinite(op) and op > 0):
                continue
            stop_price = op - stop_distance
            if not math.isfinite(stop_distance) or stop_price <= 0:
                continue
            # Verlust bis zum planmaessigen Stop inkl. Kauf-/Verkaufskosten.
            # Gaps koennen dieses Budget im realen Handel ueberschreiten.
            risk_per_share = op * (1 + factor) - stop_price * (1 - factor)
            risk_budget = opening_equity * cfg.risk_per_trade
            remaining_portfolio_risk = max(0.0, opening_equity * cfg.max_total_risk_fraction - planned_risk)
            risk_shares = math.floor(min(risk_budget, remaining_portfolio_risk) / risk_per_share)
            cap_shares = math.floor((opening_equity * cfg.max_position_fraction) / (op * (1 + factor)))
            cash_shares = math.floor(cash / (op * (1 + factor)))
            invested_shares = max(0, math.floor(
                (opening_equity * cfg.max_invested_fraction - invested_value) / (op * (1 + factor))
            ))
            qty = min(risk_shares, cap_shares, cash_shares, invested_shares)
            if qty <= 0:
                continue
            outlay = qty * op * (1 + factor)
            cash -= outlay
            planned_risk += qty * risk_per_share
            invested_value += qty * op
            positions[s] = Position(
                shares=qty, entry_date=day, entry_price=op,
                initial_atr=atr, stop_price=stop_price,
                entry_cash_out=outlay,
            )
        pending_entries.clear()

        # Preisbeobachtungen des Tages fuer bestehende + neue Positionen.
        # Intraday-Stop hat Vorrang vor einem erst am Schluss bekannten Exit.
        for s in sorted(list(positions)):
            bar = stock[s].loc[dt]
            stop = positions[s].stop_price
            if float(bar["low"]) <= stop:
                sell(s, day, min(float(bar["open"]), stop), "ATR_STOP")

        last_close = {s: float(df.loc[dt, "close"]) for s, df in stock.items()}
        closing_equity = cash + sum(p.shares * last_close[s] for s, p in positions.items())
        equity_records.append({
            "date": day, "cash": round(cash, 8),
            "positions_value": round(closing_equity - cash, 8),
            "equity": round(closing_equity, 8),
            "positions": len(positions),
        })

        if i == len(dates) - 1:
            break
        # Signale nur vom heutigen Schluss; nie von morgen.
        pending_exits = {s for s in positions if bool(stock[s].loc[dt, "exit_signal"])}
        if bool(spy_filter.loc[dt]):
            pending_entries = {
                s: float(df.loc[dt, "atr14"])
                for s, df in stock.items()
                if s not in positions and bool(df.loc[dt, "entry_signal"])
                and math.isfinite(float(df.loc[dt, "atr14"]))
            }

    trades = pd.DataFrame(trade_records, columns=[
        "symbol", "entry_date", "exit_date", "shares", "entry_price",
        "exit_price", "stop_price", "entry_cash_out", "exit_cash_in", "pnl", "reason",
    ])
    equity = pd.DataFrame(equity_records)
    equity.attrs["open_positions"] = {
        s: {"shares": p.shares, "entry_date": p.entry_date, "stop_price": p.stop_price}
        for s, p in positions.items()
    }
    return trades, equity
