import re


_SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")


def is_valid_symbol(symbol: str) -> bool:
    """Prüft ein bereits normalisiertes Aktiensymbol."""
    return _SYMBOL_PATTERN.fullmatch(symbol) is not None
