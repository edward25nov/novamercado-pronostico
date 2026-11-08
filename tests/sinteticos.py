"""Datos sintéticos pequeños con la estructura de los publicados (para pruebas del modelo)."""

import numpy as np
import pandas as pd

from novamercado.datos.lectura import Catalogos


def catalogos() -> Catalogos:
    tiendas = pd.DataFrame({
        "tienda_id": [1, 2], "nombre": ["A", "B"], "ciudad": ["Guatemala", "Cobán"],
        "departamento": ["Guatemala", "Alta Verapaz"], "tipo": ["hipermercado", "express"],
        "fecha_apertura": ["2019-01-01", "2019-01-01"]})
    familias = pd.DataFrame({"familia_id": ["abarrotes", "panaderia"], "nombre": ["Abarrotes", "Panadería"]})
    feriados = pd.DataFrame({"fecha": pd.to_datetime(["2025-03-20", "2025-04-04"]),
                             "nombre": ["Feriado X", "Feria de Cobán"], "tipo": ["feriado", "feriado"],
                             "ambito": ["nacional", "Cobán"]})
    costos = pd.DataFrame({"familia_id": ["abarrotes", "panaderia"], "costo_faltante": [1.0, 1.0],
                           "costo_sobrante": [0.2, 2.5]})
    return Catalogos(tiendas, familias, feriados, costos)


def ventas(dias: int = 150, semilla: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    fechas = pd.date_range("2025-01-01", periods=dias)
    filas = []
    for t, base_t in [(1, 300), (2, 60)]:
        for f, base_f in [("abarrotes", 1.0), ("panaderia", 0.5)]:
            promo = rng.integers(0, 5, size=dias)
            semana = 1 + 0.3 * (fechas.dayofweek >= 5)
            media = base_t * base_f * semana * (1 + 0.05 * promo)
            filas.append(pd.DataFrame({"tienda_id": t, "familia_id": f, "fecha": fechas,
                                       "ventas": rng.poisson(media).astype(float), "en_promocion": promo}))
    return pd.concat(filas, ignore_index=True)
