"""Configuración del producto, leída de variables de entorno (ver .env.example).

Los valores por defecto sirven para desarrollo local y pruebas; en Docker los define el compose.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    db_url: str
    mlflow_uri: str
    airflow_url: str
    airflow_usuario: str
    airflow_clave: str
    timeout_dependencias_s: float


def leer() -> Config:
    return Config(
        db_url=os.environ.get("NOVAMERCADO_DB_URL", "postgresql://novamercado:novamercado@localhost:5432/novamercado"),
        mlflow_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        airflow_url=os.environ.get("AIRFLOW_URL", "http://localhost:8080"),
        airflow_usuario=os.environ.get("AIRFLOW_USUARIO", "admin"),
        airflow_clave=os.environ.get("AIRFLOW_CLAVE", "admin"),
        timeout_dependencias_s=float(os.environ.get("TIMEOUT_DEPENDENCIAS_S", "3")),
    )
