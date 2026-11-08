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


def test_artefacto_de_formato_anterior_sigue_cargando():
    """El estado de un pickle anterior, sin los atributos agregados después (info, version_formato),
    se completa con valores por defecto y el Pronosticador predice."""
    cat = sinteticos.catalogos()
    v = sinteticos.ventas()
    p = T.entrenar(v, cat, n_ventanas=1).pronosticador
    from novamercado.modelo.pronosticador import VERSION_FORMATO

    assert p.version_formato == VERSION_FORMATO and p.info["version_formato"] == VERSION_FORMATO
    estado_viejo = {k: val for k, val in p.__dict__.items() if k not in ("info", "version_formato")}
    cargado = Pronosticador.__new__(Pronosticador)
    cargado.__setstate__(estado_viejo)  # lo que hace pickle.load con un artefacto viejo
    assert cargado.version_formato == 0 and cargado.info == {}
    objetivo = pd.DataFrame({"tienda_id": [1], "familia_id": ["abarrotes"],
                             "fecha": [v["fecha"].max() + pd.Timedelta(days=1)], "en_promocion": [1]})
    assert cargado.predecir(v, objetivo, cat.tiendas, cat.feriados)["cantidad_sugerida"].iloc[0] >= 0


def test_gbm_entrena_con_columnas_constantes_o_vacias():
    v, cat, X = _xy()
    X = X.assign(evento=np.nan, ev_comercial=0.0)  # ningún evento en el periodo de entrenamiento
    p = M.GBM(max_iter=20).ajustar(X, v["ventas"], v["fecha"]).predecir(X)
    assert np.isfinite(p).all()


def test_gbm_de_formato_anterior_sin_columnas_predice():
    """Un GBM serializado en F3 no tiene `columnas` (entrenaba con todas): debe predecir igual."""
    import pickle

    v, cat, X = _xy()
    rng = np.random.default_rng(0)
    ruido = ["evento", "dia_semana", "tienda", "familia", "tipo_tienda"]  # categóricas: sin ruido
    X = X.apply(lambda c: c if c.name in ruido else c.fillna(0) + rng.random(len(c)) * 1e-3)
    X["evento"] = rng.integers(0, 2, len(X)).astype(float)  # ninguna columna constante, como en F3
    m = M.GBM(max_iter=30).ajustar(X, v["ventas"], v["fecha"])
    assert len(m.columnas) == len(m._entrada(X).columns)  # como en F3: todas las columnas
    estado = m.__dict__.copy()
    estado.pop("columnas")
    viejo = pickle.loads(pickle.dumps(m))
    viejo.__dict__.clear()
    viejo.__setstate__(estado)  # lo que hace pickle.load con un artefacto de F3
    assert viejo.columnas == []
    np.testing.assert_allclose(viejo.predecir(X), m.predecir(X))
