# Projektdokumentation

## Umgebung einrichten

1. Eine virtuelle Umgebung erstellen und aktivieren.
2. `python -m pip install -r requirements.txt` ausführen.
3. `.env.example` nach `.env` kopieren und die benötigten API-Schlüssel lokal eintragen.

Die Datei `.env` enthält vertrauliche Werte und darf nicht ins Repository eingecheckt werden.

## Tests

Die Tests laufen ohne externe API-Aufrufe:

```bash
python -m unittest discover -s tests -v
```

## Paper-Trading

`test_alpaca.py` verwendet Alpacas Paper-Trading-Modus und fragt vor dem Senden einer Order nach einer Bestätigung. Echte Zugangsdaten gehören ausschließlich in die lokale `.env`-Datei.
