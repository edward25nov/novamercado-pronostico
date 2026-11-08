"""Los ejemplos publicados (datos/publicados/ejemplos) con el catálogo publicado.
Se omiten si los archivos publicados no están (p. ej. en la CI)."""

import json

import pandas as pd
import pytest

from novamercado import config
from novamercado.calidad import Catalogo, Rechazo, estado, limpiar_observacion, limpiar_prediccion

DATOS = config.leer().datos_dir
pytestmark = pytest.mark.skipif(not (DATOS / "ejemplos").is_dir(), reason="archivos publicados no disponibles")

ESPERADO = {  # archivo -> estado esperado según DECISIONES.md D8
    "prediccion_valida": "ok", "observacion_valida": "ok",
    "E01_tienda_texto": "corregido", "E02_familia_otra_forma": "corregido", "E03_promocion_texto": "corregido",
    "E04_fecha_formato": "corregido", "E05_faltan_familias": "advertencia", "E06_familia_repetida": "advertencia",
    "E07_campo_renombrado": "corregido", "E08_ventas_negativas": "advertencia", "E09_envio_repetido": "ok",
    "E10_numero_formato": "corregido",
}


@pytest.fixture(scope="module")
def cat():
    h = pd.read_csv(DATOS / "historico_ventas.csv")
    resumen = h.groupby("familia_id").agg(promo_max=("en_promocion", "max"), ventas_max=("ventas", "max")).reset_index()
    return Catalogo.desde_tablas(pd.read_csv(DATOS / "tiendas.csv"), pd.read_csv(DATOS / "familias.csv"),
                                 pd.read_csv(DATOS / "costos.csv"), pd.read_csv(DATOS / "feriados.csv"),
                                 resumen, h["fecha"].min())


@pytest.mark.parametrize("nombre", sorted(ESPERADO))
def test_ejemplo_publicado(cat, nombre):
    ruta = next((DATOS / "ejemplos").rglob(f"{nombre}.json"))
    cuerpo = ruta.read_bytes()
    es_observacion = "ventas" in json.loads(cuerpo)
    funcion = limpiar_observacion if es_observacion else limpiar_prediccion
    try:
        sol, obs = funcion(cuerpo, cat)
    except Rechazo as r:
        pytest.fail(f"{nombre} se rechazó: {r.detalle}")
    assert estado(obs) == ESPERADO[nombre], [o.contrato() for o in obs]
    assert sol.tienda_id == 5 and str(sol.fecha) == "2025-11-17"
