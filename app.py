# app.py
from fastapi import FastAPI
import logging

from main import ejecutar_agente

app = FastAPI()

@app.get("/")
def home():
    return {"message": "✅ API del Agente funcionando correctamente."}

@app.get("/ping")
def ping():
    logging.info("Ping recibido.")
    return {"message": "Ping recibido. Render no dormirá 😉"}

@app.get("/run-agente")
def run_agente():
    try:
        ejecutar_agente()
        return {"message": "🧠 Agente ejecutado correctamente."}
    except Exception as e:
        logging.error(f"Error al ejecutar agente desde endpoint: {e}")
        return {"error": str(e)}
