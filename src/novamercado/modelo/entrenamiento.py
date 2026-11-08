"""Entrenamiento, registro en MLflow y modelo inicial.

`entrenar` no toca MLflow ni la base: recibe ventas y catálogos y devuelve el Pronosticador con su
evaluación. `registrar` guarda la tanda en MLflow (un run padre y un run anidado por modelo de la
escalera) y registra una versión del modelo de producción. Solo `promover` mueve el alias.
Lo usan el inicializador (primer modelo) y el DAG de reentrenamiento (F6).
"""

import json
import logging
import os
import tempfile
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from novamercado.datos.lectura import Catalogos
from novamercado.modelo import costos as C
from novamercado.modelo import evaluacion as E
from novamercado.modelo import modelos as M
from novamercado.modelo import variables as V
from novamercado.modelo.pronosticador import ARCHIVO, VERSION_FORMATO, EnvolturaPyfunc, Pronosticador

log = logging.getLogger(__name__)

EXPERIMENTO = "novamercado-ventas"
NOMBRE_MODELO = "novamercado-ventas"
ALIAS = "champion"
ALIAS_ANTERIOR = "anterior"
N_VENTANAS = 4

# Escalera (D22): todos con las mismas ventanas y filas. El de producción es fijo (D13): el más
# robusto ante cambios de nivel de la demanda; los demás quedan como referencia en cada tanda.
ESCALERA = {
    "baseline": M.Baseline,
    "gbm_directo": lambda: M.GBM("directo", escala="absoluta"),
    "gbm_relativo_absoluta": lambda: M.GBM("relativo", escala="absoluta"),
    "gbm_relativo_sin_escala": lambda: M.GBM("relativo", escala="relativa"),
}
PRODUCCION = "gbm_relativo_sin_escala"


@dataclass
class Candidato:
    nombre: str
    parametros: dict
    factores: dict[str, float]
    metricas: dict[str, float]
    metricas_ventana: dict[str, dict[str, float]]
    costo_familia: dict[str, float]
    segundos: float


@dataclass
class Resultado:
    pronosticador: Pronosticador
    candidatos: dict[str, Candidato]
    validacion: pd.DataFrame          # predicciones fuera de muestra del modelo de producción
    linaje: dict = field(default_factory=dict)

    @property
    def produccion(self) -> Candidato:
        return self.candidatos[PRODUCCION]


def _evaluar(nombre, fabrica, X, y, ventas, vs, costos) -> tuple[Candidato, pd.Series]:
    t0 = time.perf_counter()
    pred = E.predecir_ventanas(fabrica, X, y, ventas["fecha"], vs)
    sub = ventas.loc[pred.index]
    factores = C.elegir_factores(sub["familia_id"], pred, sub["ventas"], costos)
    sugerido = C.cantidad(pred, sub["familia_id"].map(factores).to_numpy())
    metricas = E.metricas(sub["ventas"], pred, sugerido, sub["familia_id"], costos)
    por_ventana = {}
    for v in vs:
        m = ((sub["fecha"] >= v.inicio) & (sub["fecha"] <= v.fin)).to_numpy()
        por_ventana[str(v)] = E.metricas(sub["ventas"][m], pred[m], sugerido[m], sub["familia_id"][m], costos)
    costo_fila = C.costo_por_fila(sub["familia_id"], sub["ventas"], sugerido, costos)
    costo_familia = pd.Series(costo_fila, index=sub.index).groupby(sub["familia_id"]).sum().round(1).to_dict()
    cand = Candidato(nombre, fabrica().parametros(), factores, metricas, por_ventana, costo_familia,
                     time.perf_counter() - t0)
    return cand, pred


