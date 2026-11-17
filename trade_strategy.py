"""Analysiert abgeschlossene Trades aus backtest_results/*_trades.csv.

Keine Broker-Verbindung und keine Orderausführung. Kostenmodell entspricht
backtest.py: je BUY/SELL eine pauschale Ordergebühr von 1 USD; Slippage ist
bereits in den gespeicherten Ausführungspreisen enthalten.
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "backtest_results"
ORDER_FEE = 1.0


def analyze_file(path: Path) -> pd.DataFrame:
    events = pd.read_csv(path)
    required = {"date", "action", "shares", "price", "reason"}
    if not required.issubset(events.columns):
        raise ValueError(f"Fehlende Spalten in {path.name}: {sorted(required - set(events.columns))}")
    events["date"] = pd.to_datetime(events["date"], utc=True, errors="raise")
    events = events.sort_values("date", kind="stable")
    open_lots = []
    completed = []
    for _, event in events.iterrows():
        action = str(event["action"]).upper().strip()
        qty = int(event["shares"])
        price = float(event["price"])
        if qty <= 0 or price <= 0 or pd.isna(price):
            raise ValueError(f"Ungültige Stückzahl/Preis in {path.name}")
        if action == "BUY":
            open_lots.append({"date": event["date"], "qty": qty, "price": price,
                              "reason": str(event["reason"]), "fee_per_share": ORDER_FEE / qty})
        elif action == "SELL":
            remaining = qty
            if sum(lot["qty"] for lot in open_lots) < remaining:
                raise ValueError(f"SELL ohne ausreichende BUY-Position in {path.name}")
            sell_fee_per_share = ORDER_FEE / qty
            while remaining:
                lot = open_lots[0]
                matched = min(remaining, lot["qty"])
                buy_cost = matched * (lot["price"] + lot["fee_per_share"])
                sell_proceeds = matched * (price - sell_fee_per_share)
                pnl = sell_proceeds - buy_cost
                completed.append({
                    "symbol": path.name.removesuffix("_trades.csv"),
                    "entry_date": lot["date"].date().isoformat(),
                    "exit_date": event["date"].date().isoformat(),
                    "holding_days": (event["date"] - lot["date"]).days,
                    "shares": matched,
                    "entry_price": lot["price"], "exit_price": price,
                    "pnl_usd": round(pnl, 2),
                    "return_pct": round(100 * pnl / buy_cost, 2),
                    "entry_reason": lot["reason"],
                    "exit_reason": str(event["reason"]),
                })
                remaining -= matched
                lot["qty"] -= matched
                if lot["qty"] == 0:
                    open_lots.pop(0)
        else:
            raise ValueError(f"Unbekannte Aktion {action!r} in {path.name}")
    if open_lots:
        print(f"  Hinweis: {path.name}: {sum(x['qty'] for x in open_lots)} offene Aktien nicht in der Trade-Statistik.")
    return pd.DataFrame(completed)


def summarize(df: pd.DataFrame) -> None:
    if df.empty:
        print("  Keine abgeschlossenen Trades vorhanden.")
        return
    wins = df[df["pnl_usd"] > 0]
    losses = df[df["pnl_usd"] < 0]
    gross_profit = wins["pnl_usd"].sum()
    gross_loss = -losses["pnl_usd"].sum()
    factor = f"{gross_profit / gross_loss:.2f}" if gross_loss > 0 else "nicht definiert (keine Verluste)"
    print(f"  Abgeschlossene Trades: {len(df)} | Trefferquote: {len(wins) / len(df):.1%}")
    print(f"  Netto-P/L: {df['pnl_usd'].sum():+,.2f} USD | Profit Factor: {factor}")
    print(f"  Ø Gewinn: {wins['pnl_usd'].mean():+,.2f} USD" if len(wins) else "  Ø Gewinn: keine Gewinntrades")
    print(f"  Ø Verlust: {losses['pnl_usd'].mean():+,.2f} USD" if len(losses) else "  Ø Verlust: keine Verlusttrades")
    print("  Schlechteste Trades:")
    print(df.nsmallest(3, "pnl_usd")[["entry_date", "exit_date", "pnl_usd", "return_pct", "exit_reason"]].to_string(index=False))


def main() -> None:
    paths = sorted(RESULTS_DIR.glob("*_trades.csv"))
    if not paths:
        print(f"Keine Trade-Dateien gefunden in {RESULTS_DIR}. Bitte zuerst backtest.py ausführen.")
        return
    all_trades = []
    for path in paths:
        print(f"\n{path.stem.removesuffix('_trades')}:")
        try:
            df = analyze_file(path)
            summarize(df)
            if not df.empty:
                all_trades.append(df)
        except (ValueError, KeyError, pd.errors.ParserError) as exc:
            print(f"  Fehler: {exc}")
    if all_trades:
        output = pd.concat(all_trades, ignore_index=True)
        target = RESULTS_DIR / "trade_analysis.csv"
        output.to_csv(target, index=False)
        print(f"\nEinzelne abgeschlossene Trades gespeichert: {target}")
    print("Keine Orders gesendet.")


if __name__ == "__main__":
    main()
