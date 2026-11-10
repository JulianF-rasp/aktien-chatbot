# Sprint 1 – Projektgrundlage

## Ziel

Eine nachvollziehbare Basis für den Aktien-Chatbot und den Alpaca-Paper-Trading-Test schaffen: Python-Abhängigkeiten festhalten, Symbolprüfung testen und Unit-Tests automatisch bei Pushes und Pull Requests ausführen.

## Enthalten

- `trading_bot/`: wiederverwendbare Trading-Hilfsfunktionen
- `tests/`: Unit-Tests ohne externe API-Aufrufe
- `docs/`: Hinweise zu Einrichtung, Tests und Paper-Trading
- `.github/workflows/tests.yml`: CI-Workflow für die Unit-Tests
- `pyproject.toml` und `requirements.txt`: Projektmetadaten und Installation
- `.env.example`: Vorlage ohne echte Zugangsdaten

## Lokal testen

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Für den Chatbot oder Alpaca-Test die benötigten Schlüssel in eine lokale `.env`-Datei übernehmen. Keine Zugangsdaten in Git committen.
