# ai_agent_oportunidades/main.py
import ccxt
import pandas as pd
import pandas_ta as ta
import gspread
from google.oauth2.service_account import Credentials
import schedule
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
import logging
import json
from io import StringIO

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
TICKER_SHEET_NAME = "Tickers"
ALERT_DESTINATIONS = ["email"]
RSI_THRESHOLD = 30
EMAIL_REMITENTE = os.getenv("EMAIL_REMITENTE")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")
EMAIL_CONTRASENA = os.getenv("EMAIL_CONTRASENA")

# print(EMAIL_REMITENTE)
# print(EMAIL_DESTINATARIO)
# print(EMAIL_CONTRASENA)

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
oportunidades_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Oportunidades")
cierres_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cierres")
posiciones_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Posiciones")

# Binance setup
exchange = ccxt.binance()

def get_log_sheet():
    try:
        # Intenta abrir el spreadsheet
        sh = client.open("AI_Oportunidades_Mercado")
    except gspread.SpreadsheetNotFound:
        logging.error("No se encontró la hoja 'AI_Oportunidades_Mercado'")
        raise

    try:
        # Intenta abrir la worksheet "Log"
        log_ws = sh.worksheet("Log")
        logging.info("Worksheet 'Log' encontrada.")
    except gspread.WorksheetNotFound:
        logging.warning("Worksheet 'Log' no existe. Se creará.")
        log_ws = sh.add_worksheet(title="Log", rows=1000, cols=3)
        log_ws.append_row(["Timestamp", "Nivel", "Mensaje"])

    return log_ws

log_sheet = get_log_sheet()

def registrar_log_externo(nivel, mensaje):
    zona_arg = pytz.timezone("America/Argentina/Buenos_Aires")
    timestamp = datetime.now(zona_arg).strftime("%Y-%m-%d %H:%M:%S")
    try:
        log_sheet.append_row([timestamp, nivel.upper(), mensaje])
    except Exception as e:
        logging.error(f"No se pudo registrar el log externo: {e}")


def get_tickers():
    logging.info(f"get_tickers work ok")
    return sheet.col_values(1)[1:]  # omite el encabezado

