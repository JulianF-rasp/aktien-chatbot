"""Prüfung der Aufgaben aus PROJECT_PLAN.md. Keine Orders, keine Secrets im Bericht.

Beispiele:
    python -m scripts.validate_task --task A1
    python -m scripts.validate_task --task B2 --online
    python -m scripts.validate_task --task ALL

PASS = technische Prüfung bestanden; REVIEW = zusätzliche lokale/manuelle Abnahme nötig;
FAIL = Prüfung fehlgeschlagen. Keine automatischen Checkbox-Änderungen.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def use_project_venv() -> None:
    project_venv = ROOT / ".venv"
    if Path(sys.prefix).resolve() == project_venv.resolve():
        return

    interpreter = project_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if interpreter.is_file():
        os.execv(
            str(interpreter),
            [str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


use_project_venv()
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY")


def test_pytest(*test_files: str) -> tuple[str, str]:
    paths = [ROOT / file for file in test_files]
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.exists()]
    if missing:
        return "REVIEW", f"Testdateien fehlen: {', '.join(missing)}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *[str(p) for p in paths]],
        cwd=ROOT, capture_output=True, text=True, timeout=150,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    last = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-8:])
    return ("PASS" if result.returncode == 0 else "FAIL"), last


def check_a1(online: bool):
    unavailable = [s for s in SYMBOLS if not (ROOT / "data" / f"{s}_1day.csv").exists()]
    if unavailable:
        return "REVIEW", "Lokale CSV-Dateien nicht vorhanden: " + ", ".join(unavailable)
    from trading_bot.data.csv_loader import load_daily_csv
    for symbol in SYMBOLS:
        frame = load_daily_csv(ROOT / "data" / f"{symbol}_1day.csv")
        if len(frame) < 220:
            return "FAIL", f"{symbol}: nur {len(frame)} Tageskerzen (<220)"
        if not frame.index.is_monotonic_increasing:
            return "FAIL", f"{symbol}: Datumsindex nicht sortiert"
    return "PASS", "Sechs CSVs gelesen, OHLCV validiert, jeweils mindestens 220 Tageskerzen"


def check_a2(online: bool):
    return test_pytest("tests/test_v2_bridge.py", "tests/test_contracts.py")


def check_a3(online: bool):
    required = ["backtest_v2.py", "strategy_v2.py", "backtest_results/v2_equity.csv", "backtest_results/v2_trades.csv"]
    missing = [p for p in required if not (ROOT / p).exists()]
    if missing:
        return "REVIEW", "Baseline-Dateien fehlen: " + ", ".join(missing)
    import pandas as pd
    curve = pd.read_csv(ROOT / "backtest_results/v2_equity.csv")
    trades = pd.read_csv(ROOT / "backtest_results/v2_trades.csv")
    if curve.empty or "equity" not in curve or "pnl_usd" not in trades:
        return "FAIL", "Backtest-Artefakte leer oder ungültig"
    return "REVIEW", (f"Baseline verfügbar: {len(curve)} Portfolio-Tage, {len(trades)} Trades. "
                      "Reproduzierbarkeit, SPY-Benchmark, Anpassungen und Annahmen manuell abnehmen.")


def check_a4(online: bool):
    result = test_pytest("tests/test_data.py", "tests/test_v2_bridge.py")
    if result[0] == "PASS":
        return "REVIEW", result[1] + "\nZusätzlich: Nachweis der Tests für Duplikate, Zeitstempel und Zukunftsdaten prüfen."
    return result


def check_b1(online: bool):
    return test_pytest("tests/test_risk.py")


def check_b2(online: bool):
    adapter = ROOT / "trading_bot/execution/alpaca_readonly.py"
    if not adapter.exists():
        return "FAIL", "Read-only-Adapter fehlt"
    content = adapter.read_text(encoding="utf-8")
    if "submit_order(" in content or "paper=True" not in content:
        return "FAIL", "Adapter enthält Orderversand oder erzwingt nicht paper=True"
    if not online:
        return "REVIEW", "Statische Prüfung OK; für realen Paper-Lesetest lokal --online verwenden (niemals in CI)."
    result = subprocess.run(
        [sys.executable, "-m", "trading_bot.execution.alpaca_readonly"],
        cwd=ROOT, capture_output=True, text=True, timeout=45,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result.returncode != 0:
        # Credentials / Kontodaten niemals in Report schreiben
        return "FAIL", "Live-Paper-Lesetest fehlgeschlagen; Fehler lokal prüfen, keine Schlüssel hochladen."
    return "PASS", "Paper-Konto erfolgreich nur lesend abgefragt; keine Order gesendet."


def check_b3(online: bool):
    if not online:
        return "REVIEW", "Kaufkraft, Positionen und offene Orders nur mit lokalen Paper-Keys prüfbar: --online"
    try:
        from trading_bot.execution.alpaca_readonly import AlpacaPaperReader
        account = AlpacaPaperReader().read_summary()
    except Exception:
        return "FAIL", "Paper-Abfrage fehlgeschlagen; lokalen Fehler und Paper-Keys prüfen."
    # read_summary() bietet equity/cash, aber keine Buying-Power an:
    return "REVIEW", (f"Paper-Abfrage OK; {len(account.held_symbols)} Position-Symbole, "
                      f"{len(account.open_order_symbols)} offene Order-Symbole. "
                      "Kaufkraft fehlt derzeit im Adaptervertrag; Aufgabe B3 noch NICHT vollständig abgenommen.")


def check_b4(online: bool):
    gitignore = ROOT / ".gitignore"
    env_example = ROOT / ".env.example"
    if not gitignore.exists() or not env_example.exists():
        return "REVIEW", ".gitignore oder .env.example fehlen"
    patterns = gitignore.read_text(encoding="utf-8").splitlines()
    normalized = {x.strip() for x in patterns if not x.lstrip().startswith("#")}
    missing = [x for x in (".env", ".venv/", "/data/", "backtest_results/") if x not in normalized]
    if missing:
        return "FAIL", "Gitignore-Einträge fehlen: " + ", ".join(missing)
    result = test_pytest("tests/test_contracts.py", "tests/test_data.py", "tests/test_risk.py", "tests/test_v2_bridge.py")
    if result[0] == "PASS":
        return "REVIEW", "Tests und Ignore-Einträge OK. Git-Index/CI und Secret-Scan separat prüfen.\n" + result[1]
    return result


def planned_task(online: bool):
    return "REVIEW", "Automatisierte Abnahmekriterien für diese spätere Sprint-Aufgabe stehen noch aus. Tests und manuelle Nachweise vor Abschluss ergänzen."


CHECKS = {
    "A1": check_a1, "A2": check_a2, "A3": check_a3, "A4": check_a4,
    "B1": check_b1, "B2": check_b2, "B3": check_b3, "B4": check_b4,
    **{task: planned_task for task in (
        "S2A1", "S2A2", "S2A3", "S2B1", "S2B2", "S2B3",
        "S3A1", "S3A2", "S3B1", "S3B2", "S3B3",
        "S4A1", "S4A2", "S4B1", "S4B2",
        "S5A1", "S5B1", "S5AB1",
    )},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Projekt-Aufgaben validieren")
    parser.add_argument("--task", choices=[*CHECKS, "ALL"], required=True)
    parser.add_argument("--online", action="store_true", help="Nur lokal: lesende Alpaca-Paper-Abfrage")
    args = parser.parse_args()
    if args.online and os.environ.get("GITHUB_ACTIONS") == "true":
        parser.error("--online ist in GitHub Actions ausdrücklich gesperrt")
    tasks = [x for x in CHECKS if not x.startswith("S")] if args.task == "ALL" else [args.task]
    results = []
    for task in tasks:
        try:
            status, message = CHECKS[task](args.online)
        except ModuleNotFoundError as exc:
            status, message = "FAIL", f"Modul fehlt: {exc.name}"
        except Exception as exc:
            status, message = "FAIL", f"Prüfung fehlgeschlagen ({type(exc).__name__}); Details lokal prüfen."
        results.append({"task": task, "status": status, "message": message})
        print(f"\n[{status}] {task}\n{message}")
    report_dir = ROOT / "validation_reports"
    report_dir.mkdir(exist_ok=True)
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "online": args.online, "results": results,
              "note": "PASS belegt nur automatisierte Kriterien. Checkboxen/Abnahme bleiben manuell."}
    target = report_dir / f"{args.task.lower()}_latest.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write("## Validierung PROJECT_PLAN.md\n\n| Aufgabe | Status |\n|---|---|\n")
            for item in results:
                file.write(f"| {item['task']} | {item['status']} |\n")
            file.write("\n`REVIEW` bedeutet: zusätzliche lokale/manuelle Prüfung erforderlich.\n")
    print(f"\nBericht (ohne Secrets): {target}")
    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
