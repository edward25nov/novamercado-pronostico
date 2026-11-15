"""Reentrenamiento y criterio de reemplazo (D15). Lo orquesta el DAG `reentrenamiento`.

1. `entrenar_retador`: entrena la escalera con todas las ventas de la base (histórico + observaciones,
   preparadas según D26) y registra el retador como versión candidata (sin alias). Mide al retador y
   al vigente **solo en los días posteriores al corte del vigente** (máximo 28): ahí los dos están
   fuera de muestra.
   - Retador: un modelo de la misma receta entrenado solo con filas anteriores a esos días; su
     cantidad sugerida usa factores elegidos con validación anterior a esos días.
   - Vigente: su artefacto predice las mismas filas, un día a la vez con las ventas reales hasta el día
     anterior, con sus propios factores.
2. `decidir`: con al menos MIN_DIAS_NUEVOS días, se promueve salvo que el retador sea peor que el
   vigente por más de TOLERANCIA (no inferioridad: con la misma receta, el retador solo agrega datos
   más recientes). Si no, el alias no se toca. Siempre se registra el resultado.
3. `registrar_fallo`: si una tarea falla, la ejecución queda `fallido`, diciendo si el alias cambió.
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
from novamercado.modelo import preparacion

log = logging.getLogger(__name__)

MIN_DIAS_NUEVOS = 7    # días posteriores al corte del vigente necesarios para comparar
MAX_DIAS_COMPARACION = 28
TOLERANCIA = 0.02      # no inferioridad: se promueve salvo que el retador cueste más de 2 % más
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

def decidir_reemplazo(costo_retador: float | None, costo_vigente: float | None, filas: int,
                      version_vigente: str | None, ventana: str, dias_nuevos: int | None) -> tuple[bool, str]:
    """(promover, motivo)."""
    if version_vigente is None:
        if costo_retador is not None and not math.isfinite(costo_retador):
            return False, "el retador no pasó las verificaciones de sanidad y no hay modelo vigente"
        return True, "no había modelo vigente: se promueve el retador"
    if dias_nuevos is None or dias_nuevos < MIN_DIAS_NUEVOS:
        return False, (f"solo hay {dias_nuevos or 0} días de ventas posteriores al corte del vigente "
                       f"(v{version_vigente}); se necesitan {MIN_DIAS_NUEVOS} para compararlos fuera de "
                       "muestra: se conserva el vigente")
    if not (filas > 0 and costo_retador is not None and math.isfinite(costo_retador) and costo_retador >= 0):
        return False, f"el retador no pasó las verificaciones de sanidad (costo {costo_retador}, {filas} filas)"
    if costo_vigente is None or not math.isfinite(costo_vigente):
        return True, (f"el vigente (v{version_vigente}) no pudo predecir {ventana}; costo del retador "
                      f"{_miles(costo_retador)}")
    cambio = costo_retador / costo_vigente - 1 if costo_vigente > 0 else 0.0
    texto = (f"Costo en validación {_miles(costo_retador)} vs {_miles(costo_vigente)} del vigente "
             f"(v{version_vigente}; {cambio:+.1%}; {dias_nuevos} días posteriores a su corte: {ventana})")
    if costo_retador <= costo_vigente * (1 + TOLERANCIA):
        return True, texto
    return False, f"{texto}: el retador es peor por más de {TOLERANCIA:.0%}, se conserva el vigente"


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
                    retador = args[0].get("version_retador") if args and isinstance(args[0], dict) else None
                    registrar_fallo(run_id, f"{etapa}: {type(e).__name__}: {str(e)[:300]}", cfg=cfg,
                                    version_retador=retador)
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
    ultima = ventas["fecha"].max()

    # El vigente y su corte definen los días de comparación (fuera de muestra para ambos).
    actual = T.vigente(cfg.mlflow_uri)
    vigente = corte = desde = None
    if actual is not None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                vigente = T.descargar(cfg.mlflow_uri, actual[0], Path(tmp))
            corte = pd.Timestamp(vigente.info["fecha_corte"])
            desde = max(corte + pd.Timedelta(days=1), ultima - pd.Timedelta(days=MAX_DIAS_COMPARACION - 1))
        except Exception:  # noqa: BLE001 - un vigente ilegible no bloquea al retador
            log.exception("no se pudo cargar el vigente")
    dias_nuevos = int((ultima - corte).days) if corte is not None else None
    res = T.entrenar(ventas, cat, comparar_desde=desde if dias_nuevos and dias_nuevos > 0 else None)

    costo_ret = wape_ret = costo_vig = wape_vig = None
    filas = 0
    if res.comparacion is not None and len(res.comparacion):
        comp = res.comparacion
        # Factores del retador elegidos con validación anterior a los días comparados.
        val = res.validacion[res.validacion["fecha"] < desde]
        k = C.elegir_factores(val["familia_id"], val["venta_esperada"], val["ventas"], cat.costos) if len(val) else {}
        cant_ret = C.cantidad(comp["venta_esperada"], comp["familia_id"].map(k).fillna(1.0).to_numpy())
        costo_ret = _costo(comp["familia_id"], comp["ventas"], cant_ret, cat.costos)
        wape_ret = float(np.abs(comp["venta_esperada"] - comp["ventas"]).sum() / max(comp["ventas"].sum(), 1))
        filas = int(len(comp))
        if vigente is not None:
            try:
                preparadas, _ = preparacion.preparar(ventas)
                objetivos = comp[["tienda_id", "familia_id", "fecha", "en_promocion"]].reset_index(drop=True)
                pred = vigente.predecir(preparadas, objetivos, cat.tiendas, cat.feriados)
                costo_vig = _costo(objetivos["familia_id"], comp["ventas"].to_numpy(),
                                   pred["cantidad_sugerida"].to_numpy(), cat.costos)
                wape_vig = float(np.abs(pred["venta_esperada"].to_numpy() - comp["ventas"].to_numpy()).sum()
                                 / max(comp["ventas"].sum(), 1))
            except Exception:  # noqa: BLE001
                log.exception("el vigente no pudo predecir los días de comparación")

    version = T.registrar(res, cfg.mlflow_uri, origen="reentrenamiento",
                          etiquetas={"dag_run_id": run_id, TAG_DECISION: "pendiente"})
    ventana = f"{desde.date()}..{ultima.date()}" if desde is not None else "sin días posteriores al corte"
    info = {"version_retador": version, "version_vigente": actual[0] if actual else None,
            "corte_vigente": str(corte.date()) if corte is not None else None, "dias_nuevos": dias_nuevos,
            "ventana": ventana, "filas_ventana": filas, "costo_retador": costo_ret, "wape_retador": wape_ret,
            "costo_vigente": costo_vig, "wape_vigente": wape_vig, "fecha_corte": res.pronosticador.info["fecha_corte"],
            "costo_validacion_4_ventanas": res.produccion.metricas["costo_total"], **res.linaje,
            "segundos_entrenamiento": round(time.perf_counter() - t0, 1)}
    log.info("retador v%s: costo %s; vigente %s: costo %s (%s)", version, costo_ret, info["version_vigente"],
             costo_vig, ventana)
    return info


@_con_registro_de_fallo("decidir")
def decidir(run_id: str, info: dict, cfg: config.Config | None = None) -> dict:
    cfg = cfg or config.leer()
    promover, motivo = decidir_reemplazo(info["costo_retador"], info["costo_vigente"], info["filas_ventana"],
                                         info["version_vigente"], info["ventana"], info["dias_nuevos"])
    cliente = MlflowClient(cfg.mlflow_uri)
    # Orden: tags, luego el alias (lo único que cambia lo que sirve la API) y al final el resultado.
    cliente.set_model_version_tag(T.NOMBRE_MODELO, info["version_retador"], TAG_DECISION,
                                  "promovido" if promover else "rechazado")
    cliente.set_model_version_tag(T.NOMBRE_MODELO, info["version_retador"], "motivo", motivo[:500])
    if promover:
        T.promover(cfg.mlflow_uri, info["version_retador"])
    vigente = T.version_vigente(cfg.mlflow_uri)
    registrar_resultado(cfg.db_url, run_id, "exitoso", promover, vigente, motivo, info)
    log.info("decisión: %s — %s", "promovido" if promover else "no promovido", motivo)
    return {"promovido": promover, "version": vigente, "motivo": motivo}


def registrar_fallo(run_id: str, motivo: str, cfg: config.Config | None = None,
                    version_retador: str | None = None) -> None:
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
    if version_retador is not None and version == version_retador:
        registrar_resultado(cfg.db_url, run_id, "fallido", True, version,
                            f"el retador v{version} quedó promovido, pero falló un paso posterior: {motivo}")
        return
    registrar_resultado(cfg.db_url, run_id, "fallido", False, version,
                        f"el reentrenamiento falló y el modelo vigente no cambió: {motivo}")
