# import ccxt
# import pandas as pd
# import pandas_ta as ta
# import gspread
# from oauth2client.service_account import ServiceAccountCredentials
# import schedule
# import time
# import smtplib
# from email.mime.text import MIMEText
# from datetime import datetime
# import pytz

# # ========== CONFIGURACIÓN ==========
# TICKER_SHEET_NAME = "Tickers"
# ALERT_DESTINATIONS = ["email"]
# EMAIL_REMITENTE = "tu_email@gmail.com"
# EMAIL_DESTINATARIO = "tu_email@gmail.com"
# EMAIL_CONTRASENA = "tu_contraseña"

# # Google Sheets setup
# scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
# client = gspread.authorize(creds)
# sheet = client.open("AI_Oportunidades_Mercado").worksheet(TICKER_SHEET_NAME)
# oportunidades_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Oportunidades")
# cierres_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Cierres")
# posiciones_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Posiciones")
# backtest_sheet = client.open("AI_Oportunidades_Mercado").worksheet("Backtest")

# # Binance setup
# exchange = ccxt.binance()

# def get_tickers():
#     return sheet.col_values(1)[1:]  # omite el encabezado

# def get_ohlcv(ticker):
#     try:
#         ohlcv = exchange.fetch_ohlcv(f"{ticker}/USDT", timeframe='1d', limit=365)
#         df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         return df
#     except Exception as e:
#         print(f"Error con {ticker}: {e}")
#         return pd.DataFrame()

# def condiciones_apertura(df):
#     df['rsi'] = ta.rsi(df['close'], length=14)
#     macd = ta.macd(df['close'])
#     df['macd_line'] = macd['MACD_12_26_9']
#     df['macd_signal'] = macd['MACDs_12_26_9']
#     df['macd_hist'] = macd['MACDh_12_26_9']

#     adx = ta.adx(df['high'], df['low'], df['close'])
#     df['adx'] = adx['ADX_14']
#     df['di+'] = adx['DMP_14']
#     df['di-'] = adx['DMN_14']

#     df['apertura'] = (
#         (df['macd_line'] > 0) &
#         (df['di+'] > df['di-']) &
#         (df['di+'] > df['adx'])
#     ) & ~(
#         (df['macd_line'].shift(1) > 0) &
#         (df['di+'].shift(1) > df['di-'].shift(1)) &
#         (df['di+'].shift(1) > df['adx'].shift(1))
#     )
#     return df

# def backtest_indicador(ticker):
#     df = get_ohlcv(ticker)
#     if df.empty:
#         return

#     df = condiciones_apertura(df)
#     zona_arg = pytz.timezone("America/Argentina/Buenos_Aires")

#     for i in range(len(df)):
#         if df.loc[i, 'apertura']:
#             fecha = df.loc[i, 'timestamp'].astimezone(zona_arg).strftime("%Y-%m-%d")
#             open_price = df.loc[i + 1, 'open'] if i + 1 < len(df) else df.loc[i, 'close']
#             day_after_close = df.loc[i + 1, 'close'] if i + 1 < len(df) else None
#             week_after_close = df.loc[i + 5, 'close'] if i + 5 < len(df) else None

#             j = i + 1
#             while j < len(df):
#                 cierre_condicion = not (
#                     df.loc[j, 'macd_line'] > 0 and
#                     df.loc[j, 'di+'] > df.loc[j, 'di-'] and
#                     df.loc[j, 'di+'] > df.loc[j, 'adx']
#                 )
#                 if cierre_condicion:
#                     break
#                 j += 1
#             close_price = df.loc[j, 'close'] if j < len(df) else None

#             backtest_sheet.append_row([
#                 fecha,
#                 ticker,
#                 round(open_price, 4),
#                 round(day_after_close, 4) if day_after_close else '',
#                 round(week_after_close, 4) if week_after_close else '',
#                 round(close_price, 4) if close_price else '',
#                 round(((day_after_close - open_price) / open_price) * 100, 2) if day_after_close else '',
#                 round(((week_after_close - open_price) / open_price) * 100, 2) if week_after_close else '',
#                 round(((close_price - open_price) / open_price) * 100, 2) if close_price else ''
#             ])

# def backtest_masivo():
#     tickers = get_tickers()
#     for ticker in tickers:
#         backtest_indicador(ticker)

# Para lanzar el backtest manualmente por ticker:
# backtest_indicador("BTC")

# Para lanzar el backtest para todos los tickers en la hoja:
# backtest_masivo()
