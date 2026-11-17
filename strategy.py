"""Einfache Swing-Trading-Teststrategie. Keine Broker-Orders.

Liest die CSV-Dateien aus market_data.py und berechnet Indikatoren.
BUY/SELL sind ausschließlich Signale, keine Orderempfehlungen.
"""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL")


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(data.columns):
        raise ValueError(f"Fehlende Spalten: {sorted(required - set(data.columns))}")
    df = data.copy().sort_index()
    if len(df) < 220:
        raise ValueError("Mindestens 220 abgeschlossene Tageskerzen benötigt")
    if df[list(required)].isna().any().any():
        raise ValueError("Kursdaten enthalten fehlende Werte")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Kursdaten enthalten ungültige Preise")

    close = df["close"].astype(float)
    for period in (20, 50, 200):
        df[f"ema{period}"] = close.ewm(span=period, adjust=False, min_periods=period).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi14"] = 100 - 100 / (1 + rs)
    df.loc[(avg_loss == 0) & (avg_gain > 0), "rsi14"] = 100.0
    df.loc[(avg_loss == 0) & (avg_gain == 0), "rsi14"] = 50.0

    previous_close = close.shift(1)
    true_range = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - previous_close).abs(),
         (df["low"] - previous_close).abs()], axis=1
    ).max(axis=1)
    df["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return df


def generate_signal(latest: pd.Series, has_position: bool = False,
                    entry_price: float | None = None) -> tuple[str, str]:
    """Signal am Schluss einer abgeschlossenen Tageskerze.

    entry_price dient hier nur zur Demonstration eines statischen ATR-Stopps.
    Ein echter Stop muss später beim Einstieg gespeichert und verwaltet werden.
    """
    needed = ("close", "ema20", "ema50", "ema200", "rsi14", "atr14")
    if any(pd.isna(latest.get(col)) for col in needed):
        return "HOLD", "Indikatoren noch nicht vollständig"

    price = float(latest["close"])
    if has_position:
        if entry_price is not None:
            if entry_price <= 0:
                raise ValueError("entry_price muss positiv sein")
            if price <= entry_price - 2 * float(latest["atr14"]):
                return "SELL", "ATR-Stop (nur Schlusskursprüfung)"
        if price < float(latest["ema50"]):
            return "SELL", "Schlusskurs unter EMA50"
        return "HOLD", "Position halten"

    if (price > float(latest["ema200"])
            and float(latest["ema20"]) > float(latest["ema50"])
            and 45 <= float(latest["rsi14"]) <= 70):
        return "BUY", "Trend- und Momentumfilter erfüllt"
    return "HOLD", "Kein Einstiegssignal"


def analyze_csv(path: Path, has_position: bool = False,
                entry_price: float | None = None) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Datei fehlt: {path}. Zuerst market_data.py starten.")
    data = pd.read_csv(path, index_col="timestamp_ny", parse_dates=["timestamp_ny"])
    indicators = calculate_indicators(data)
    last = indicators.iloc[-1]
    signal, reason = generate_signal(last, has_position, entry_price)
    return {
        "symbol": path.name.replace("_1day.csv", ""),
        "date": str(indicators.index[-1]),
        "close": round(float(last["close"]), 2),
        "ema20": round(float(last["ema20"]), 2),
        "ema50": round(float(last["ema50"]), 2),
        "ema200": round(float(last["ema200"]), 2),
        "rsi14": round(float(last["rsi14"]), 2),
        "atr14": round(float(last["atr14"]), 2),
        "signal": signal,
        "reason": reason,
    }


def main() -> None:
    print("Swing-Strategie | Signale ohne Orderausführung")
    print("Hinweis: Für den Test wird angenommen, dass keine Positionen bestehen.")
    for symbol in SYMBOLS:
        try:
            result = analyze_csv(DATA_DIR / f"{symbol}_1day.csv")
            print(f"{symbol}: {result['signal']:4} | Schlusskurs {result['close']:>8.2f} | "
                  f"RSI {result['rsi14']:>5.1f} | ATR {result['atr14']:>6.2f} | "
                  f"{result['reason']}")
        except Exception as exc:
            print(f"{symbol}: FEHLER - {exc}")
    print("Keine Orders gesendet.")


if __name__ == "__main__":
    main()
