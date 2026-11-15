"""Preparación de datos para reentrenar (D26) y criterio de reemplazo (D15), sin MLflow."""

import math

import numpy as np
import pandas as pd

from novamercado.modelo import preparacion
from novamercado.reentrenamiento import MIN_DIAS_NUEVOS, TOLERANCIA, decidir_reemplazo


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


def test_promueve_si_el_retador_es_mejor():
    promover, motivo = decidir_reemplazo(18_210, 19_940, 3360, "3", "2026-05-04..2026-05-31", 28)
    assert promover and motivo.startswith("Costo en validación 18 210 vs 19 940 del vigente")


def test_no_inferioridad_promueve_un_empate():
    assert decidir_reemplazo(10_000 * (1 + TOLERANCIA / 2), 10_000, 100, "3", "v", 10)[0]


def test_no_promueve_si_es_peor_por_mas_de_la_tolerancia():
    promover, motivo = decidir_reemplazo(10_000 * (1 + 2 * TOLERANCIA), 10_000, 100, "3", "v", 10)
    assert not promover and "se conserva el vigente" in motivo


def test_sin_dias_nuevos_suficientes_no_se_compara():
    for dias in (None, 0, MIN_DIAS_NUEVOS - 1):
        promover, motivo = decidir_reemplazo(1, 10_000, 100, "3", "v", dias)
        assert not promover and "días de ventas posteriores al corte" in motivo
    assert decidir_reemplazo(1, 10_000, 100, "3", "v", MIN_DIAS_NUEVOS)[0]


def test_sin_vigente_o_vigente_que_no_predice_se_promueve():
    assert decidir_reemplazo(None, None, 0, None, "v", None)[0]
    assert decidir_reemplazo(10_000, None, 100, "3", "v", 10)[0]
    assert decidir_reemplazo(10_000, math.inf, 100, "3", "v", 10)[0]


def test_retador_sin_filas_o_con_costo_invalido_no_se_promueve():
    assert not decidir_reemplazo(10_000, 20_000, 0, "3", "v", 10)[0]
    assert not decidir_reemplazo(math.nan, 20_000, 100, "3", "v", 10)[0]


def test_comparacion_fuera_de_muestra_no_usa_los_dias_comparados():
    """El modelo de comparación del retador se entrena solo con filas anteriores a `comparar_desde`."""
    from novamercado.modelo import entrenamiento as T
    from tests import sinteticos

    cat, v = sinteticos.catalogos(), sinteticos.ventas()
    desde = v["fecha"].max() - pd.Timedelta(days=9)
    alterado = v.copy()
    alterado.loc[alterado["fecha"] >= desde, "ventas"] *= 3  # cambiar los días comparados
    a = T.entrenar(v, cat, n_ventanas=1, comparar_desde=desde).comparacion
    b = T.entrenar(alterado, cat, n_ventanas=1, comparar_desde=desde).comparacion
    assert len(a) == 10 * 4 and (a["fecha"] >= desde).all()
    # el primer día comparado solo depende de datos anteriores: misma predicción con el futuro alterado
    primero = a["fecha"] == desde
    np.testing.assert_allclose(a.loc[primero, "venta_esperada"], b.loc[primero, "venta_esperada"])
