"""Métrica de negocio (enunciado) y cantidad sugerida (D14).

costo = c_faltante · máx(real − sugerido, 0) + c_sobrante · máx(sugerido − real, 0), por tienda,
familia y día, con los costos de `costos.csv`.
"""

import numpy as np
import pandas as pd

# Factores candidatos para cantidad = ceil(venta_esperada · k). τ va de 0.29 a 0.95 (perfil de datos).
FACTORES = np.round(np.arange(0.50, 2.51, 0.01), 2)


def costo(real, sugerido, c_faltante, c_sobrante) -> np.ndarray:
    real = np.asarray(real, dtype=float)
    sugerido = np.asarray(sugerido, dtype=float)
    return (np.asarray(c_faltante) * np.maximum(real - sugerido, 0)
            + np.asarray(c_sobrante) * np.maximum(sugerido - real, 0))


def cantidad(venta_esperada, factor) -> np.ndarray:
    """Entero no negativo (contrato)."""
    v = np.ceil(np.maximum(np.asarray(venta_esperada, dtype=float), 0) * np.asarray(factor) - 1e-9)
    return v.astype(np.int64)


def elegir_factores(familia: pd.Series, venta_esperada, real, costos: pd.DataFrame) -> dict[str, float]:
    """Para cada familia, el factor k que minimiza el costo total en los datos dados (newsvendor
    empírico). Empate: el factor más cercano a 1."""
    c = costos.set_index("familia_id")
    df = pd.DataFrame({"familia": familia.to_numpy(), "pred": np.asarray(venta_esperada, float),
                       "real": np.asarray(real, float)})
    factores = {}
    for fam, g in df.groupby("familia"):
        cf, cs = c.loc[fam, "costo_faltante"], c.loc[fam, "costo_sobrante"]
        totales = np.array([costo(g["real"], cantidad(g["pred"], k), cf, cs).sum() for k in FACTORES])
        mejores = np.flatnonzero(totales == totales.min())
        factores[fam] = float(FACTORES[mejores[np.argmin(np.abs(FACTORES[mejores] - 1))]])
    return factores


def costo_por_fila(familia: pd.Series, real, sugerido, costos: pd.DataFrame) -> np.ndarray:
    c = costos.set_index("familia_id")
    return costo(real, sugerido, familia.map(c["costo_faltante"]).to_numpy(),
                 familia.map(c["costo_sobrante"]).to_numpy())
