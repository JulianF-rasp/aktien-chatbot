"""Backtest fuer gespeicherte Tageskerzen, kein Brokerzugriff.

Mac: ./.venv/bin/python -m scripts.run_backtest
"""
from __future__ import annotations
import json
import argparse
from pathlib import Path
import pandas as pd
from trading_bot.backtesting.engine import SYMBOLS, run_backtest, BacktestConfig
from trading_bot.backtesting.performance import summarize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "backtest_results"


def load(symbol: str) -> pd.DataFrame:
    file = DATA / f"{symbol}_1day.csv"
    df = pd.read_csv(file)
    df.columns = [str(c).lower() for c in df.columns]
    date_column = next((c for c in ("timestamp_ny", "date", "timestamp") if c in df.columns), None)
    if date_column is None:
        raise ValueError(f"{file}: Datumsspalte fehlt")
    # Alpaca-Tageskerzen: ISO-Datum als reines lokales Handelsdatum erhalten.
    df.index = pd.to_datetime(df[date_column].astype(str).str.slice(0, 10), errors="raise")
    df = df.drop(columns=[date_column]).sort_index()
    if df.index.has_duplicates:
        raise ValueError(f"{file}: doppelte Handelstage")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Portfolio-Backtest")
    parser.add_argument("--scenario", choices=["baseline-usd", "planning-25k-usd"],
                        default="baseline-usd")
    args = parser.parse_args()
    if args.scenario == "planning-25k-usd":
        cfg = BacktestConfig(initial_cash=25_000.0, risk_per_trade=.0025,
                             max_positions=3, max_total_risk_fraction=.01,
                             max_invested_fraction=.60)
        prefix = "planning_25k_usd"
    else:
        cfg = BacktestConfig()
        prefix = "baseline_usd"
    prices = {s: load(s) for s in SYMBOLS}
    spy = load("SPY")
    trades, equity = run_backtest(prices, spy, cfg)
    metrics = summarize(trades, equity)
    OUTPUT.mkdir(exist_ok=True, parents=True)
    trades.to_csv(OUTPUT / f"{prefix}_trades.csv", index=False)
    equity.to_csv(OUTPUT / f"{prefix}_equity.csv", index=False)
    (OUTPUT / f"{prefix}_summary.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Berichte: backtest_results/{prefix}_trades.csv, {prefix}_equity.csv, {prefix}_summary.json")
    print("Keine Broker-Orders ausgefuehrt.")


if __name__ == "__main__":
    main()
