"""Verificación de las dependencias externas de la API: base de datos, MLflow y Airflow.

Cada función devuelve None si la dependencia responde, o un texto con el motivo si no.
Nunca lanza excepciones: la API debe seguir respondiendo aunque una dependencia falle.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx
import psycopg

from novamercado.config import Config


def revisar_db(cfg: Config) -> str | None:
    try:
        with psycopg.connect(cfg.db_url, connect_timeout=max(1, int(cfg.timeout_dependencias_s))) as con:
            con.execute("SELECT 1")
        return None
    except Exception as e:  # noqa: BLE001 - cualquier fallo es "no disponible"
        return f"base de datos no disponible ({type(e).__name__})"


def _revisar_http(url: str, nombre: str, timeout: float) -> str | None:
    try:
        r = httpx.get(url, timeout=timeout)
        if r.status_code == 200:
            return None
        return f"{nombre} respondió {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return f"{nombre} no disponible ({type(e).__name__})"


def revisar_mlflow(cfg: Config) -> str | None:
    return _revisar_http(f"{cfg.mlflow_uri}/health", "MLflow", cfg.timeout_dependencias_s)


def revisar_airflow(cfg: Config) -> str | None:
    return _revisar_http(f"{cfg.airflow_url}/api/v2/monitor/health", "Airflow", cfg.timeout_dependencias_s)


REVISIONES = {"db": revisar_db, "mlflow": revisar_mlflow, "airflow": revisar_airflow}


def revisar_todas(cfg: Config) -> dict[str, str | None]:
    """Revisa las tres dependencias en paralelo: el peor caso es un timeout, no la suma de tres."""
    with ThreadPoolExecutor(max_workers=len(REVISIONES)) as ex:
        futuros = {nombre: ex.submit(f, cfg) for nombre, f in REVISIONES.items()}
        return {nombre: fut.result() for nombre, fut in futuros.items()}
