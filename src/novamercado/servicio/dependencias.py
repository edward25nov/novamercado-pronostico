"""Verificación de las dependencias externas de la API: base de datos, MLflow y Airflow.

Cada función devuelve None si la dependencia responde, o un texto con el motivo si no.
Nunca lanza excepciones: la API debe seguir respondiendo aunque una dependencia falle.
"""

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


def revisar_todas(cfg: Config) -> dict[str, str | None]:
    return {"db": revisar_db(cfg), "mlflow": revisar_mlflow(cfg), "airflow": revisar_airflow(cfg)}
