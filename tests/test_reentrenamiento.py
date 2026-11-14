"""Preparación de datos para reentrenar (D26) y criterio de reemplazo (D15), sin MLflow."""

import math

import numpy as np
import pandas as pd

from novamercado.modelo import preparacion
from novamercado.reentrenamiento import MARGEN, decidir_reemplazo


def _ventas():
    fechas = pd.date_range("2025-01-01", periods=6)
    return pd.DataFrame({
        "tienda_id": 1, "familia_id": "abarrotes", "fecha": fechas,
        "ventas": [100.0, 110, 120, 99999, 130, 125],
        "en_promocion": [2, 3, np.nan, np.nan, np.nan, 5],
        "origen": ["historico", "historico", "observacion", "observacion", "observacion", "observacion"]})


def test_excluye_observaciones_atipicas_pero_no_el_historico():
    v = _ventas()
    v.loc[1, "ventas"] = 400  # el máximo histórico de la familia sube a 400: tope 1200
    p, resumen = preparacion.preparar(v)
    assert 99999 not in p["ventas"].to_list() and 400 in p["ventas"].to_list()
    assert resumen["filas_atipicas_excluidas"] == 1


def test_imputa_la_promocion_faltante_con_la_ultima_conocida():
    p, resumen = preparacion.preparar(_ventas())
    assert p["en_promocion"].to_list() == [2, 3, 3, 3, 5]  # la fila atípica ya no está
    assert resumen["promociones_imputadas"] == 2


def test_sin_promocion_previa_se_imputa_cero():
    v = _ventas().assign(en_promocion=np.nan)
    assert preparacion.preparar(v)[0]["en_promocion"].eq(0).all()


def test_promueve_si_mejora_al_menos_el_margen():
    promover, motivo = decidir_reemplazo(18_210, 19_940, 3360, "3", "2026-05-04..2026-05-31")
    assert promover and motivo.startswith("Costo en validación 18 210 vs 19 940 del vigente")


def test_no_promueve_si_la_mejora_es_menor_al_margen():
    vigente = 10_000
    promover, motivo = decidir_reemplazo(vigente * (1 - MARGEN / 2), vigente, 100, "3", "v")
    assert not promover and "se conserva el vigente" in motivo


def test_no_promueve_si_empeora():
    assert not decidir_reemplazo(12_000, 10_000, 100, "3", "v")[0]


def test_sin_vigente_o_vigente_que_no_predice_se_promueve():
    assert decidir_reemplazo(10_000, None, 100, None, "v")[0]
    assert decidir_reemplazo(10_000, None, 100, "3", "v")[0]
    assert decidir_reemplazo(10_000, math.inf, 100, "3", "v")[0]


def test_retador_sin_filas_o_con_costo_invalido_no_se_promueve():
    assert not decidir_reemplazo(10_000, 20_000, 0, "3", "v")[0]
    assert not decidir_reemplazo(math.nan, 20_000, 100, "3", "v")[0]
