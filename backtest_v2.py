"""Portfolio-Backtest V2, ohne Broker-Zugriff. Ausführen: python backtest_v2.py"""
from pathlib import Path
import pandas as pd
from strategy_v2 import prepare, spy_market_filter

ROOT = Path(__file__).resolve().parent
SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL']
INITIAL_CASH = 50_000.0
RISK_PER_TRADE = 0.005
MAX_POSITION_FRACTION = 0.20
STOP_ATR_MULTIPLIER = 2.5
COST_BPS = 5  # 0,05 % je Ausführung: vereinfachte Slippage/Gebühren


def read_prices(symbol):
    candidates = [ROOT / 'data' / f'{symbol}_1day.csv', ROOT / f'{symbol}_1day.csv']
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        raise FileNotFoundError(f'{symbol}_1day.csv fehlt. Bitte Kursdaten für {symbol} laden.')
    df = pd.read_csv(path)
    df.columns = [str(c).lower() for c in df.columns]
    date_col = next((c for c in (
        'timestamp_ny', 'timestamp', 'date', 'datetime', 'time', 'unnamed: 0'
    ) if c in df.columns), None)
    if date_col is None:
        raise ValueError(f'{path.name}: Keine Datumsspalte gefunden: {list(df.columns)}')

    # timestamp_ny ist bereits New-York-Lokalzeit. Nicht als UTC interpretieren.
    # Für Tageskerzen genügt das Kalenderdatum aus dem Zeitstempel.
    if date_col == 'timestamp_ny':
        # Auch bei unterschiedlichen UTC-Offsets (Sommer-/Winterzeit) stabil:
        dates = pd.to_datetime(df[date_col].astype(str).str[:10], errors='coerce')
        df['_trading_date'] = dates.dt.date
    else:
        parsed = pd.to_datetime(df[date_col], utc=True, errors='coerce')
        df['_trading_date'] = parsed.dt.tz_convert('America/New_York').dt.date

    df = df.dropna(subset=['_trading_date']).set_index('_trading_date')
    df = df[~df.index.duplicated(keep='last')].sort_index()
    return prepare(df)


def execution_price(price, buy):
    return float(price) * (1 + COST_BPS / 10_000 if buy else 1 - COST_BPS / 10_000)


def run():
    prices = {s: read_prices(s) for s in SYMBOLS}
    spy = read_prices('SPY')
    spy_filter = spy_market_filter(spy)
    # Nur gemeinsame Handelstage; vermeidet Lücken zwischen Symbolen.
    days = sorted(set(spy.index).intersection(*(set(p.index) for p in prices.values())))
    if len(days) < 250:
        raise ValueError('Zu wenig gemeinsame Historie (mindestens 250 Handelstage benötigt).')
    cash = INITIAL_CASH
    positions = {}  # symbol -> {qty, entry, stop, entry_date}
    pending_buy = set()
    pending_sell = set()
    trades = []
    equity_rows = []
    for i, day in enumerate(days):
        # 1. Gestern erzeugte Signale am heutigen Open ausführen.
        for s in sorted(pending_sell):
            if s in positions:
                pos = positions.pop(s)
                price = execution_price(prices[s].loc[day, 'open'], buy=False)
                cash += pos['qty'] * price
                trades.append(dict(symbol=s, entry_date=pos['entry_date'], exit_date=day,
                                   entry_price=pos['entry'], exit_price=price, qty=pos['qty'],
                                   pnl_usd=round((price-pos['entry'])*pos['qty'], 2), reason='EMA50'))
        pending_sell.clear()
        for s in sorted(pending_buy):
            if s in positions or len(positions) >= 5:
                continue
            row = prices[s].loc[day]
            price = execution_price(row['open'], buy=True)
            atr = float(prices[s].loc[days[i-1], 'atr14']) if i else float('nan')
            if pd.isna(atr) or atr <= 0:
                continue
            stop = price - STOP_ATR_MULTIPLIER * atr
            if stop <= 0:
                continue
            equity_at_open = cash + sum(p['qty'] * float(prices[t].loc[day, 'open']) for t,p in positions.items())
            risk_budget = equity_at_open * RISK_PER_TRADE
            qty = int(min(risk_budget / (price-stop), equity_at_open * MAX_POSITION_FRACTION / price,
                          cash / price))
            if qty > 0:
                cash -= qty * price
                positions[s] = dict(qty=qty, entry=price, stop=stop, entry_date=day)
        pending_buy.clear()
        # 2. Stop-Loss auf Tageskerzen: bei Gap unter Stop zum Open, sonst zum Stop.
        for s in list(positions):
            row = prices[s].loc[day]
            pos = positions[s]
            if row['low'] <= pos['stop']:
                raw = min(float(row['open']), pos['stop'])
                price = execution_price(raw, buy=False)
                cash += pos['qty'] * price
                trades.append(dict(symbol=s, entry_date=pos['entry_date'], exit_date=day,
                                   entry_price=pos['entry'], exit_price=price, qty=pos['qty'],
                                   pnl_usd=round((price-pos['entry'])*pos['qty'], 2), reason='ATR-Stop'))
                del positions[s]
        # 3. Nach Handelsschluss neue Signale erzeugen; Ausführung erst morgen.
        if i < len(days)-1:
            market_ok = bool(spy_filter.loc[day])
            for s in SYMBOLS:
                row = prices[s].loc[day]
                if s in positions:
                    if bool(row['exit_signal']):
                        pending_sell.add(s)
                elif market_ok and bool(row['entry_signal']) and pd.notna(row['atr14']):
                    pending_buy.add(s)
        equity = cash + sum(pos['qty'] * float(prices[s].loc[day, 'close']) for s,pos in positions.items())
        equity_rows.append(dict(date=day, equity=equity, cash=cash, positions=len(positions)))
    curve = pd.DataFrame(equity_rows).set_index('date')
    curve['drawdown_pct'] = (curve['equity'] / curve['equity'].cummax() - 1) * 100
    out = ROOT / 'backtest_results'
    out.mkdir(exist_ok=True)
    pd.DataFrame(trades).to_csv(out / 'v2_trades.csv', index=False)
    curve.to_csv(out / 'v2_equity.csv')
    print(f'Zeitraum: {days[0]} bis {days[-1]}')
    print(f'Startkapital: {INITIAL_CASH:,.2f} USD')
    print(f'Endkapital: {curve.equity.iloc[-1]:,.2f} USD')
    print(f'Rendite: {(curve.equity.iloc[-1]/INITIAL_CASH-1)*100:+.2f} %')
    print(f'Max. Drawdown: {curve.drawdown_pct.min():.2f} %')
    print(f'Abgeschlossene Trades: {len(trades)}')
    print(f'Offene Positionen: {len(positions)}')
    print(f'Ergebnisse: {out}')
    print('Keine Orders gesendet.')


if __name__ == '__main__':
    run()
