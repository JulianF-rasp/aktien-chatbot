"""A3: Price-only SPY buy-and-hold benchmark for the portfolio backtests.

Run from repository root: ./.venv/bin/python -m scripts.spy_benchmark
Does not submit orders or access Alpaca.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def _load_equity(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Equity-Datei fehlt: {path}")
    df = pd.read_csv(path)
    if not {'date', 'equity'}.issubset(df.columns):
        raise ValueError(f"{path}: Spalten 'date' und 'equity' erforderlich")
    df['date'] = pd.to_datetime(df['date'], errors='raise').dt.normalize()
    df['equity'] = pd.to_numeric(df['equity'], errors='raise')
    if df['date'].isna().any() or df['date'].duplicated().any() or not df['date'].is_monotonic_increasing:
        raise ValueError(f"{path}: doppelte/unsortierte/ungültige Datumswerte")
    if len(df) < 2 or not df['equity'].map(math.isfinite).all() or (df['equity'] <= 0).any():
        raise ValueError(f"{path}: Equity-Werte fehlen oder sind ungültig")
    return df.set_index('date')


def _load_spy(path: Path) -> pd.Series:
    if not path.is_file():
        raise FileNotFoundError(f"SPY-Kursdatei fehlt: {path}")
    df = pd.read_csv(path)
    date_col = next((c for c in ('timestamp_ny', 'date', 'timestamp') if c in df), None)
    if not date_col or 'close' not in df.columns:
        raise ValueError(f"{path}: Datumsspalte und 'close' erforderlich")
    dates = pd.to_datetime(df[date_col], errors='raise', utc=False)
    if isinstance(dates.dtype, pd.DatetimeTZDtype):
        dates = dates.dt.tz_localize(None)
    dates = dates.dt.normalize()
    closes = pd.to_numeric(df['close'], errors='raise')
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError(f"{path}: doppelte/unsortierte/ungültige Handelsdaten")
    if not closes.map(math.isfinite).all() or (closes <= 0).any():
        raise ValueError(f"{path}: ungültige SPY-Schlusskurse")
    return pd.Series(closes.to_numpy(dtype=float), index=pd.DatetimeIndex(dates), name='spy_close')


def _max_drawdown(values: pd.Series) -> float:
    return float((values / values.cummax() - 1).min() * 100)


def compare(equity_path: Path, spy: pd.Series, cost_bps: float = 5.0) -> dict:
    if cost_bps < 0 or cost_bps >= 10000:
        raise ValueError('cost_bps muss zwischen 0 und 10000 liegen')
    equity = _load_equity(equity_path)
    missing = equity.index.difference(spy.index)
    if len(missing):
        first = ', '.join(str(x.date()) for x in missing[:5])
        raise ValueError(f"SPY fehlt an {len(missing)} Backtest-Tagen (z. B. {first}); kein Forward-Fill")
    reference = spy.loc[equity.index]
    capital = float(equity['equity'].iloc[0])
    eq = equity['equity'].astype(float)
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        raise ValueError('Ungültiger Auswertungszeitraum')
    buy_hold = capital * reference / float(reference.iloc[0])
    cost = cost_bps / 10000.0
    # The SPY comparison assumes a hypothetical purchase at first day's close
    # and liquidation at last day's close; simple symmetric cost haircut.
    spy_net_factor = (1 - cost) / (1 + cost)
    spy_total_pct = (float(buy_hold.iloc[-1]) / capital - 1) * 100
    spy_after_cost_pct = (float(buy_hold.iloc[-1]) / capital * spy_net_factor - 1) * 100
    bot_total_pct = (float(eq.iloc[-1]) / capital - 1) * 100
    return {
        'scenario': equity_path.stem,
        'from': str(equity.index[0].date()),
        'to': str(equity.index[-1].date()),
        'calendar_days': days,
        'trading_days': len(eq),
        'bot_total_pct': bot_total_pct,
        'bot_cagr_pct': ((float(eq.iloc[-1]) / capital) ** (365.25 / days) - 1) * 100,
        'bot_max_drawdown_pct': _max_drawdown(eq),
        'spy_price_only_total_pct': spy_total_pct,
        'spy_after_roundtrip_cost_pct': spy_after_cost_pct,
        'spy_price_only_cagr_pct': ((float(buy_hold.iloc[-1]) / capital) ** (365.25 / days) - 1) * 100,
        'spy_max_drawdown_pct': _max_drawdown(buy_hold),
        'bot_minus_spy_price_only_pp': bot_total_pct - spy_total_pct,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='SPY-Preisbenchmark für A3 (keine Orders)')
    parser.add_argument('--spy', type=Path, default=ROOT / 'data' / 'SPY_1day.csv')
    parser.add_argument('--results', type=Path, default=ROOT / 'backtest_results')
    parser.add_argument('--cost-bps', type=float, default=5.0)
    args = parser.parse_args()
    spy = _load_spy(args.spy)
    paths = sorted(args.results.glob('*equity.csv'))
    if not paths:
        raise FileNotFoundError(f"Keine Equity-CSV in {args.results} gefunden")
    rows = [compare(p, spy, args.cost_bps) for p in paths]
    output = args.results / 'spy_benchmark_comparison.csv'
    pd.DataFrame(rows).to_csv(output, index=False)
    for r in rows:
        print(f"\n{r['scenario']} ({r['from']} bis {r['to']})")
        print(f"  Bot: {r['bot_total_pct']:+.3f}% gesamt, {r['bot_cagr_pct']:+.3f}% p.a., DD {r['bot_max_drawdown_pct']:.3f}%")
        print(f"  SPY: {r['spy_price_only_total_pct']:+.3f}% Preisrendite, {r['spy_price_only_cagr_pct']:+.3f}% p.a., DD {r['spy_max_drawdown_pct']:.3f}%")
        print(f"  SPY mit Modellkosten: {r['spy_after_roundtrip_cost_pct']:+.3f}%")
        print(f"  Bot minus SPY (Preisrendite): {r['bot_minus_spy_price_only_pp']:+.3f} Prozentpunkte")
    print(f"\nBericht: {output}")
    print('HINWEIS: SPY nur Kursrendite ohne Dividenden, Steuern und EUR/USD-Umrechnung.')


if __name__ == '__main__':
    main()
