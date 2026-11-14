"""Reentrenamiento y criterio de reemplazo (D15). Lo orquesta el DAG `reentrenamiento`.

1. `entrenar_retador`: entrena la escalera con todas las ventas de la base (histórico + observaciones,
   preparadas según D26), registra el retador como versión candidata (sin alias) y mide al retador y
   al vigente en la **misma ventana**: los últimos 28 días con ventas.
   - Retador: el modelo de esa ventana se entrenó solo con datos anteriores a ella (validación
     temporal de `entrenar`), y su cantidad sugerida usa factores elegidos con las ventanas
     anteriores (no con la que se mide).
   - Vigente: su artefacto predice las mismas filas, un día a la vez con las ventas reales hasta el día
     anterior, con sus propios factores (elegidos al entrenarse, antes de la ventana).
2. `decidir`: se promueve si el costo del retador es al menos MARGEN menor que el del vigente y pasa
   las verificaciones de sanidad. Si no, el alias no se toca. Siempre se registra el resultado.
3. `registrar_fallo`: si una tarea falla, la ejecución queda `fallido` y el vigente sigue igual.
"""

import json
import logging
import math
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from mlflow.tracking import MlflowClient

from novamercado import config
from novamercado.datos import lectura
from novamercado.modelo import costos as C
from novamercado.modelo import entrenamiento as T
from novamercado.modelo import evaluacion as E
from novamercado.modelo import preparacion

log = logging.getLogger(__name__)

MARGEN = 0.01  # el retador debe costar al menos 1 % menos que el vigente en la misma ventana
TAG_DECISION = "decision"


