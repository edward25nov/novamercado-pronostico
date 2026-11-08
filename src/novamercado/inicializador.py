"""Inicializador del producto: se ejecuta una vez en cada `docker compose up` y termina.

1. Espera a la base del producto.
2. Aplica el esquema (idempotente).
3. Carga los archivos publicados que no estén cargados con la misma huella.
(F3: si no existe `@champion`, entrena y registra el primer modelo.)

Volver a ejecutarlo no repite trabajo (D5). Uso: python -m novamercado.inicializador
"""

import logging
import sys
import time

import psycopg

from novamercado import config
from novamercado.datos import carga

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
    log.info("inicialización terminada en %.1f s", time.perf_counter() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
