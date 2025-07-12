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
from telegram import Bot

# ========== CONFIGURACIÓN ==========
TICKER_SHEET_NAME = "Tickers"
ALERT_DESTINATIONS = ["email", "telegram"]
RSI_THRESHOLD = 30
TELEGRAM_TOKEN = "TU_TOKEN"
TELEGRAM_CHAT_ID = "TU_CHAT_ID"

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open("AI_Oportunidades_Mercado").worksheet(TICKER_SHEET_NAME)

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

def analizar_indicadores(df):
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    adx = ta.adx(df['high'], df['low'], df['close'])
    df['adx'] = adx['ADX_14']
    df['di+'] = adx['DMP_14']
    df['di-'] = adx['DMN_14']

    # Condiciones: deben cumplirse en la última vela y NO en la anterior
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

    return False
  
def enviar_alerta(ticker):
        mensaje = f"⚠️ Señal de oportunidad detectada para {ticker}:\nMACD > 0, DI+ > DI- y DI+ > ADX solo en última vela"    if "email" in ALERT_DESTINATIONS:
        enviar_email(mensaje)
    if "telegram" in ALERT_DESTINATIONS:
        enviar_telegram(mensaje)

def enviar_email(mensaje):
    msg = MIMEText(mensaje)
    msg["Subject"] = "Alerta de Oportunidad"
    msg["From"] = "tu_email@dominio.com"
    msg["To"] = "destino@dominio.com"

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("tu_email@dominio.com", "tu_contraseña")
        server.send_message(msg)

def enviar_telegram(mensaje):
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje)

def ejecutar_agente():
    tickers = get_tickers()
    for ticker in tickers:
        df = get_ohlcv(ticker)
        if df.empty:
            continue
        if analizar_indicadores(df):
            enviar_alerta(ticker)

def main():
    schedule.every().day.at("21:00").do(ejecutar_agente)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
