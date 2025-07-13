# ai_agent_oportunidades/main.py
import ccxt
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
from dotenv import load_dotenv
import os
import logging
import json
from ratelimit import limits, sleep_and_retry

from shared import analizar_indicadores, enviar_alerta, enviar_email, get_log_sheet, get_tickers, registrar_log_buffer, registrar_log_externo, volcar_logs_en_sheets

load_dotenv()


# Configuración del logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agente_oportunidades.log"),
        logging.StreamHandler()
    ]
)


# ========== CONFIGURACIÓN ==========
TICKER_SHEET_NAME = "Cryptos_Tickers"
ALERT_DESTINATIONS = ["email"]
EMAIL_REMITENTE = os.getenv("EMAIL_REMITENTE")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")
EMAIL_CONTRASENA = os.getenv("EMAIL_CONTRASENA")

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
sheet = client.open("AI_Oportunidades_Mercado").worksheet(TICKER_SHEET_NAME)
oportunidades_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cryptos_Oportunidades")
cierres_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cryptos_Cierres")
posiciones_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cryptos_Posiciones")

# Binance setup
exchange = ccxt.binance()

log_sheet = get_log_sheet("Cryptos_Log")


# Binance permite 1200 requests/min (pero esto cambia por endpoint)
ONE_MINUTE = 60

@sleep_and_retry
@limits(calls=60, period=ONE_MINUTE)
def get_crypto_ohlcv(ticker):
    try:
        ohlcv = exchange.fetch_ohlcv(f"{ticker}/USDT", timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        logging.info(f"Datos OHLCV obtenidos para {ticker}")
        return df
    except Exception as e:
        logging.error(f"Error obteniendo datos de {ticker}: {e}")
        registrar_log_buffer("ERROR", f"Error al obtener OHLCV de {ticker}: {e}", ticker)
        return pd.DataFrame()

def crypto_ejecutar_agente():
    inicio = time.time()
    logging.info("Ejecutando agente de cryptos...")
    registrar_log_buffer("INFO", "Ejecutando agente...", "")
    tickers = get_tickers(sheet)
    for ticker in tickers:
        ticker = str(ticker).strip()
        try:
            logging.info(f"Analizando ticker: {ticker}")
            registrar_log_buffer("INFO", f"Analizando ticker {ticker}", ticker)
            df = get_crypto_ohlcv(ticker)
            if df.empty:
                msg = f"No se obtuvieron datos para {ticker}"
                logging.warning(msg)
                registrar_log_buffer("WARNING", "No se obtuvieron datos", ticker)
                continue
            if analizar_indicadores(df, ticker,log_sheet,posiciones_sheet,cierres_sheet):
                actual = df.iloc[-1]
                enviar_alerta(ticker, actual,log_sheet,oportunidades_sheet)
    
        except Exception as e:
            msg = f"[{ticker}] Error inesperado durante el análisis: {e}"
            logging.error(msg)
            registrar_log_buffer("error", msg, ticker)
            continue  # Importante: no dejar que se caiga todo el loop
    
    if "email" in ALERT_DESTINATIONS:
        mensaje = f"🧠 Agente ejecutado correctamente. Total de cryptos analizados: {len(tickers)}.\n"
        mensaje += "No se detectaron nuevas oportunidades."  # Podés mejorar el resumen dinámicamente
        enviar_email(mensaje,log_sheet)
    
    fin = time.time()
    duracion = fin - inicio
    mensaje = f"Ejecución finalizada. Duración total: {duracion:.2f} segundos"
    logging.info(mensaje)
    registrar_log_buffer("INFO", mensaje, "Fin")

    volcar_logs_en_sheets(log_sheet)


# def main():
#     schedule.every().day.at("21:00").do(ejecutar_agente)
#     while True:
#         schedule.run_pending()
#         time.sleep(60)

if __name__ == "__main__":
    crypto_ejecutar_agente()
    # main()
    # enviar_email("Esto es una prueba de envío desde el bot.")
