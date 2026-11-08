"""Configuración del producto, leída de variables de entorno (ver .env.example).

Los valores por defecto sirven para desarrollo local y pruebas; en Docker los define el compose.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode

RAIZ_REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    db_url: str
    mlflow_uri: str
    airflow_url: str
    airflow_usuario: str
    airflow_clave: str
    timeout_dependencias_s: float
    datos_dir: Path
    cache_dir: Path                # copia local del modelo vigente (D17)
    intervalo_salud_s: float       # cada cuánto el monitor revisa las dependencias
    intervalo_modelo_s: float      # cada cuánto se consulta el alias champion


def url_db() -> str:
    """URL de la base del producto armada desde sus partes; usuario y clave van codificados
    para que una clave con @, : o / no rompa la URL."""
    usuario = quote(os.environ.get("PRODUCTO_DB_USUARIO", "novamercado"), safe="")
    clave = quote(os.environ.get("PRODUCTO_DB_CLAVE", "novamercado"), safe="")
    host = os.environ.get("PRODUCTO_DB_HOST", "localhost")
    puerto = os.environ.get("PRODUCTO_DB_PUERTO", "5432")
    nombre = quote(os.environ.get("PRODUCTO_DB_NOMBRE", "novamercado"), safe="")
    url = f"postgresql://{usuario}:{clave}@{host}:{puerto}/{nombre}"
    # Opciones de libpq (p. ej. "-c search_path=prueba_x"): las usan las pruebas para aislar esquemas.
    if opciones := os.environ.get("PRODUCTO_DB_OPCIONES"):
        url += "?" + urlencode({"options": opciones}, quote_via=quote)  # espacios como %20, no '+'
    return url


def leer() -> Config:
    return Config(
        db_url=url_db(),
        mlflow_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        airflow_url=os.environ.get("AIRFLOW_URL", "http://localhost:8080"),
        airflow_usuario=os.environ.get("AIRFLOW_USUARIO", "admin"),
        airflow_clave=os.environ.get("AIRFLOW_CLAVE", "admin"),
        timeout_dependencias_s=float(os.environ.get("TIMEOUT_DEPENDENCIAS_S", "3")),
        datos_dir=Path(os.environ.get("NOVAMERCADO_DATOS", RAIZ_REPO / "datos" / "publicados")),
        cache_dir=Path(os.environ.get("NOVAMERCADO_CACHE", "/cache" if Path("/cache").is_dir() else
                                      RAIZ_REPO / ".cache")),
        intervalo_salud_s=float(os.environ.get("INTERVALO_SALUD_S", "15")),
        intervalo_modelo_s=float(os.environ.get("INTERVALO_MODELO_S", "30")),
    )
