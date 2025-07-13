import json
import os
import gspread
import yfinance as yf
import logging
import pytz
from datetime import datetime
from google.oauth2.service_account import Credentials

from shared import get_tickers


# Obtener la variable de entorno
raw_json = os.getenv("GOOGLE_CREDS_JSON")

if raw_json is None:
    raise ValueError("La variable de entorno GOOGLE_CREDS_JSON no está definida.")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
# Obtener el JSON desde variable de entorno
creds_dict = json.loads(raw_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open("AI_Oportunidades_Mercado").worksheet("Stocks_Tickers")

def evaluar_riesgo_accion(ticker: str) -> dict:
    """
    Evalúa el riesgo de manipulación de una acción según Market Cap, volumen y beta.
    Si marketCap es 0 o None, se ignora ese criterio.
    Devuelve un dict con las métricas y nivel de riesgo.
    """
    try:
        data = yf.Ticker(ticker).info
        market_cap = data.get("marketCap", 0)
        avg_volume = data.get("averageVolume", 0)
        beta = data.get("beta", 1)

        criterios_utilizados = []

        riesgo = "BAJO"

        if market_cap and market_cap < 300_000_000:
            riesgo = "ALTO"
            criterios_utilizados.append("market_cap < 300M")
        elif market_cap and market_cap < 2_000_000_000:
            riesgo = "MODERADO"
            criterios_utilizados.append("market_cap < 2B")

        if avg_volume < 500_000:
            riesgo = "ALTO"
            criterios_utilizados.append("avg_volume < 500K")
        elif avg_volume < 1_000_000 and riesgo != "ALTO":
            riesgo = "MODERADO"
            criterios_utilizados.append("avg_volume < 1M")

        if beta > 2:
            riesgo = "ALTO"
            criterios_utilizados.append("beta > 2")
        elif beta > 1.5 and riesgo != "ALTO":
            riesgo = "MODERADO"
            criterios_utilizados.append("beta > 1.5")

        resultado = {
            "ticker": ticker,
            "market_cap": market_cap,
            "avg_volume": avg_volume,
            "beta": beta,
            "riesgo": riesgo,
            "criterios_utilizados": ", ".join(criterios_utilizados) if criterios_utilizados else "N/A"
        }

        logging.info(f"[{ticker}] Riesgo: {riesgo} | MC={market_cap}, Vol={avg_volume}, Beta={beta}")
        return resultado

    except Exception as e:
        logging.error(f"Error al evaluar riesgo de {ticker}: {e}")
        return {
            "ticker": ticker,
            "error": str(e)
        }


def guardar_riesgo_en_sheets(sheet_client, datos: list[dict], nombre_hoja="Riesgo"):
    """
    Guarda una lista de dicts con evaluación de riesgo en una hoja de Google Sheets.
    Si no existe la hoja, la crea.
    """
    try:
        spreadsheet = sheet_client.open("AI_Oportunidades_Mercado")
        try:
            hoja_riesgo = spreadsheet.worksheet(nombre_hoja)
        except:
            hoja_riesgo = spreadsheet.add_worksheet(title=nombre_hoja, rows=5000, cols=10)
            hoja_riesgo.append_row(["Fecha", "Ticker", "Market Cap", "Avg Volume", "Beta", "Riesgo"])

        zona_arg = pytz.timezone("America/Argentina/Buenos_Aires")
        fecha = datetime.now(zona_arg).strftime("%Y-%m-%d %H:%M:%S")

        nuevas_filas = []
        for item in datos:
            if "error" in item:
                continue  # O podés guardar errores si querés
            nuevas_filas.append([
                fecha,
                item["ticker"],
                item["market_cap"],
                item["avg_volume"],
                item["beta"],
                item["riesgo"]
            ])

        if nuevas_filas:
            hoja_riesgo.append_rows(nuevas_filas, value_input_option="RAW")

    except Exception as e:
        logging.error(f"Error al guardar riesgo en Sheets: {e}")


if __name__ == "__main__":
    tickers = [t for t in get_tickers(sheet) if isinstance(t, str) and t.strip() != ""]
    resultados = []

    for t in tickers:
        resultado = evaluar_riesgo_accion(t)
        resultados.append(resultado)

    guardar_riesgo_en_sheets(client, resultados)