"""Swing-Trading V2: Indikatoren und Signale, keine Broker-Orders."""
import pandas as pd


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Erwartet Datumsindex und Spalten open/high/low/close/volume."""
    x = df.copy().sort_index()
    x.columns = [str(c).lower() for c in x.columns]
    for c in ('open', 'high', 'low', 'close'):
        if c not in x.columns:
            raise ValueError(f'Spalte fehlt: {c}')
        x[c] = pd.to_numeric(x[c], errors='coerce')
    x = x.dropna(subset=['open', 'high', 'low', 'close'])
    x = x[~x.index.duplicated(keep='last')]
    for n in (20, 50, 200):
        x[f'ema{n}'] = x['close'].ewm(span=n, adjust=False, min_periods=n).mean()
    prev_close = x['close'].shift(1)
    tr = pd.concat([x['high'] - x['low'], (x['high'] - prev_close).abs(),
                    (x['low'] - prev_close).abs()], axis=1).max(axis=1)
    x['atr14'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    # Wichtig: heutiges Hoch darf nicht im Ausbruchslevel enthalten sein.
    x['prior20high'] = x['high'].shift(1).rolling(20).max()
    x['trend'] = (x['close'] > x['ema200']) & (x['ema20'] > x['ema50'])
    x['breakout'] = x['close'] > x['prior20high']
    # Nur frischer Ausbruch, keine wiederholten Einstiege bei anhaltendem Signal.
    x['entry_signal'] = x['trend'] & x['breakout'] & ~x['breakout'].shift(1).fillna(False).astype(bool)
    x['exit_signal'] = x['close'] < x['ema50']
    return x


def spy_market_filter(spy: pd.DataFrame) -> pd.Series:
    x = prepare(spy)
    return (x['close'] > x['ema200']).fillna(False)