def _miles(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


# --- registro en la base

def marcar_en_curso(db_url: str, run_id: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as con:
        con.execute("INSERT INTO reentrenamientos (id, estado) VALUES (%s, 'en_curso') ON CONFLICT (id) DO NOTHING",
                    (run_id,))


def registrar_resultado(db_url: str, run_id: str, estado: str, promovido: bool | None, version: str | None,
                        motivo: str, metricas: dict | None = None) -> None:
    with psycopg.connect(db_url, autocommit=True) as con:
        con.execute(
            "INSERT INTO reentrenamientos (id, estado, promovido, version, motivo, metricas, terminado_en) "
            "VALUES (%s, %s, %s, %s, %s, %s, now()) ON CONFLICT (id) DO UPDATE SET estado = EXCLUDED.estado, "
            "promovido = EXCLUDED.promovido, version = EXCLUDED.version, motivo = EXCLUDED.motivo, "
            "metricas = EXCLUDED.metricas, terminado_en = now()",
            (run_id, estado, promovido, version, motivo[:1000], json.dumps(metricas or {}, default=str)))


# --- criterio (función pura, con pruebas)

def decidir_reemplazo(costo_retador: float, costo_vigente: float | None, filas: int, version_vigente: str | None,
                      ventana: str) -> tuple[bool, str]:
    """(promover, motivo)."""
    if not (filas > 0 and math.isfinite(costo_retador) and costo_retador >= 0):
        return False, f"el retador no pasó las verificaciones de sanidad (costo {costo_retador}, {filas} filas)"
    if version_vigente is None:
        return True, f"no había modelo vigente; costo del retador en validación {_miles(costo_retador)} ({ventana})"
    if costo_vigente is None or not math.isfinite(costo_vigente):
        return True, (f"el vigente (v{version_vigente}) no pudo predecir la ventana {ventana}; costo del retador "
                      f"{_miles(costo_retador)}")
    promover = costo_retador <= costo_vigente * (1 - MARGEN)
    mejora = 1 - costo_retador / costo_vigente if costo_vigente > 0 else 0.0
    texto = (f"Costo en validación {_miles(costo_retador)} vs {_miles(costo_vigente)} del vigente "
             f"(v{version_vigente}; {mejora:+.1%}; ventana {ventana})")
    if promover:
        return True, texto
    return False, f"{texto}: no mejora al menos {MARGEN:.0%}, se conserva el vigente"


# --- tareas

def _costo(familia: pd.Series, real, cantidad, costos) -> float:
    return float(C.costo_por_fila(familia, real, cantidad, costos).sum())


def _con_registro_de_fallo(etapa: str):
    """Si la tarea falla, registra el motivo real antes de propagar la excepción (el contexto del
    callback de Airflow 3 no trae la excepción)."""
    def decorador(funcion):
        def envuelta(run_id: str, *args, cfg: config.Config | None = None, **kw):
            cfg = cfg or config.leer()
            try:
                return funcion(run_id, *args, cfg=cfg, **kw)
            except Exception as e:
                try:
                    registrar_fallo(run_id, f"{etapa}: {type(e).__name__}: {str(e)[:300]}", cfg=cfg)
                except Exception:  # noqa: BLE001 - si tampoco hay base, queda el callback de Airflow
                    log.exception("no se pudo registrar el fallo")
                raise
        return envuelta
    return decorador


@_con_registro_de_fallo("entrenar_retador")
def entrenar_retador(run_id: str, cfg: config.Config | None = None) -> dict:
    cfg = cfg or config.leer()
    t0 = time.perf_counter()
    marcar_en_curso(cfg.db_url, run_id)
    with psycopg.connect(cfg.db_url) as con:
        ventas, cat = lectura.ventas(con), lectura.catalogos(con)
    res = T.entrenar(ventas, cat)

    # Retador en la última ventana, con factores elegidos en las ventanas anteriores.
    vs = [v for v in E.ventanas(res.validacion["fecha"].max(), T.N_VENTANAS)]
    w = vs[-1]
    val = res.validacion
    antes, en = val["fecha"] < w.inicio, (val["fecha"] >= w.inicio) & (val["fecha"] <= w.fin)
    k = C.elegir_factores(val.loc[antes, "familia_id"], val.loc[antes, "venta_esperada"], val.loc[antes, "ventas"],
                          cat.costos)
    vw = val[en]
    cant_ret = C.cantidad(vw["venta_esperada"], vw["familia_id"].map(k).fillna(1.0).to_numpy())
    costo_ret = _costo(vw["familia_id"], vw["ventas"], cant_ret, cat.costos)
    wape_ret = float(np.abs(vw["venta_esperada"] - vw["ventas"]).sum() / max(vw["ventas"].sum(), 1))

    # Vigente en las mismas filas.
    actual = T.vigente(cfg.mlflow_uri)
    costo_vig = wape_vig = None
    if actual is not None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                vigente = T.descargar(cfg.mlflow_uri, actual[0], Path(tmp))
            preparadas, _ = preparacion.preparar(ventas)
            objetivos = vw[["tienda_id", "familia_id", "fecha"]].merge(
                preparadas[["tienda_id", "familia_id", "fecha", "en_promocion"]], how="left")
            pred = vigente.predecir(preparadas, objetivos, cat.tiendas, cat.feriados)
            costo_vig = _costo(vw["familia_id"].reset_index(drop=True), vw["ventas"].to_numpy(),
                               pred["cantidad_sugerida"].to_numpy(), cat.costos)
            wape_vig = float(np.abs(pred["venta_esperada"].to_numpy() - vw["ventas"].to_numpy()).sum()
                             / max(vw["ventas"].sum(), 1))
        except Exception:  # noqa: BLE001 - un vigente que no puede predecir no bloquea al retador
            log.exception("el vigente no pudo predecir la ventana de comparación")

    version = T.registrar(res, cfg.mlflow_uri, origen="reentrenamiento",
                          etiquetas={"dag_run_id": run_id, TAG_DECISION: "pendiente"})
    info = {"version_retador": version, "version_vigente": actual[0] if actual else None,
            "ventana": str(w), "filas_ventana": int(len(vw)), "costo_retador": costo_ret, "wape_retador": wape_ret,
            "costo_vigente": costo_vig, "wape_vigente": wape_vig, "fecha_corte": res.pronosticador.info["fecha_corte"],
            "costo_validacion_4_ventanas": res.produccion.metricas["costo_total"], **res.linaje,
            "segundos_entrenamiento": round(time.perf_counter() - t0, 1)}
    log.info("retador v%s: costo %.0f; vigente %s: costo %s (ventana %s)", version, costo_ret, info["version_vigente"],
             costo_vig, w)
    return info


@_con_registro_de_fallo("decidir")
def decidir(run_id: str, info: dict, cfg: config.Config | None = None) -> dict:
    cfg = cfg or config.leer()
    promover, motivo = decidir_reemplazo(info["costo_retador"], info["costo_vigente"], info["filas_ventana"],
                                         info["version_vigente"], info["ventana"])
    cliente = MlflowClient(cfg.mlflow_uri)
    if promover:
        T.promover(cfg.mlflow_uri, info["version_retador"])
    cliente.set_model_version_tag(T.NOMBRE_MODELO, info["version_retador"], TAG_DECISION,
                                  "promovido" if promover else "rechazado")
    cliente.set_model_version_tag(T.NOMBRE_MODELO, info["version_retador"], "motivo", motivo[:500])
    vigente = T.version_vigente(cfg.mlflow_uri)
    registrar_resultado(cfg.db_url, run_id, "exitoso", promover, vigente, motivo, info)
    log.info("decisión: %s — %s", "promovido" if promover else "no promovido", motivo)
    return {"promovido": promover, "version": vigente, "motivo": motivo}


def registrar_fallo(run_id: str, motivo: str, cfg: config.Config | None = None) -> None:
    """La ejecución falló: el alias no se tocó. `version` es la vigente (si MLflow responde)."""
    cfg = cfg or config.leer()
    try:
        version = T.version_vigente(cfg.mlflow_uri)
    except Exception:  # noqa: BLE001
        version = None
    if version is None:
        with psycopg.connect(cfg.db_url, autocommit=True) as con:
            fila = con.execute("SELECT version FROM reentrenamientos WHERE version IS NOT NULL "
                               "ORDER BY terminado_en DESC NULLS LAST LIMIT 1").fetchone()
            fila = fila or con.execute("SELECT valor FROM estado_producto WHERE clave = 'modelo_inicial'").fetchone()
            version = fila[0] if fila else None
    with psycopg.connect(cfg.db_url, autocommit=True) as con:
        previo = con.execute("SELECT estado FROM reentrenamientos WHERE id = %s", (run_id,)).fetchone()
    if previo and previo[0] == "fallido":
        return  # ya se registró el motivo real (la tarea); el callback no lo reemplaza por uno genérico
    registrar_resultado(cfg.db_url, run_id, "fallido", False, version,
                        f"el reentrenamiento falló y el modelo vigente no cambió: {motivo}")
