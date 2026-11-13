# Trading-System – Projektstruktur und Modulübersicht

**Status:** Zielarchitektur für die schrittweise Entwicklung
**Ansatz:** Modularer Python-Monolith, zunächst US-Aktien/ETFs und Alpaca Paper Trading
**Team:** Zwei Entwickler – A (Daten, Analyse, Signale, Backtesting), B (Risiko, Broker, Betrieb)

## 1. Fachliche Modulstruktur

```text
trading-system/
├── data/
│   ├── stock_client.py           # US-Aktien/ETFs, zunächst Alpaca-Daten
│   ├── stock3_client.py          # Optional, keine MVP-Abhängigkeit
│   ├── forex_client.py           # Spätere Forex-Marktdaten
│   ├── crypto_client.py          # Spätere Krypto-Marktdaten
│   └── news_client.py            # Optionale Nachrichtenquellen
├── analysis/
│   ├── technical.py              # Indikatoren, z. B. ATR
│   ├── market_regime.py          # Marktfilter, z. B. SPY
│   ├── sentiment.py              # Optionale Nachrichtenanalyse
│   └── machine_learning.py       # Spätere optionale ML-Modelle
├── signals/
│   ├── signal_generator.py       # Strategie in TradingSignal überführen
│   ├── signal_validation.py      # Datenfrische, Plausibilität, Duplikate
│   └── signal_scoring.py         # Optionale Signalbewertung
├── risk/
│   ├── position_sizing.py        # Positionsgröße anhand Kapital und Stop
│   ├── stop_loss.py              # Stop-Berechnung und -Regeln
│   └── risk_manager.py           # Limits, Kill Switch, Freigabe
├── execution/
│   ├── exchange_client.py        # Broker-Adapter, zunächst Alpaca Paper
│   └── order_manager.py          # Order-Lebenszyklus und Brokerabgleich
├── backtesting/
│   ├── engine.py                 # Reproduzierbarer Portfolio-Backtest
│   └── performance.py            # Rendite, Drawdown, Benchmark, Kosten
├── dashboard/                    # Anzeige, keine eigene Orderlogik
├── core/
│   ├── models.py                 # MarketBar, TradingSignal, OrderIntent
│   ├── config.py                 # Paper-Modus und Risikoparameter
│   └── storage.py                # SQLite-Speicherung
├── monitoring/                   # Logs, Alarme, Healthchecks
├── tests/                        # Modul- und Integrationstests
└── main.py                       # Unabhängiger Scheduler/Trading-Runner
```

Diese Struktur beschreibt die fachlichen Bausteine und Verantwortlichkeiten des Trading-Projekts. Sie ist eine Zielarchitektur; Module werden schrittweise ergänzt, wenn ihre Anforderungen und Schnittstellen festgelegt sind.

## 2. Datenfluss und Verantwortlichkeiten

```text
Datenanbieter → data → analysis → signals → risk → execution → Alpaca Paper
                     ↘ backtesting ↗           ↘ monitoring / dashboard
               core/models + core/storage als gemeinsame Grundlage
```

- **Data & Quant (A):** Daten, Analyse, Signale und Backtesting.
- **Risk & Platform (B):** Risiko, Ausführung, Speicherung, Monitoring und Betrieb.
- **Gemeinsam:** Datenverträge, Schnittstellen, Integrationstests und Dashboard-Abnahme.
- **Architekturregel:** Nur `execution` darf freigegebene Paper-Orders senden. Dashboard, Analyse, KI und Signalgenerierung platzieren keine Brokerorders direkt.

### Gemeinsame Datenverträge

| Modell | Mindestfelder | Übergabe |
|---|---|---|
| `MarketBar` | Symbol, OHLCV, Zeitstempel, Intervall, Quelle | `data` → `analysis` |
| `TradingSignal` | ID, Symbol, Strategieversion, BUY/SELL/HOLD, Zeitstempel, Begründung, Stop-Vorschlag | `signals` → `risk` |
| `OrderIntent` | Signal-ID, Konto, Symbol, Richtung, Stückzahl, Ordertyp, Risikofreigabe | `risk` → `execution` |

Der Ordermanager protokolliert Zustände wie `CREATED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED` und `REJECTED`. Wiederholte Verarbeitung derselben Signal-ID darf keine Doppelorder auslösen. Nach Neustarts werden Orders und Positionen mit dem Broker abgeglichen.

## 3. Entwicklungsreihenfolge

### Sprint 1 – Baseline und Schnittstellen

- Bestehende Strategie und Backtest sichern und reproduzierbar dokumentieren.
- Daten-, Modell- und Strategie-Schnittstellen festlegen.
- Tests für Indikatoren, Signale, Look-ahead-Bias und Datenqualität erstellen.
- Brokerzugriff von Strategie und Oberfläche trennen.
- Paper-only-Konfiguration und Geheimnisschutz absichern.

### Sprint 2 – Datenpipeline und Speicherung

- Marktdatenadapter, Normalisierung und Datenfrische ergänzen.
- SQLite-Speicherung und Persistenztests einführen.
- Fehlende, doppelte oder unvollständige Kerzen erkennen.

### Sprint 3 – Strategie, Backtest und Risiko

- Strategie-Signale integrieren und Backtest/Performancevergleich ergänzen.
- Positionsgrößen, Stops, Exposure-Limits, Verlustlimits und Kill Switch implementieren.
- Ungültige Signale und Grenzüberschreitungen sicher ablehnen.

### Sprint 4 – Paper-Ausführung

- Signale nur aus abgeschlossenen Kerzen erzeugen.
- Alpaca-Paper-Orders, Statusverarbeitung, Idempotenz und Brokerabgleich ergänzen.
- Timeout-, Neustart- und Teilfüllungsszenarien testen.

### Sprint 5 – Überwachter Paper-Betrieb

- Dashboard für Signale, Risiko und Performance bereitstellen.
- Unabhängigen Runner, Monitoring, Alarmierung und Instanzschutz betreiben.
- Mehrwöchigen Paper-Test ohne kritische Ausführungsfehler dokumentieren.

### Optionale Erweiterungen

- Weitere Datenanbieter und Broker nur über austauschbare Adapter integrieren.
- Forex, Krypto und zusätzliche Intervalle nur bei tatsächlichem Bedarf ergänzen.
- Stock3 ist optional und kein MVP-Kriterium.
- ML/Sentiment erst nach belastbarer regelbasierter Baseline und messbarem Mehrwert untersuchen.

## 4. Vorläufige Paper-Risikogrenzen

| Grenze | Startwert |
|---|---:|
| Risiko pro Trade | 0,25 % |
| Geplantes Gesamtrisiko | 1,0 % |
| Maximaler Positionsanteil | 20 % |
| Maximale offene Positionen | 3 |
| Tagesverlustgrenze | 1,0 % |
| Wochenverlustgrenze | 2,5 % |
| Veraltete Marktdaten oder ungeklärter Brokerstatus | Neue Orders sperren |
| Echtgeldhandel | Nicht Teil des MVP |

Diese Werte sind Entwicklungsparameter und keine garantierten Verlustobergrenzen.

## 5. Abnahmekriterien

Das MVP ist erst fertig, wenn Datenqualität geprüft, Signale reproduzierbar, Backtests frei von Look-ahead-Bias, Risikoprüfungen vollständig und Orderausführungen idempotent sind. Brokerabgleich, Monitoring und mehrwöchiger Paper-Betrieb müssen ebenfalls nachgewiesen sein. Automatisierte Tests laufen ohne Brokerzugriff; Geheimnisse werden weder committet noch protokolliert.
