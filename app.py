# app.py
from fastapi import BackgroundTasks, FastAPI
import logging

from acciones_agent import stocks_ejecutar_agente
from crypto_agent import crypto_ejecutar_agente

app = FastAPI()

@app.get("/")
def home():
    return {"message": "✅ API del Agente funcionando correctamente."}

@app.get("/ping")
def ping():
    logging.info("Ping recibido.")
    return {"message": "Ping recibido. Render no dormirá 😉"}

@app.get("/run-crypto-agente")
def crypto_run_agente():
    try:
        crypto_ejecutar_agente()
        return {"message": "🧠 Agente ejecutado correctamente."}
    except Exception as e:
        logging.error(f"Error al ejecutar agente desde endpoint: {e}")
        return {"error": str(e)}

@app.get("/run-stock-agente")
def stocks_run_agente(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(stocks_ejecutar_agente)
        return {"mensaje": "Agente de acciones en ejecución en segundo plano"}
    except Exception as e:
        logging.error(f"Error al ejecutar agente desde endpoint: {e}")
        return {"error": str(e)}