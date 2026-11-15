from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


def load_csv(file_path: str | Path) -> pd.DataFrame:
    """Lädt eine CSV-Datei in einen pandas-DataFrame."""
    return pd.read_csv(file_path)


def load_daily_csv(file_path: str | Path) -> pd.DataFrame:
    """Lädt und validiert eine Tageskurs-CSV mit timestamp_ny und OHLCV-Spalten."""
    frame = load_csv(file_path)
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    required_columns = {"timestamp_ny", "open", "high", "low", "close", "volume"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(
            f"Fehlende CSV-Spalten: {', '.join(sorted(missing_columns))}"
        )
    if frame.empty:
        raise ValueError("CSV enthält keine Kursdaten")

    timestamps = pd.to_datetime(frame.pop("timestamp_ny"), errors="coerce")
    if timestamps.isna().any():
        raise ValueError("CSV enthält ungültige Zeitstempel")
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(ZoneInfo("America/New_York"))
    else:
        timestamps = timestamps.dt.tz_convert(ZoneInfo("America/New_York"))

    frame.index = pd.DatetimeIndex(timestamps, name="timestamp_ny")
    if frame.index.has_duplicates:
        raise ValueError("CSV enthält doppelte Zeitstempel")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Kursdaten sind nicht chronologisch sortiert")

    price_columns = ["open", "high", "low", "close"]
    for column in [*price_columns, "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    numeric_values = frame[[*price_columns, "volume"]].to_numpy(dtype=float)
    if not np.isfinite(numeric_values).all():
        raise ValueError("CSV enthält fehlende oder ungültige OHLCV-Werte")

    prices = frame[price_columns]
    if (prices <= 0).any().any():
        raise ValueError("OHLC-Kurse müssen größer als null sein")
    if (frame["volume"] < 0).any():
        raise ValueError("Handelsvolumen darf nicht negativ sein")
    if (frame["high"] < frame["low"]).any():
        raise ValueError("Tageshoch darf nicht unter dem Tagestief liegen")
    if (
        (frame["open"] < frame["low"])
        | (frame["open"] > frame["high"])
        | (frame["close"] < frame["low"])
        | (frame["close"] > frame["high"])
    ).any():
        raise ValueError("Eröffnungs- und Schlusskurs müssen in der Tagesrange liegen")

    return frame
