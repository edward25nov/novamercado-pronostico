import numpy as np
import pandas as pd

from novamercado.modelo import entrenamiento as T
from novamercado.modelo import modelos as M
from novamercado.modelo import variables as V
from novamercado.modelo.pronosticador import Pronosticador
from tests import sinteticos


def _xy():
    cat = sinteticos.catalogos()
    v = sinteticos.ventas()
    cod = V.codigos_desde(cat.tiendas, cat.familias, cat.feriados)
    return v, cat, V.construir(v, v, cat.tiendas, cat.feriados, cod)


def test_gbm_predice_valores_finitos_y_acotados():
    v, cat, X = _xy()
    m = M.GBM(max_iter=50).ajustar(X, v["ventas"], v["fecha"])
    p = m.predecir(X)
    assert np.isfinite(p).all() and (p >= 0).all()
    assert p.max() < 10 * v["ventas"].max()


def test_serie_sin_historia_usa_nivel_de_respaldo():
    v, cat, X = _xy()
    m = M.GBM(max_iter=50).ajustar(X, v["ventas"], v["fecha"])
    sin_hist = X.iloc[[0]].copy()
    sin_hist[[c for c in X.columns if c.startswith(("lag_", "media_", "desv_", "mismo_"))]] = np.nan
    p = m.predecir(sin_hist)
    assert 0 < p[0] < 10 * v["ventas"].max()


def test_entrenar_y_pronosticador_guardado_predice_igual(tmp_path):
    cat = sinteticos.catalogos()
    v = sinteticos.ventas()
    res = T.entrenar(v, cat, n_ventanas=2)
    assert set(res.candidatos) == set(T.ESCALERA)
    assert res.pronosticador.info["fecha_corte"] == str(v["fecha"].max().date())
    obj = pd.DataFrame({"tienda_id": [1, 2], "familia_id": ["abarrotes", "panaderia"],
                        "fecha": [v["fecha"].max() + pd.Timedelta(days=1)] * 2, "en_promocion": [0, 3]})
    antes = res.pronosticador.predecir(v, obj, cat.tiendas, cat.feriados)
    copia = Pronosticador.cargar(res.pronosticador.guardar(tmp_path))
    despues = copia.predecir(v, obj, cat.tiendas, cat.feriados)
    pd.testing.assert_frame_equal(antes, despues)
    assert (despues["cantidad_sugerida"] >= 0).all() and despues["cantidad_sugerida"].dtype.kind == "i"
