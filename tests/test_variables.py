import numpy as np
import pandas as pd

from novamercado.modelo import calendario
from novamercado.modelo import variables as V
from tests import sinteticos


def _datos():
    cat = sinteticos.catalogos()
    return sinteticos.ventas(), cat, V.codigos_desde(cat.tiendas, cat.familias, cat.feriados)


def test_no_usa_ventas_del_mismo_dia_ni_futuras():
    v, cat, cod = _datos()
    obj = v[v["fecha"] == "2025-03-01"]
    X1 = V.construir(v, obj, cat.tiendas, cat.feriados, cod)
    alterado = v.copy()
    alterado.loc[alterado["fecha"] >= "2025-03-01", "ventas"] = 99999
    X2 = V.construir(alterado, obj, cat.tiendas, cat.feriados, cod)
    pd.testing.assert_frame_equal(X1, X2)


def test_rezago_1_es_el_dia_anterior_y_hueco_queda_en_nan():
    v, cat, cod = _datos()
    sin_ayer = v[~((v["fecha"] == "2025-03-09") & (v["tienda_id"] == 1))]
    obj = v[(v["fecha"] == "2025-03-10") & (v["tienda_id"] == 1)]
    X = V.construir(sin_ayer, obj, cat.tiendas, cat.feriados, cod)
    assert X["lag_1"].isna().all()
    assert (X["dias_sin_dato"] == 2).all()
    esperado = v[(v["fecha"] == "2025-03-08") & (v["tienda_id"] == 1)]["ventas"].to_numpy()
    assert np.array_equal(X["lag_2"].to_numpy(), esperado)


def test_prediccion_de_fecha_futura_sin_venta_ese_dia():
    v, cat, cod = _datos()
    manana = v["fecha"].max() + pd.Timedelta(days=1)
    obj = pd.DataFrame({"tienda_id": [1], "familia_id": ["abarrotes"], "fecha": [manana],
                        "en_promocion": [2]})
    X = V.construir(v, obj, cat.tiendas, cat.feriados, cod)
    assert X["lag_1"].notna().all() and X["media_28"].notna().all()
    assert X["en_promocion"].iloc[0] == 2


def test_feriado_local_solo_en_su_ciudad():
    cat = sinteticos.catalogos()
    fechas = pd.to_datetime(["2025-04-04"] * 2 + ["2025-03-20"] * 2)
    obj = pd.DataFrame({"tienda_id": [1, 2, 1, 2], "fecha": fechas})
    cal = calendario.variables(obj, cat.feriados, cat.tiendas, sorted(cat.feriados["nombre"]))
    assert cal["ev_feriado"].tolist() == [0, 1, 1, 1]  # Cobán solo para la tienda 2; el nacional para ambas
    # La feria de Cobán es "hoy" para la tienda 2; para la tienda 1 el evento más cercano está a 15 días
    assert cal.loc[1, "dias_a_evento"] == 0
    assert np.isnan(cal.loc[0, "dias_a_evento"])


def test_quincena_y_fin_de_mes():
    cat = sinteticos.catalogos()
    fechas = pd.to_datetime(["2025-02-15", "2025-02-28", "2025-02-27", "2025-03-31"])
    obj = pd.DataFrame({"tienda_id": [1, 1, 1, 1], "fecha": fechas})
    cal = calendario.variables(obj, cat.feriados, cat.tiendas, [])
    assert cal["quincena"].tolist() == [1, 1, 0, 1]


def test_evento_no_visto_queda_en_nan_pero_marca_el_tipo():
    cat = sinteticos.catalogos()
    obj = pd.DataFrame({"tienda_id": [1], "fecha": pd.to_datetime(["2025-03-20"])})
    cal = calendario.variables(obj, cat.feriados, cat.tiendas, ["Otro evento"])
    assert np.isnan(cal["evento"].iloc[0]) and cal["ev_feriado"].iloc[0] == 1
