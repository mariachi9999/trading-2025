# ai_agent_oportunidades/requirements.txt
# Librerías necesarias para el agente
ccxt
pandas
pandas-ta
gspread
oauth2client
schedule
pytz


# ai_agent_oportunidades/main.py
import ccxt
import pandas as pd
import pandas_ta as ta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import schedule
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

# ========== CONFIGURACIÓN ==========
TICKER_SHEET_NAME = "Tickers"
ALERT_DESTINATIONS = ["email"]
RSI_THRESHOLD = 30
EMAIL_REMITENTE = "tu_email@gmail.com"
EMAIL_DESTINATARIO = "tu_email@gmail.com"
EMAIL_CONTRASENA = "tu_contraseña"

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open("AI_Oportunidades_Mercado").worksheet(TICKER_SHEET_NAME)
oportunidades_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Oportunidades")
cierres_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cierres")
posiciones_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Posiciones")

# Binance setup
exchange = ccxt.binance()

def get_tickers():
    return sheet.col_values(1)[1:]  # omite el encabezado

def get_ohlcv(ticker):
    try:
        ohlcv = exchange.fetch_ohlcv(f"{ticker}/USDT", timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        return df
    except Exception as e:
        print(f"Error con {ticker}: {e}")
        return pd.DataFrame()

def tiene_posicion_abierta(ticker):
    try:
        rows = posiciones_sheet.get_all_values()
        for row in rows[1:]:
            if row[0] == ticker and row[5].lower() == "open":
                return True
        return False
    except Exception as e:
        print(f"Error al verificar posición abierta: {e}")
        return False

def analizar_indicadores(df, ticker):
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    adx = ta.adx(df['high'], df['low'], df['close'])
    df['adx'] = adx['ADX_14']
    df['di+'] = adx['DMP_14']
    df['di-'] = adx['DMN_14']

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
    msg["From"] = EMAIL_REMITENTE
    msg["To"] = EMAIL_DESTINATARIO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_REMITENTE, EMAIL_CONTRASENA)
        server.send_message(msg)

def ejecutar_agente():
    tickers = get_tickers()
    for ticker in tickers:
        df = get_ohlcv(ticker)
        if df.empty:
            continue
        if analizar_indicadores(df, ticker):
            actual = df.iloc[-1]
            enviar_alerta(ticker, actual)

def main():
    schedule.every().day.at("21:00").do(ejecutar_agente)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
