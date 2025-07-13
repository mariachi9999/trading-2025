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
import yfinance as yf

from shared import analizar_indicadores, enviar_alerta, enviar_email, get_log_sheet, get_tickers, registrar_log_externo

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
TICKER_SHEET_NAME = "Stocks_Tickers"
ALERT_DESTINATIONS = ["email"]
RSI_THRESHOLD = 30
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
oportunidades_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Stocks_Oportunidades")
cierres_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Stocks_Cierres")
posiciones_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Stocks_Posiciones")

# Binance setup
exchange = ccxt.binance()

log_sheet = get_log_sheet("Stocks_Log")

def get_accion_ohlcv(ticker):
    try:
        df = yf.download(ticker, period="100d", interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
          raise ValueError(f"No se pudo obtener información para el ticker: {ticker}")
                # Aplanar columnas si hay MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Date": "timestamp"
        }, inplace=True)
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        # print(df.tail())
        logging.info(f"Datos OHLCV obtenidos para {ticker} (acciones)")
        return df
    except Exception as e:
        logging.error(f"Error obteniendo datos de {ticker}: {e}")
        registrar_log_externo("ERROR", f"Error al obtener OHLCV de {ticker}: {e}",log_sheet)
        return pd.DataFrame()

def stocks_ejecutar_agente():
    inicio = time.time()
    logging.info("Ejecutando agente de stocks...")
    registrar_log_externo("INFO", "Ejecutando agente...",log_sheet)
    tickers = get_tickers(sheet)
    for ticker in tickers:
        logging.info(f"Analizando ticker: {ticker}")
        registrar_log_externo("INFO", f"Analizando ticker: {ticker}",log_sheet)
        df = get_accion_ohlcv(ticker)
        if df.empty:
            msg = f"No se obtuvieron datos para {ticker}"
            logging.warning(msg)
            registrar_log_externo("WARNING", msg,log_sheet)
            continue
        if analizar_indicadores(df, ticker,log_sheet,posiciones_sheet,cierres_sheet):
            actual = df.iloc[-1]
            enviar_alerta(ticker, actual,log_sheet,oportunidades_sheet)
    
    if "email" in ALERT_DESTINATIONS:
        mensaje = f"🧠 Agente ejecutado correctamente. Total de acciones analizados: {len(tickers)}.\n"
        mensaje += "No se detectaron nuevas oportunidades."  # Podés mejorar el resumen dinámicamente
        enviar_email(mensaje,log_sheet)
    
    fin = time.time()
    duracion = fin - inicio
    mensaje = f"Ejecución finalizada. Duración total: {duracion:.2f} segundos"
    logging.info(mensaje)
    registrar_log_externo("INFO", mensaje,log_sheet)
    logging.info("Ejecución del agente finalizada.")
    registrar_log_externo("INFO", "Ejecución del agente finalizada.",log_sheet)

# def main():
#     schedule.every().day.at("21:00").do(ejecutar_agente)
#     while True:
#         schedule.run_pending()
#         time.sleep(60)

if __name__ == "__main__":
    stocks_ejecutar_agente()
    # main()
    # enviar_email("Esto es una prueba de envío desde el bot.")
