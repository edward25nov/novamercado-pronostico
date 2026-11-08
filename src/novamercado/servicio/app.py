"""Aplicación FastAPI.

Fase F1: solo GET /health. Mientras no hay modelo cargado responde 503 (contrato del Anexo),
e informa el estado de cada dependencia para verificar la red de Docker.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from novamercado import config
from novamercado.servicio import dependencias

app = FastAPI(title="NovaMercado · pronóstico diario de ventas", version="0.1.0")
app.state.modelo = None  # se carga en la fase F5


@app.get("/health")
def health():
    cfg = config.leer()
    revision = dependencias.revisar_todas(cfg)
    fallas = [m for m in revision.values() if m]
    cuerpo = {"dependencias": {k: (m or "ok") for k, m in revision.items()}}
    if app.state.modelo is None:
        return JSONResponse(status_code=503, content={"estado": "sin_modelo",
                                                      "motivo": "no hay un modelo cargado", **cuerpo})
    if fallas:
        return {"estado": "degradado", "motivo": "; ".join(fallas), **cuerpo}
    return {"estado": "ok", **cuerpo}
