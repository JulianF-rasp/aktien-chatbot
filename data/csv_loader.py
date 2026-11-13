from pathlib import Path

import pandas as pd


def load_csv(file_path: str | Path) -> pd.DataFrame:
    """Lädt eine CSV-Datei in einen pandas-DataFrame."""
    return pd.read_csv(file_path)
