"""Configuración del producto, leída de variables de entorno (ver .env.example).

Los valores por defecto sirven para desarrollo local y pruebas; en Docker los define el compose.
"""

import os
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class Config:
    db_url: str
    mlflow_uri: str
    airflow_url: str
    airflow_usuario: str
    airflow_clave: str
    timeout_dependencias_s: float


def url_db() -> str:
    """URL de la base del producto armada desde sus partes; usuario y clave van codificados
    para que una clave con @, : o / no rompa la URL."""
    usuario = quote(os.environ.get("PRODUCTO_DB_USUARIO", "novamercado"), safe="")
    clave = quote(os.environ.get("PRODUCTO_DB_CLAVE", "novamercado"), safe="")
    host = os.environ.get("PRODUCTO_DB_HOST", "localhost")
    puerto = os.environ.get("PRODUCTO_DB_PUERTO", "5432")
    nombre = quote(os.environ.get("PRODUCTO_DB_NOMBRE", "novamercado"), safe="")
    return f"postgresql://{usuario}:{clave}@{host}:{puerto}/{nombre}"


def leer() -> Config:
    return Config(
        db_url=url_db(),
        mlflow_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        airflow_url=os.environ.get("AIRFLOW_URL", "http://localhost:8080"),
        airflow_usuario=os.environ.get("AIRFLOW_USUARIO", "admin"),
        airflow_clave=os.environ.get("AIRFLOW_CLAVE", "admin"),
        timeout_dependencias_s=float(os.environ.get("TIMEOUT_DEPENDENCIAS_S", "3")),
    )
