"""Performancekennzahlen fuer abgeschlossene Trades und Equity-Kurve."""
from __future__ import annotations
import pandas as pd


def summarize(trades: pd.DataFrame, equity: pd.DataFrame) -> dict:
    if equity.empty:
        raise ValueError("Equity-Kurve leer")
    initial = float(equity.iloc[0]["equity"])
    final = float(equity.iloc[-1]["equity"])
    # Die erste Equity-Zeile wird nach dem ersten Handelstag geschrieben:
    # Trades werden fruehestens am zweiten Tag ausgefuehrt.
    series = equity["equity"].astype(float)
    dd = series / series.cummax() - 1
    wins = trades.loc[trades["pnl"] > 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    losses = trades.loc[trades["pnl"] < 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    gross_loss = abs(float(losses.sum()))
    gross_win = float(wins.sum())
    return {
        "start_equity": round(initial, 2), "end_equity": round(final, 2),
        "return_pct": round((final / initial - 1) * 100, 3),
        "max_drawdown_pct": round(float(dd.min()) * 100, 3),
        "closed_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if len(trades) else 0.0,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else (None if not gross_win else "inf"),
        "realized_pnl": round(float(trades["pnl"].sum()), 2) if not trades.empty else 0.0,
        "open_positions": int(equity.iloc[-1]["positions"]),
    }
