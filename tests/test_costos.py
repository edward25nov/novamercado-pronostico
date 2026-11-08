import numpy as np
import pandas as pd

from novamercado.modelo import costos as C


def test_costo_del_enunciado():
    # faltan 10 unidades a 1.5 y sobran 0
    assert C.costo([100], [90], 1.5, 2.0)[0] == 15.0
    assert C.costo([100], [110], 1.5, 2.0)[0] == 20.0
    assert C.costo([100], [100], 1.5, 2.0)[0] == 0.0


def test_cantidad_es_entero_no_negativo():
    q = C.cantidad([612.4, 0.0, -3.0, 10.0], [1.05, 1.2, 1.0, 1.0])
    assert q.dtype.kind == "i"
    assert q.tolist() == [644, 0, 0, 10]


def test_factor_sigue_al_cuantil_critico():
    rng = np.random.default_rng(1)
    real = rng.poisson(100, size=4000)
    pred = np.full(len(real), 100.0)
    fam = pd.Series(["licores"] * 2000 + ["panaderia"] * 2000)
    costos = pd.DataFrame({"familia_id": ["licores", "panaderia"], "costo_faltante": [2.0, 1.0],
                           "costo_sobrante": [0.1, 2.5]})
    k = C.elegir_factores(fam, pred, real, costos)
    assert k["licores"] > 1.1   # τ = 0.95: sugerir por encima
    assert k["panaderia"] < 1.0  # τ = 0.29: sugerir por debajo
