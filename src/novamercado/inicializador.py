"""Inicializador del producto: se ejecuta una vez en cada `docker compose up` y termina.

1. Espera a la base del producto.
2. Aplica el esquema (idempotente).
3. Carga los archivos publicados que no estén cargados con la misma huella.
4. Si no existe `@champion`, entrena y registra el primer modelo y lo promueve.

Volver a ejecutarlo no repite trabajo (D5). Uso: python -m novamercado.inicializador
"""

import logging
import sys
import time

import psycopg

from novamercado import config
from novamercado.datos import carga, lectura
from novamercado.modelo import entrenamiento

log = logging.getLogger("novamercado.inicializador")


def esperar_db(url: str, intentos: int = 30, pausa_s: float = 2.0) -> None:
    for i in range(1, intentos + 1):
        try:
            with psycopg.connect(url, connect_timeout=3) as con:
                con.execute("SELECT 1")
            return
        except psycopg.OperationalError as e:
            log.info("base no disponible (intento %d/%d): %s", i, intentos, type(e).__name__)
            time.sleep(pausa_s)
    raise RuntimeError("la base del producto no respondió")


CLAVE_MODELO_INICIAL = "modelo_inicial"


def mlflow_responde(uri: str, intentos: int, pausa_s: float = 3.0) -> bool:
    import httpx

    for i in range(1, intentos + 1):
        try:
            if httpx.get(f"{uri}/health", timeout=3).status_code == 200:
                return True
        except httpx.HTTPError as e:
            log.info("MLflow no disponible (intento %d/%d): %s", i, intentos, type(e).__name__)
        if i < intentos:
            time.sleep(pausa_s)
    return False


def asegurar_modelo_inicial(cfg: config.Config) -> str:
    """Garantiza que exista `@champion`. Devuelve lo que hizo.

    MLflow es la fuente de verdad; la marca en `estado_producto` solo sirve para no depender de él
    cuando no responde (si ya hubo un modelo, la API usa su caché). Casos:
    - champion existe: nada que hacer.
    - no hay champion pero sí una versión del inicializador (murió entre registrar y promover):
      se promueve esa versión, sin reentrenar.
    - no hay ninguna (primer arranque, o se perdió el volumen de MLflow): se entrena y promueve.
    """
    with psycopg.connect(cfg.db_url, autocommit=True) as con:
        marca = con.execute("SELECT valor FROM estado_producto WHERE clave = %s",
                            (CLAVE_MODELO_INICIAL,)).fetchone()
        # Con marca, esperar poco: si MLflow está caído no hace falta (la API tiene caché).
        if not mlflow_responde(cfg.mlflow_uri, intentos=4 if marca else 60):
            if marca:
                return f"MLflow no disponible; el modelo inicial ya se había registrado (versión {marca[0]})"
            raise RuntimeError("MLflow no respondió y todavía no hay un modelo registrado")
        vigente = entrenamiento.version_vigente(cfg.mlflow_uri)
        if vigente is not None:
            hecho = f"@{entrenamiento.ALIAS} vigente (versión {vigente})"
        elif (huerfana := entrenamiento.ultima_version(cfg.mlflow_uri, origen="inicializador")) is not None:
            entrenamiento.promover(cfg.mlflow_uri, huerfana)
            vigente = huerfana
            hecho = f"versión {huerfana} registrada sin promover: promovida sin reentrenar"
        else:
            t0 = time.perf_counter()
            res = entrenamiento.entrenar(lectura.ventas(con), lectura.catalogos(con))
            vigente = entrenamiento.registrar(res, cfg.mlflow_uri, origen="inicializador")
            entrenamiento.promover(cfg.mlflow_uri, vigente)
            log.info("primer modelo: versión %s, costo en validación %.0f (%.0f s)", vigente,
                     res.produccion.metricas["costo_total"], time.perf_counter() - t0)
            hecho = f"modelo entrenado y promovido (versión {vigente})"
        con.execute("INSERT INTO estado_producto (clave, valor) VALUES (%s, %s) ON CONFLICT (clave) "
                    "DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = now()", (CLAVE_MODELO_INICIAL, vigente))
        return hecho


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = config.leer()
    inicio = time.perf_counter()
    esperar_db(cfg.db_url)
    try:
        resumen = carga.preparar_base(cfg.db_url, cfg.datos_dir)
    except carga.ErrorDatosPublicados as e:
        log.error("%s", e)
        return 1
    for archivo, estado in resumen.items():
        log.info("%s: %s", archivo, estado)
    log.info("%s", asegurar_modelo_inicial(cfg))
    log.info("inicialización terminada en %.1f s", time.perf_counter() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
