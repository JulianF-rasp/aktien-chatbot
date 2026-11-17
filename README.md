# Aktien-Chatbot

Streamlit-Prototyp für Aktieninformationen und KI-gestützte Analysen sowie ein separates Alpaca-Paper-Trading-Testskript.

## Einrichtung

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Trage benötigte Zugangsdaten ausschließlich lokal in `.env` ein. `cp -n` überschreibt keine bereits vorhandene `.env`-Datei. `.env` wird von Git ignoriert.

## Starten

```bash
streamlit run app.py
```

Der manuelle Paper-Trading-Test `test_alpaca.py` kann eine simulierte Kauforder absenden und fragt vorher nach Bestätigung. Nicht als automatisierten Test ausführen.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Projektübersicht

Die zentrale [Architektur und Ordnerstruktur](trading-system-architektur.md) steht im Repo-Root. Anforderungen und Sprintplanung sind in [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) dokumentiert.
