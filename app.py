
import os
import streamlit as st
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------
# Konfiguration
# -----------------------------------

load_dotenv()

st.set_page_config(
    page_title="Aktien-Chatbot",
    page_icon="📈",
    layout="wide"
)

# OpenAI API verbinden
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error(
        "OpenAI API-Key fehlt. Bitte prüfe deine .env-Datei."
    )
    st.stop()

client = OpenAI(api_key=api_key)


# -----------------------------------
# KI-Aktienanalyse
# -----------------------------------

def aktienanalyse(prompt):
    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    return response.output_text


# -----------------------------------
# Hilfsfunktion für Kennzahlen
# -----------------------------------

def format_number(value, decimals=2):
    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"

        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


# -----------------------------------
# Benutzeroberfläche
# -----------------------------------

st.title("📈 Aktien-Chatbot")
st.write("Dein persönlicher Assistent für Aktienanalyse")

ticker = st.text_input(
    "Aktien-Ticker eingeben",
    value="AAPL",
    help="Beispiele: AAPL, MSFT, NVDA, SAP.DE"
)

if st.button("Aktie analysieren", type="primary"):

    if not ticker.strip():
        st.warning("Bitte gib einen Aktien-Ticker ein.")

    else:
        ticker = ticker.strip().upper()

        with st.spinner("Lade Aktieninformationen..."):

            try:
                # -----------------------------------
                # Aktieninformationen laden
                # -----------------------------------

                aktie = yf.Ticker(ticker)

                info = aktie.info
                historie = aktie.history(period="1y")

                if not info or not info.get("longName"):
                    st.error(
                        "Keine Unternehmensdaten gefunden. "
                        "Bitte prüfe den Ticker."
                    )
                    st.stop()

                unternehmen = info.get(
                    "longName",
                    ticker
                )

                st.header(unternehmen)

                # -----------------------------------
                # Kennzahlen anzeigen
                # -----------------------------------

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Aktueller Kurs",
                    format_number(info.get("currentPrice"))
                )

                col2.metric(
                    "Marktkapitalisierung",
                    format_number(info.get("marketCap"), 0)
                )

                col3.metric(
                    "KGV",
                    format_number(info.get("trailingPE"))
                )

                # -----------------------------------
                # Kursverlauf
                # -----------------------------------

                if not historie.empty:
                    st.subheader("Kursverlauf (1 Jahr)")
                    st.line_chart(historie["Close"])

                # -----------------------------------
                # Unternehmensbeschreibung
                # -----------------------------------

                st.subheader("Unternehmensbeschreibung")

                beschreibung = info.get(
                    "longBusinessSummary",
                    "Keine Unternehmensbeschreibung verfügbar."
                )

                st.write(beschreibung)

                # -----------------------------------
                # KI-Aktienanalyse
                # -----------------------------------

                st.subheader("KI-Aktienanalyse")

                prompt = f"""
Du bist ein sachlicher Finanzanalyst.

Analysiere das folgende Unternehmen anhand der
bereitgestellten Informationen.

Unternehmen: {unternehmen}
Ticker: {ticker}

Aktueller Kurs:
{info.get("currentPrice", "N/A")}

Marktkapitalisierung:
{info.get("marketCap", "N/A")}

KGV:
{info.get("trailingPE", "N/A")}

Umsatz:
{info.get("totalRevenue", "N/A")}

Gewinn:
{info.get("netIncomeToCommon", "N/A")}

Gewinnwachstum:
{info.get("earningsGrowth", "N/A")}

Dividendenrendite:
{info.get("dividendYield", "N/A")}

Unternehmensbeschreibung:
{beschreibung}

Erstelle eine strukturierte Analyse mit folgenden Punkten:

1. Geschäftsmodell
2. Finanzielle Kennzahlen
3. Wachstum und Chancen
4. Risiken
5. Wettbewerbsposition
6. Langfristige Perspektiven
7. Zusammenfassung

Erkläre die Kennzahlen verständlich.
Unterscheide Fakten von Einschätzungen.
Weise auf fehlende Daten hin.
Gib keine garantierten Kursprognosen ab.

Schließe mit einem Hinweis, dass die Analyse
keine Anlageberatung darstellt.
"""

                with st.spinner("KI analysiert die Aktie..."):
                    analyse = aktienanalyse(prompt)

                st.markdown(analyse)

            except Exception as e:
                st.error(
                    f"Fehler bei der Aktienanalyse: {e}"
                )