def entrenar(ventas: pd.DataFrame, cat: Catalogos, n_ventanas: int = N_VENTANAS) -> Resultado:
    """Evalúa la escalera con validación temporal y entrena el modelo de producción con todo."""
    ventas = ventas.reset_index(drop=True)
    codigos = V.codigos_desde(cat.tiendas, cat.familias, cat.feriados)
    X = V.construir(ventas, ventas, cat.tiendas, cat.feriados, codigos)
    y = ventas["ventas"].to_numpy(dtype=float)
    ultima = ventas["fecha"].max()
    vs = E.ventanas(ultima, n_ventanas)

    candidatos, preds = {}, {}
    for nombre, fabrica in ESCALERA.items():
        candidatos[nombre], preds[nombre] = _evaluar(nombre, fabrica, X, y, ventas, vs, cat.costos)
        log.info("%s: costo %.0f, WAPE %.4f (%.0f s)", nombre, candidatos[nombre].metricas["costo_total"],
                 candidatos[nombre].metricas["wape"], candidatos[nombre].segundos)

    prod = candidatos[PRODUCCION]
    modelo = ESCALERA[PRODUCCION]().ajustar(X, y, ventas["fecha"])
    p = preds[PRODUCCION]
    sub = ventas.loc[p.index]
    validacion = sub[["tienda_id", "familia_id", "fecha", "ventas"]].assign(
        venta_esperada=p.to_numpy(),
        cantidad_sugerida=C.cantidad(p, sub["familia_id"].map(prod.factores).to_numpy()))
    info = {
        "modelo": PRODUCCION,
        "version_formato": VERSION_FORMATO,
        "fecha_corte": str(ultima.date()),
        "ventanas_validacion": [str(v) for v in vs],
        "filas_entrenamiento": int(len(ventas)),
        "costo_validacion": prod.metricas["costo_total"],
        "wape_validacion": prod.metricas["wape"],
    }
    linaje = {
        "filas": int(len(ventas)),
        "fecha_min": str(ventas["fecha"].min().date()),
        "fecha_max": str(ultima.date()),
        "suma_ventas": float(ventas["ventas"].sum()),
        "filas_observacion": int((ventas.get("origen") == "observacion").sum()) if "origen" in ventas else 0,
        "huella_ventas": str(pd.util.hash_pandas_object(
            ventas[["tienda_id", "familia_id", "fecha", "ventas"]], index=False).sum()),
    }
    return Resultado(Pronosticador(modelo, codigos, prod.factores, info), candidatos, validacion, linaje)


def _registrar_candidato(cand: Candidato):
    mlflow.log_params({k: v for k, v in cand.parametros.items() if v is not None} | {"modelo": cand.nombre})
    mlflow.log_metrics({f"{k}_validacion": v for k, v in cand.metricas.items()})
    for i, m in enumerate(cand.metricas_ventana.values(), start=1):
        mlflow.log_metrics({f"costo_ventana_{i}": m["costo_total"], f"wape_ventana_{i}": m["wape"]})
    mlflow.log_dict({"factores": cand.factores, "costo_por_familia": cand.costo_familia,
                     "metricas_por_ventana": cand.metricas_ventana}, "evaluacion.json")
    mlflow.log_metric("segundos_evaluacion", cand.segundos)


def registrar(res: Resultado, tracking_uri: str, origen: str, etiquetas: dict | None = None) -> str:
    """Registra la tanda en MLflow y una versión nueva del modelo de producción (sin alias).
    Devuelve el número de versión (texto)."""
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENTO)
    etiquetas = {"origen": origen, "commit": os.environ.get("GIT_COMMIT", "desconocido"), **(etiquetas or {})}
    with mlflow.start_run(run_name=f"tanda-{res.pronosticador.info['fecha_corte']}") as padre:
        mlflow.set_tags(etiquetas | {"tipo": "tanda"})
        mlflow.log_params({f"datos_{k}": v for k, v in res.linaje.items()}
                          | {"ventanas_validacion": ",".join(res.pronosticador.info["ventanas_validacion"])})
        tabla = pd.DataFrame({n: c.metricas for n, c in res.candidatos.items()}).T.round(4)
        mlflow.log_text(tabla.to_csv(), "escalera.csv")
        for nombre, cand in res.candidatos.items():
            with mlflow.start_run(run_name=nombre, nested=True) as hijo:
                mlflow.set_tags(etiquetas | {"tipo": "candidato", "produccion": str(nombre == PRODUCCION)})
                _registrar_candidato(cand)
                if nombre != PRODUCCION:
                    continue
                with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
                    # La envoltura no usa predict de pyfunc (ver EnvolturaPyfunc): sin firma a propósito.
                    warnings.filterwarnings("ignore", message=".*type hints to the `predict` method.*")
                    ruta = res.pronosticador.guardar(Path(tmp))
                    info = mlflow.pyfunc.log_model(
                        name="modelo", python_model=EnvolturaPyfunc(), artifacts={"pronosticador": str(ruta)},
                        registered_model_name=NOMBRE_MODELO)
                mlflow.log_dict(res.pronosticador.info, "info_modelo.json")
                run_hijo = hijo.info.run_id
        mlflow.log_metric("costo_validacion_produccion", res.produccion.metricas["costo_total"])
    version = str(info.registered_model_version)
    cliente = MlflowClient()
    tags = {
        "costo_validacion": f"{res.produccion.metricas['costo_total']:.1f}",
        "wape_validacion": f"{res.produccion.metricas['wape']:.4f}",
        "fecha_corte": res.pronosticador.info["fecha_corte"],
        "ventanas_validacion": ",".join(res.pronosticador.info["ventanas_validacion"]),
        "modelo": PRODUCCION, "version_formato": str(VERSION_FORMATO), "run_id": run_hijo, "tanda": padre.info.run_id,
        "factores": json.dumps(res.pronosticador.factores), **etiquetas,
    }
    for k, v in tags.items():
        cliente.set_model_version_tag(NOMBRE_MODELO, version, k, v)
    return version


