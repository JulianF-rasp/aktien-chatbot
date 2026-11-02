import argparse
import os
import re

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

parser = argparse.ArgumentParser(description="Sendet eine Paper-Kauforder für eine Aktie.")
parser.add_argument(
    "symbol",
    nargs="?",
    help="Aktien-Ticker, zum Beispiel MSFT oder SAP.DE",
)
args = parser.parse_args()

load_dotenv()

symbol = (args.symbol or input("Aktien-Ticker eingeben: ")).strip().upper()
if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
    parser.error("Ungültiger Ticker. Erlaubt sind Buchstaben, Zahlen, Punkte und Bindestriche.")

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")
if not api_key or not secret_key:
    parser.error("ALPACA_API_KEY oder ALPACA_SECRET_KEY fehlt in der .env-Datei.")

client = TradingClient(
    api_key,
    secret_key,
    paper=True
)

order = MarketOrderRequest(
    symbol=symbol,
    qty=1,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY
)

confirm = input(f"Simulierte Kauforder für 1 {symbol}-Aktie senden? (ja/nein): ")

if confirm.strip().casefold() == "ja":
    result = client.submit_order(order)
    print("Paper-Order gesendet!")
    print("Order-ID:", result.id)
    print("Status:", result.status)
    print("Aktie:", result.symbol)
    print("Stückzahl:", result.qty)
else:
    print("Order abgebrochen.")