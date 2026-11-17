"""Gemeinsame, broker-unabhängige Verträge für Sprint 1.

Enthält ausschließlich Datentypen. Keine Netzwerk- oder Orderfunktionen.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def _positive(value: float, name: str) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} muss eine endliche positive Zahl sein.")


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    timestamp: datetime  # zeitbezogen, mit Zeitzone
    timeframe: str  # z. B. 1day, 15min
    source: str  # z. B. alpaca-iex
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool = True

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.source.strip() or not self.timeframe.strip():
            raise ValueError("Symbol, Datenquelle und Zeitintervall sind erforderlich.")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("MarketBar.timestamp benötigt eine Zeitzone.")
        for name in ("open", "high", "low", "close"):
            _positive(getattr(self, name), name)
        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError("volume darf nicht negativ sein.")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high ist kleiner als ein anderer OHLC-Preis.")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low ist größer als ein anderer OHLC-Preis.")


@dataclass(frozen=True)
class TradingSignal:
    signal_id: str
    symbol: str
    side: Side
    bar_date: date  # Schlusskursdatum der abgeschlossenen Tageskerze
    strategy_version: str
    reason: str
    suggested_stop: float | None = None

    def __post_init__(self) -> None:
        if not all((self.signal_id.strip(), self.symbol.strip(),
                    self.strategy_version.strip(), self.reason.strip())):
            raise ValueError("Signal-ID, Symbol, Version und Begründung dürfen nicht leer sein.")
        if self.suggested_stop is not None:
            _positive(self.suggested_stop, "suggested_stop")


@dataclass(frozen=True)
class OrderIntent:
    """Ein geplanter Auftrag, noch KEINE Broker-Order."""
    intent_id: str
    signal_id: str
    symbol: str
    side: Side
    quantity: int
    order_type: str = "market"

    def __post_init__(self) -> None:
        if self.side is Side.HOLD:
            raise ValueError("HOLD kann keine Order sein.")
        if not self.intent_id.strip() or not self.signal_id.strip() or not self.symbol.strip():
            raise ValueError("OrderIntent-IDs und Symbol dürfen nicht leer sein.")
        if self.quantity <= 0:
            raise ValueError("quantity muss positiv sein.")
        if self.order_type != "market":
            raise ValueError("In Sprint 1 werden nur Market-Order-Pläne modelliert.")
