"""Einfacher Swing-Backtest pro Aktie; keine echten oder Paper-Orders.

Signale werden nach Tagesschluss berechnet und frühestens am nächsten
Handelstag zum Eröffnungskurs ausgeführt. Pro Aktie separates Testkapital.
Annahmen: Long-only, ganze Stücke, 0,10 % Slippage pro Ausführung,
1 USD pauschale Orderkosten. Ein fixer ATR-Stop wird beim Einstieg gesetzt.
"""
from pathlib import Path
import pandas as pd
from strategy import calculate_indicators, generate_signal, DATA_DIR, SYMBOLS

START_CAPITAL = 10_000.0  # PRO Aktie, kein gemeinsames Portfolio
SLIPPAGE = 0.001
ORDER_FEE = 1.0
MAX_ALLOCATION = 0.95
OUTPUT_DIR = Path(__file__).resolve().parent / "backtest_results"


def backtest_one(symbol: str) -> dict:
    path = DATA_DIR / f"{symbol}_1day.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} fehlt. Bitte zuerst market_data.py starten.")
    raw = pd.read_csv(path, index_col="timestamp_ny", parse_dates=["timestamp_ny"])
    df = calculate_indicators(raw)
    if len(df) < 222:
        raise ValueError("Zu wenige Tageskerzen")

    cash = START_CAPITAL
    shares = 0
    entry_price = None
    stop_price = None
    trades = []
    equity_curve = []
    buy_hold_start = None

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]  # letzter bekannter Tagesschluss
        today = df.iloc[i]     # heutige Ausführung (Open/Low)
        date = str(df.index[i])
        op = float(today["open"])
        low = float(today["low"])
        close = float(today["close"])
        if buy_hold_start is None:
            buy_hold_start = op

        if shares > 0:
            signal, reason = generate_signal(prev, has_position=True, entry_price=None)
            # Schlusskurs-Signal: Ausstieg zum nächsten Open.
            if signal == "SELL":
                fill = op * (1 - SLIPPAGE)
                cash += shares * fill - ORDER_FEE
                trades.append({"date": date, "action": "SELL", "shares": shares,
                               "price": round(fill, 4), "reason": reason})
                shares = 0
                entry_price = None
                stop_price = None
            elif stop_price is not None and low <= stop_price:
                # Bei Gap unter den Stop: höchstens Open; sonst Stoppreis.
                fill = min(op, stop_price) * (1 - SLIPPAGE)
                cash += shares * fill - ORDER_FEE
                trades.append({"date": date, "action": "SELL", "shares": shares,
                               "price": round(fill, 4), "reason": "Fixer ATR-Stop"})
                shares = 0
                entry_price = None
                stop_price = None
        else:
            signal, reason = generate_signal(prev, has_position=False)
            if signal == "BUY" and pd.notna(prev["atr14"]):
                fill = op * (1 + SLIPPAGE)
                qty = int((cash * MAX_ALLOCATION - ORDER_FEE) // fill)
                if qty > 0:
                    cash -= qty * fill + ORDER_FEE
                    shares = qty
                    entry_price = fill
                    stop_price = fill - 2 * float(prev["atr14"])
                    trades.append({"date": date, "action": "BUY", "shares": qty,
                                   "price": round(fill, 4), "reason": reason})
                    # Tages-Tief kann vor dem Einstieg liegen: kein Stop am Einstiegstag.
        equity_curve.append({"date": date, "equity": cash + shares * close})

    curve = pd.DataFrame(equity_curve)
    if curve.empty:
        raise ValueError("Keine auswertbaren Tage")
    curve["peak"] = curve["equity"].cummax().clip(lower=START_CAPITAL)
    curve["drawdown_pct"] = (curve["equity"] / curve["peak"] - 1) * 100
    final_equity = float(curve["equity"].iloc[-1])
    benchmark = (float(df["close"].iloc[-1]) / buy_hold_start - 1) * 100

    OUTPUT_DIR.mkdir(exist_ok=True)
    pd.DataFrame(trades, columns=["date", "action", "shares", "price", "reason"]).to_csv(
        OUTPUT_DIR / f"{symbol}_trades.csv", index=False)
    curve.to_csv(OUTPUT_DIR / f"{symbol}_equity.csv", index=False)
    return {
        "symbol": symbol,
        "start": str(df.index[1]),
        "end": str(df.index[-1]),
        "equity": final_equity,
        "return_pct": (final_equity / START_CAPITAL - 1) * 100,
        "drawdown_pct": float(curve["drawdown_pct"].min()),
        "buy_hold_pct": benchmark,
        "buys": sum(t["action"] == "BUY" for t in trades),
        "open_position": shares > 0,
    }


def main():
    print("SWING-BACKTEST | Tagesdaten | KEINE ORDERS")
    print("Je Aktie 10.000 USD eigenes Startkapital; kein gemeinsames Depot.")
    for symbol in SYMBOLS:
        try:
            r = backtest_one(symbol)
            print(f"{symbol}: Rendite {r['return_pct']:+7.2f}% | Buy&Hold "
                  f"{r['buy_hold_pct']:+7.2f}% | Max. Drawdown "
                  f"{r['drawdown_pct']:7.2f}% | Einstiege {r['buys']} | "
                  f"Position offen: {r['open_position']}")
        except Exception as exc:
            print(f"{symbol}: FEHLER - {exc}")
    print(f"Ergebnisse gespeichert in: {OUTPUT_DIR}")
    print("Keine Orders gesendet.")


if __name__ == "__main__":
    main()
