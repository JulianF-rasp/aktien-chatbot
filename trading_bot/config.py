"""Konfiguration: Echtgeldmodus absichtlich nicht implementiert."""
from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class Settings:
    mode: str = "DRY_RUN"  # DRY_RUN = nur simulierte Entscheidungen; PAPER = nur Lesetest in Sprint 1

    def __post_init__(self) -> None:
        if self.mode not in {"DRY_RUN", "PAPER"}:
            raise ValueError("Nur TRADING_MODE=DRY_RUN oder PAPER erlaubt. LIVE ist gesperrt.")


def load_settings() -> Settings:
    return Settings(mode=environ.get("TRADING_MODE", "DRY_RUN").upper().strip())
