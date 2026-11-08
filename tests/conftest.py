"""Fixtures compartidas.

Las pruebas de base de datos necesitan un Postgres (no MLflow ni Airflow): definir
NOVAMERCADO_TEST_DB_URL, p. ej. con el contenedor de pruebas del README:
    docker run -d --name novamercado-pruebas-db -p 55432:5432 -e POSTGRES_PASSWORD=pruebas postgres:16.15
    export NOVAMERCADO_TEST_DB_URL=postgresql://postgres:pruebas@localhost:55432/postgres
Cada prueba trabaja en un esquema propio que se borra al terminar. Sin la variable, se omiten.
"""

import os
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest

DATOS_PRUEBA = Path(__file__).with_name("datos_prueba")


@pytest.fixture
def datos(tmp_path) -> Path:
    """Copia editable de los archivos de prueba (mismo formato que los publicados)."""
    destino = tmp_path / "publicados"
    shutil.copytree(DATOS_PRUEBA, destino)
    return destino


@pytest.fixture
def con():
    url = os.environ.get("NOVAMERCADO_TEST_DB_URL")
    if not url:
        pytest.skip("NOVAMERCADO_TEST_DB_URL no definida")
    esquema = f"prueba_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {esquema}")
    try:
        with psycopg.connect(url, autocommit=True, options=f"-c search_path={esquema}") as c:
            yield c
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f"DROP SCHEMA {esquema} CASCADE")