def vigente(tracking_uri: str) -> tuple[str, str] | None:
    """(versión, run_id) del alias champion, o None si no existe (MLflow debe responder). El run_id
    identifica el modelo aunque el Registry se reinicie y vuelva a numerar desde 1."""
    mlflow.set_tracking_uri(tracking_uri)
    try:
        v = MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS)
    except mlflow.exceptions.MlflowException as e:
        if "RESOURCE_DOES_NOT_EXIST" in str(e.error_code) or "not found" in str(e).lower():
            return None
        raise
    return str(v.version), str(v.run_id or v.tags.get("run_id", ""))


def version_vigente(tracking_uri: str) -> str | None:
    """Versión con el alias champion, o None si no existe (MLflow debe responder)."""
    actual = vigente(tracking_uri)
    return actual[0] if actual else None


def ultima_version(tracking_uri: str, origen: str | None = None) -> str | None:
    """Versión registrada más reciente (opcionalmente con el tag `origen`), o None."""
    mlflow.set_tracking_uri(tracking_uri)
    filtro = f"name='{NOMBRE_MODELO}'"
    versiones = [v for v in MlflowClient().search_model_versions(filtro)
                 if origen is None or v.tags.get("origen") == origen]
    return str(max(int(v.version) for v in versiones)) if versiones else None


def promover(tracking_uri: str, version: str) -> None:
    """Mueve champion a `version`; el vigente anterior queda con el alias `anterior`."""
    mlflow.set_tracking_uri(tracking_uri)
    cliente = MlflowClient()
    previa = version_vigente(tracking_uri)
    if previa and previa != version:
        cliente.set_registered_model_alias(NOMBRE_MODELO, ALIAS_ANTERIOR, previa)
    cliente.set_registered_model_alias(NOMBRE_MODELO, ALIAS, version)


def descargar(tracking_uri: str, version: str, destino: Path) -> Pronosticador:
    """Descarga el Pronosticador de una versión registrada (lo usa la API, con caché local)."""
    mlflow.set_tracking_uri(tracking_uri)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = mlflow.artifacts.download_artifacts(
        artifact_uri=f"models:/{NOMBRE_MODELO}/{version}", dst_path=str(destino))
    archivo = next(Path(ruta).rglob(ARCHIVO))
    return Pronosticador.cargar(archivo)


def resumen(res: Resultado) -> pd.DataFrame:
    filas = {n: {"wape": c.metricas["wape"], "sesgo": c.metricas["sesgo"], "mae": c.metricas["mae"],
                 "costo": c.metricas["costo_total"], "segundos": c.segundos}
             for n, c in res.candidatos.items()}
    return pd.DataFrame(filas).T.assign(vs_baseline=lambda d: d["costo"] / d.loc["baseline", "costo"] - 1)