def get_ohlcv(ticker):
    try:
        ohlcv = exchange.fetch_ohlcv(f"{ticker}/USDT", timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        logging.info(f"Datos OHLCV obtenidos para {ticker}")
        return df
    except Exception as e:
        logging.error(f"Error obteniendo datos de {ticker}: {e}")
        registrar_log_externo("ERROR", f"Error al obtener OHLCV de {ticker}: {e}")
        return pd.DataFrame()

def tiene_posicion_abierta(ticker):
    try:
        rows = posiciones_sheet.get_all_values()
        for row in rows[1:]:
            if row[0] == ticker and row[5].lower() == "open":
                logging.info(f"{ticker} tiene posición abierta.")
                return True
        return False
    except Exception as e:
        logging.error(f"Error al verificar posición abierta de {ticker}: {e}")
        registrar_log_externo("ERROR", f"Error al verificar posición abierta para {ticker}: {e}")
        return False

def analizar_indicadores(df, ticker):
    
    try:
        macd = ta.macd(df['close'])
        if macd is not None and not macd.empty:
            df['macd_line'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            df['macd_hist'] = macd['MACDh_12_26_9']
        else:
            df['macd_line'] = df['macd_signal'] = df['macd_hist'] = None
    except Exception as e:
        logging.error(f"Error al calcular MACD para {ticker}: {e}")
        registrar_log_externo("ERROR", f"Error al calcular MACD para {ticker}: {e}")

    try:
        
        adx = ta.adx(df['high'], df['low'], df['close'])
        if adx is not None and not adx.empty:
            df['adx'] = adx['ADX_14']
            df['di+'] = adx['DMP_14']
            df['di-'] = adx['DMN_14']
        else:
            df['adx'] = df['di+'] = df['di-'] = None
    
    except Exception as e:
        logging.error(f"Error al calcular ADX para {ticker}: {e}")
        registrar_log_externo("ERROR", f"Error al calcular ADX para {ticker}: {e}")
        
    actual = df.iloc[-1]
    anterior = df.iloc[-2]

    condiciones_actuales = (
        actual['macd_line'] > 0 and
        actual['di+'] > actual['di-'] and
        actual['di+'] > actual['adx']
    )

    condiciones_anteriores = (
        anterior['macd_line'] > 0 and
        anterior['di+'] > anterior['di-'] and
        anterior['di+'] > anterior['adx']
    )
    
    mensaje_log_sin_emojis = (
        f"[{ticker}] Condiciones actuales: MACD={actual['macd_line']:.2f}, "
        f"DI+={actual['di+']:.2f}, DI-={actual['di-']:.2f}, ADX={actual['adx']:.2f} -> "
        f"{'Cumple' if condiciones_actuales else 'No cumple'} | "
        f"Condiciones anteriores -> {'Cumplía' if condiciones_anteriores else 'No cumplía'}"
    )

    mensaje_log_con_emojis = (
        f"[{ticker}] Condiciones actuales: MACD={actual['macd_line']:.2f}, "
        f"DI+={actual['di+']:.2f}, DI-={actual['di-']:.2f}, ADX={actual['adx']:.2f} -> "
        f"{'Cumple ✅' if condiciones_actuales else 'No cumple ❌'} | "
        f"Condiciones anteriores -> {'Cumplía ✅' if condiciones_anteriores else 'No cumplía ❌'}"
    )

    logging.info(mensaje_log_sin_emojis)
    registrar_log_externo("INFO", mensaje_log_con_emojis)

    if condiciones_actuales and not condiciones_anteriores:
        return True
    elif not condiciones_actuales and condiciones_anteriores and tiene_posicion_abierta(ticker):
        registrar_cierre(ticker, df.iloc[-2])

    return False

def oportunidad_ya_registrada(fecha, ticker):
    registros = oportunidades_sheet.get_all_values()
    for row in registros[1:]:
        if row[0].startswith(fecha[:10]) and row[1] == ticker:
            return True
    return False

def registrar_oportunidad(ticker, actual):
    zona_arg = pytz.timezone("America/Argentina/Buenos_Aires")
    fecha = datetime.now(zona_arg).strftime("%Y-%m-%d %H:%M:%S")
    if not oportunidad_ya_registrada(fecha, ticker):
        oportunidades_sheet.insert_row([
            fecha,
            ticker,
            f"{actual['macd_line']:.2f}",
            f"{actual['di+']:.2f}",
            f"{actual['di-']:.2f}",
            f"{actual['adx']:.2f}",
            f"{actual['rsi']:.2f}"
        ], index=2)
        mensaje_log = f"Oportunidad registrada para {ticker} el {fecha}"
        logging.info(mensaje_log)
        registrar_log_externo("INFO", mensaje_log)


def registrar_cierre(ticker, anterior):
    zona_arg = pytz.timezone("America/Argentina/Buenos_Aires")
    fecha = datetime.now(zona_arg).strftime("%Y-%m-%d %H:%M:%S")
    cierres_sheet.insert_row([
        fecha,
        ticker,
        f"{anterior['macd_line']:.2f}",
        f"{anterior['di+']:.2f}",
        f"{anterior['di-']:.2f}",
        f"{anterior['adx']:.2f}",
        f"{anterior['rsi']:.2f}"
    ], index=2)
    mensaje_log = f"Cierre registrado para {ticker} el {fecha}"
    logging.info(mensaje_log)
    registrar_log_externo("INFO", mensaje_log)
    enviar_email(f"🔻 Señal de cierre detectada para {ticker} el {fecha}")

def enviar_alerta(ticker, actual):
    mensaje = (
        f"⚠️ Señal de oportunidad detectada para {ticker}:\n"
        f"MACD > 0, DI+ > DI- y DI+ > ADX solo en última vela\n"
        f"Valores:\n"
        f"MACD line: {actual['macd_line']:.2f}\nDI+: {actual['di+']:.2f}\nDI-: {actual['di-']:.2f}\nADX: {actual['adx']:.2f}\nRSI: {actual['rsi']:.2f}"
    )
    if "email" in ALERT_DESTINATIONS:
        enviar_email(mensaje)
    registrar_oportunidad(ticker, actual)

def enviar_email(mensaje):
    msg = MIMEText(mensaje)
    msg["Subject"] = "Alerta de Oportunidad"
    if EMAIL_REMITENTE is not None:
        msg["From"] = EMAIL_REMITENTE
    else:
        raise ValueError("EMAIL_DESTINATARIO no puede ser None")
    if EMAIL_DESTINATARIO is not None:
        msg["To"] = EMAIL_DESTINATARIO
    else:
        raise ValueError("EMAIL_DESTINATARIO no puede ser None")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        try:
            server.starttls()
            if EMAIL_CONTRASENA is None:
                raise ValueError("EMAIL_CONTRASENA no puede ser None")
            server.login(EMAIL_REMITENTE, EMAIL_CONTRASENA)
            server.send_message(msg)
            logging.info("Correo enviado correctamente")
            registrar_log_externo("INFO", "Correo enviado correctamente")
        except Exception as e:
            print(f"[EXCEPCIÓN EMAIL] {e}")
            logging.error(f"Error al enviar email: {e}")
            registrar_log_externo("ERROR", f"Error al enviar email: {e}")


def ejecutar_agente():
    inicio = time.time()
    logging.info("Ejecutando agente...")
    registrar_log_externo("INFO", "Ejecutando agente...")
    tickers = get_tickers()
    for ticker in tickers:
        logging.info(f"Analizando ticker: {ticker}")
        registrar_log_externo("INFO", f"Analizando ticker: {ticker}")
        df = get_ohlcv(ticker)
        if df.empty:
            msg = f"No se obtuvieron datos para {ticker}"
            logging.warning(msg)
            registrar_log_externo("WARNING", msg)
            continue
        if analizar_indicadores(df, ticker):
            actual = df.iloc[-1]
            enviar_alerta(ticker, actual)
    
    if "email" in ALERT_DESTINATIONS:
        mensaje = f"🧠 Agente ejecutado correctamente. Total de tickers analizados: {len(tickers)}.\n"
        mensaje += "No se detectaron nuevas oportunidades."  # Podés mejorar el resumen dinámicamente
        enviar_email(mensaje)
    
    fin = time.time()
    duracion = fin - inicio
    mensaje = f"Ejecución finalizada. Duración total: {duracion:.2f} segundos"
    logging.info(mensaje)
    registrar_log_externo("INFO", mensaje)
    logging.info("Ejecución del agente finalizada.")
    registrar_log_externo("INFO", "Ejecución del agente finalizada.")

def main():
    schedule.every().day.at("21:00").do(ejecutar_agente)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    ejecutar_agente()
    # main()
    # enviar_email("Esto es una prueba de envío desde el bot.")
