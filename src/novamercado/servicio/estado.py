"""Estado del servicio en memoria: modelo vigente, catálogo y salud de las dependencias (D17).

Un hilo en segundo plano:
- cada `intervalo_salud_s` (15 s) revisa db, MLflow y Airflow en paralelo y refresca el catálogo;
- cada `intervalo_modelo_s` (30 s; 5 s mientras no hay modelo) consulta la versión de `@champion` y,
  si cambió, la descarga y la reemplaza de forma atómica (una sola asignación de atributo).
El modelo cargado se guarda en `cache_dir`: si MLflow no responde al arrancar, se usa la copia local.
Los endpoints solo leen este estado: nunca esperan a MLflow.
"""

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from novamercado.calidad import Catalogo
from novamercado.config import Config
from novamercado.datos import lectura
from novamercado.modelo import entrenamiento
from novamercado.modelo.pronosticador import ARCHIVO, Pronosticador
from novamercado.servicio import dependencias, repositorio

log = logging.getLogger(__name__)
PAUSA_SIN_MODELO_S = 5.0


@dataclass(frozen=True)
class ModeloVigente:
    pronosticador: Pronosticador
    nombre: str
    alias: str
    version: str
    origen: str  # "mlflow" | "cache"


class Cargador:
    """Obtiene el champion de MLflow con una copia local en disco."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.carpeta = Path(cfg.cache_dir)
        self.indice = self.carpeta / "vigente.json"

    def desde_cache(self) -> ModeloVigente | None:
        try:
            info = json.loads(self.indice.read_text())
            ruta = self.carpeta / "modelos" / info["version"] / ARCHIVO
            return ModeloVigente(Pronosticador.cargar(ruta), info["nombre"], info["alias"], info["version"], "cache")
        except (OSError, ValueError, KeyError, EOFError) as e:
            log.info("sin modelo en caché (%s)", type(e).__name__)
            return None

    def _cargar_version(self, version: str) -> ModeloVigente:
        destino = self.carpeta / "modelos" / version
        archivo = destino / ARCHIVO
        if archivo.is_file():
            p = Pronosticador.cargar(archivo)
        else:
            temporal = self.carpeta / "modelos" / f".{version}.descarga"
            p = entrenamiento.descargar(self.cfg.mlflow_uri, version, temporal)
            p.guardar(destino)
            shutil.rmtree(temporal, ignore_errors=True)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        tmp = self.indice.with_suffix(".tmp")
        tmp.write_text(json.dumps({"nombre": entrenamiento.NOMBRE_MODELO, "alias": entrenamiento.ALIAS,
                                   "version": version}))
        os.replace(tmp, self.indice)  # atómico: nunca queda un índice a medias
        return ModeloVigente(p, entrenamiento.NOMBRE_MODELO, entrenamiento.ALIAS, version, "mlflow")

    def actualizar(self, actual: ModeloVigente | None) -> tuple[ModeloVigente | None, str | None]:
        """(modelo a usar, motivo si no hay). Lanza excepción si MLflow no responde."""
        version = entrenamiento.version_vigente(self.cfg.mlflow_uri)
        if version is None:
            return actual, "todavía no hay un modelo con el alias champion (el primer arranque lo entrena)"
        if actual is not None and actual.version == version:
            return actual, None
        nuevo = self._cargar_version(version)
        log.info("modelo vigente: versión %s (antes %s)", version, actual.version if actual else "ninguna")
        return nuevo, None


class Estado:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cargador = Cargador(cfg)
        self.modelo: ModeloVigente | None = None
        self.motivo_sin_modelo = "el servicio está arrancando"
        self.catalogo: Catalogo | None = None
        self.catalogos: lectura.Catalogos | None = None
        self.salud: dict[str, str | None] = {"db": "sin revisar", "mlflow": "sin revisar", "airflow": "sin revisar"}
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._ultima_consulta_modelo = 0.0

    # --- ciclo en segundo plano

    def iniciar(self) -> None:
        if self.modelo is None:
            self.modelo = self.cargador.desde_cache()
            if self.modelo:
                log.info("modelo cargado desde la caché: versión %s", self.modelo.version)
        self._hilo = threading.Thread(target=self._ciclo, name="monitor", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()

    def _ciclo(self) -> None:
        while not self._detener.is_set():
            self.revisar()
            pausa = self.cfg.intervalo_salud_s if self.modelo else min(PAUSA_SIN_MODELO_S, self.cfg.intervalo_salud_s)
            self._detener.wait(pausa)

    def revisar(self) -> None:
        """Una pasada: salud, catálogo y (si toca) modelo. Cada paso es independiente: una falla en uno
        (p. ej. el catálogo mientras el inicializador carga) no impide los demás. No lanza excepciones."""
        try:
            self.salud = dependencias.revisar_todas(self.cfg)
        except Exception:  # noqa: BLE001 - el monitor nunca debe morir
            log.exception("falló la revisión de dependencias")
        if self.salud.get("db") is None:
            try:
                self.refrescar_catalogo()
            except Exception:  # noqa: BLE001
                log.exception("no se pudo cargar el catálogo")
        try:
            espera = PAUSA_SIN_MODELO_S if self.modelo is None else self.cfg.intervalo_modelo_s
            if self.salud.get("mlflow") is None and time.monotonic() - self._ultima_consulta_modelo >= espera:
                self._ultima_consulta_modelo = time.monotonic()
                self.modelo, motivo = self.cargador.actualizar(self.modelo)
                if motivo:
                    self.motivo_sin_modelo = motivo
            elif self.modelo is None and self.salud.get("mlflow"):
                self.motivo_sin_modelo = f"no hay modelo en caché y {self.salud['mlflow']}"
        except Exception as e:  # noqa: BLE001
            log.exception("no se pudo actualizar el modelo")
            if self.modelo is None:
                self.motivo_sin_modelo = f"no se pudo cargar el modelo ({type(e).__name__}: {e})"[:300]

    def refrescar_catalogo(self) -> None:
        """Carga el catálogo una vez y luego solo actualiza la última fecha con ventas (para el horizonte
        de fechas aceptadas, D12)."""
        with repositorio.conectar(self.cfg.db_url) as con:
            if self.catalogo is None:
                if repositorio.ultima_fecha_ventas(con) is None:
                    # El inicializador todavía no cargó el histórico (una sola transacción): reintentar luego.
                    log.info("catálogo pendiente: todavía no hay ventas cargadas")
                    return
                self.catalogo, self.catalogos = repositorio.catalogo(con)
                log.info("catálogo cargado: %d tiendas, %d familias", len(self.catalogo.tiendas),
                         len(self.catalogo.familias))
            else:
                ultima = repositorio.ultima_fecha_ventas(con)
                if ultima and ultima > self.catalogo.fecha_max_datos:
                    self.catalogo = replace(self.catalogo, fecha_max_datos=ultima)

    def ver_fecha_observada(self, fecha) -> None:
        if self.catalogo is not None and fecha > self.catalogo.fecha_max_datos:
            self.catalogo = replace(self.catalogo, fecha_max_datos=fecha)

    # --- lectura

    def resumen_salud(self) -> tuple[int, dict]:
        """(código HTTP, cuerpo) de GET /health según el contrato."""
        deps = {k: (v or "ok") for k, v in self.salud.items()}
        cuerpo = {"dependencias": deps,
                  "version_modelo": self.modelo.version if self.modelo else None,
                  "origen_modelo": self.modelo.origen if self.modelo else None}
        if self.modelo is None:
            return 503, {"estado": "sin_modelo", "motivo": self.motivo_sin_modelo, **cuerpo}
        fallas = [v for v in self.salud.values() if v]
        if self.catalogo is None:
            fallas.append("catálogo no cargado")
        if fallas:
            return 200, {"estado": "degradado", "motivo": "; ".join(fallas), **cuerpo}
        return 200, {"estado": "ok", **cuerpo}
