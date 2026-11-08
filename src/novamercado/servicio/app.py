"""API del servicio (contrato del Anexo del enunciado).

Los endpoints solo orquestan: la limpieza vive en `novamercado.calidad`, el registro en
`servicio.repositorio`, el modelo vigente y la salud en `servicio.estado`.

- Datos de entrada defectuosos nunca producen un 500: se reparan, se advierten o se rechazan con 422.
- Si falta algo del servicio (modelo, base), se responde 503 con `detail`.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

import pandas as pd
import psycopg
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from novamercado import calidad, config
from novamercado.calidad.esquemas import (
    Calidad,
    PrediccionFamilia,
    RespuestaObservaciones,
    RespuestaPrediccion,
)
from novamercado.calidad.resultado import ADVERTIR, Observacion
from novamercado.servicio import repositorio
from novamercado.servicio.estado import Estado

log = logging.getLogger("novamercado.servicio")

EJEMPLO_PREDICCION = {"tienda_id": 5, "fecha": "2025-11-17", "familias": [
    {"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}]}
EJEMPLO_OBSERVACION = {"tienda_id": 5, "fecha": "2025-11-17", "ventas": [
    {"familia_id": "abarrotes", "ventas": 994}, {"familia_id": "bebidas", "ventas": 1292}]}


def _cuerpo_openapi(ejemplo: dict) -> dict:
    # El cuerpo se lee crudo (la limpieza decide qué reparar), así que el esquema solo documenta.
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"type": "object"}, "example": ejemplo}}}}


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if not hasattr(app.state, "estado"):
        app.state.estado = Estado(config.leer())
    if os.environ.get("NOVAMERCADO_SIN_MONITOR") != "1":
        app.state.estado.iniciar()
    yield
    app.state.estado.detener()


app = FastAPI(title="NovaMercado · pronóstico diario de ventas", version="1.0.0", lifespan=ciclo_de_vida)


def _estado(request: Request) -> Estado:
    return request.app.state.estado


def _error(codigo: int, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"detail": detalle})


def _calidad(obs: list[Observacion]) -> Calidad:
    return Calidad(estado=calidad.estado(obs), observaciones=[o.contrato() for o in obs])


def avisos_datos_recientes(ventas: pd.DataFrame, tienda_id: int, fecha, familias: list[str]) -> list[Observacion]:
    """Advertencia si faltan las ventas del día anterior (D12): el pronóstico usa lo último disponible."""
    ayer = pd.Timestamp(fecha) - timedelta(days=1)
    ultima = ventas.groupby("familia_id")["fecha"].max() if len(ventas) else pd.Series(dtype="datetime64[ns]")
    sin_dato = [f for f in familias if f not in ultima.index]
    atrasadas = {f: ultima[f] for f in familias if f in ultima.index and ultima[f] < ayer}
    avisos = []
    if sin_dato:
        avisos.append(Observacion("familias", ADVERTIR, f"no hay ventas registradas de {', '.join(sin_dato)} en los "
                                  f"{repositorio.DIAS_HISTORIA_PREDICCION} días anteriores; se usó el nivel típico de "
                                  "la familia en tiendas del mismo tipo", "sin_historia"))
    if atrasadas:
        desde = min(atrasadas.values()).date()
        nombres = "todas las familias" if len(atrasadas) == len(familias) else ", ".join(sorted(atrasadas))
        avisos.append(Observacion("fecha", ADVERTIR, f"faltan las ventas del {ayer.date()} de la tienda {tienda_id} "
                                  f"({nombres}); la última conocida es del {desde} y el pronóstico se hizo con ella",
                                  "datos_recientes_faltantes"))
    return avisos


@app.get("/vivo", include_in_schema=False)
def vivo():
    """Vida del proceso, sin consultar dependencias: lo usa el HEALTHCHECK del contenedor."""
    return {"vivo": True}


@app.get("/health")
def health(request: Request):
    codigo, cuerpo = _estado(request).resumen_salud()
    return JSONResponse(status_code=codigo, content=cuerpo)


@app.get("/modelo")
def modelo(request: Request):
    m = _estado(request).modelo
    if m is None:
        return _error(503, f"no hay un modelo cargado: {_estado(request).motivo_sin_modelo}")
    return {"nombre": m.nombre, "alias": m.alias, "version": m.version, "origen": m.origen,
            "fecha_corte": m.pronosticador.info.get("fecha_corte")}


def _catalogo_listo(est: Estado):
    if est.catalogo is None:
        try:
            est.refrescar_catalogo()
        except Exception as e:  # noqa: BLE001
            return _error(503, f"la base de datos no está disponible ({type(e).__name__})")
    return None


def _servicio_listo(est: Estado):
    if est.modelo is None:
        return _error(503, f"no hay un modelo cargado: {est.motivo_sin_modelo}")
    return _catalogo_listo(est)


def _predecir(est: Estado, cuerpo: bytes):
    if (no_listo := _servicio_listo(est)) is not None:
        return no_listo
    modelo, cat, cats = est.modelo, est.catalogo, est.catalogos  # una sola foto: un cambio de modelo no la mezcla
    try:
        with repositorio.conectar(est.cfg.db_url) as con:
            def promo_previa(t, f, d):
                return repositorio.ultima_promocion(con, t, f, d)

            try:
                sol, obs = calidad.limpiar_prediccion(cuerpo, cat, promo_previa)
            except calidad.Rechazo as r:
                repositorio.registrar_solicitud(con, "prediccion", cuerpo, 422, detalle=r.detalle)
                return _error(422, r.detalle)
            except psycopg.Error:
                raise
            except Exception as e:  # noqa: BLE001 - una regla que falla no puede volverse un 500 (D7)
                log.exception("excepción inesperada en la limpieza de una predicción")
                detalle = f"no se pudo interpretar la solicitud ({type(e).__name__})"
                repositorio.registrar_solicitud(con, "prediccion", cuerpo, 422, detalle=detalle)
                return _error(422, detalle)

            familias = [f.familia_id for f in sol.familias]
            ventas = repositorio.ventas_para_predecir(con, sol.tienda_id, sol.fecha)
            obs = obs + avisos_datos_recientes(ventas, sol.tienda_id, sol.fecha, familias)
            objetivos = pd.DataFrame({"tienda_id": sol.tienda_id, "familia_id": familias,
                                      "fecha": pd.Timestamp(sol.fecha),
                                      "en_promocion": [f.en_promocion for f in sol.familias]})
            resultado = modelo.pronosticador.predecir(ventas, objetivos, cats.tiendas, cats.feriados)
            resultado.insert(0, "familia_id", familias)
            respuesta = RespuestaPrediccion(
                tienda_id=sol.tienda_id, fecha=sol.fecha, version_modelo=modelo.version,
                predicciones=[PrediccionFamilia(familia_id=r.familia_id, venta_esperada=float(r.venta_esperada),
                                                cantidad_sugerida=int(r.cantidad_sugerida))
                              for r in resultado.itertuples(index=False)],
                calidad=_calidad(obs))
            with con.transaction():
                sid = repositorio.registrar_solicitud(con, "prediccion", cuerpo, 200, sol, respuesta.calidad.estado,
                                                      observaciones=obs)
                repositorio.registrar_predicciones(con, sid, sol, resultado, modelo.version)
            return respuesta
    except psycopg.Error as e:
        log.exception("base de datos no disponible")
        return _error(503, f"la base de datos no está disponible ({type(e).__name__}); intente de nuevo")


def _observar(est: Estado, cuerpo: bytes):
    # Las observaciones no necesitan el modelo: se registran aunque todavía no haya champion.
    if (no_listo := _catalogo_listo(est)) is not None:
        return no_listo
    cat = est.catalogo
    try:
        with repositorio.conectar(est.cfg.db_url) as con:
            try:
                obs_canonica, obs = calidad.limpiar_observacion(cuerpo, cat)
            except calidad.Rechazo as r:
                repositorio.registrar_solicitud(con, "observaciones", cuerpo, 422, detalle=r.detalle)
                return _error(422, r.detalle)
            except psycopg.Error:
                raise
            except Exception as e:  # noqa: BLE001
                log.exception("excepción inesperada en la limpieza de una observación")
                detalle = f"no se pudo interpretar la solicitud ({type(e).__name__})"
                repositorio.registrar_solicitud(con, "observaciones", cuerpo, 422, detalle=detalle)
                return _error(422, detalle)
            estado = calidad.estado(obs)
            with con.transaction():
                sid = repositorio.registrar_solicitud(con, "observaciones", cuerpo, 200, obs_canonica, estado,
                                                      observaciones=obs)
                guardados = repositorio.guardar_observacion(con, sid, obs_canonica)
            est.ver_fecha_observada(obs_canonica.fecha)
            return RespuestaObservaciones(registros_guardados=guardados, calidad=_calidad(obs))
    except psycopg.Error as e:
        log.exception("base de datos no disponible")
        return _error(503, f"la base de datos no está disponible ({type(e).__name__}); intente de nuevo")


@app.post("/v1/prediccion", response_model=RespuestaPrediccion, openapi_extra=_cuerpo_openapi(EJEMPLO_PREDICCION),
          responses={422: {"description": "Solicitud rechazada"}, 503: {"description": "Servicio no listo"}})
async def prediccion(request: Request):
    """Pronóstico de un día para una tienda: venta esperada y cantidad sugerida por familia."""
    return await run_in_threadpool(_predecir, _estado(request), await request.body())


@app.post("/v1/observaciones", response_model=RespuestaObservaciones,
          openapi_extra=_cuerpo_openapi(EJEMPLO_OBSERVACION),
          responses={422: {"description": "Solicitud rechazada"}, 503: {"description": "Servicio no listo"}})
async def observaciones(request: Request):
    """Ventas reales de un día para una tienda. Reenviar lo mismo no duplica (registros_guardados = 0)."""
    return await run_in_threadpool(_observar, _estado(request), await request.body())
