"""Preparación de las ventas para entrenar (D26).

- Ventas atípicas: una observación mayor a FACTOR_ATIPICO veces el máximo histórico de su familia se
  guardó (no se descarta un dato real, D8) pero no entra al entrenamiento: un error de captura
  (p. ej. 99 999) deformaría el modelo. Es la misma regla que marca `ventas_atipicas` en la limpieza.
- Promoción faltante: las observaciones no traen `en_promocion`; se toma de la solicitud de
  pronóstico del día (lectura.SQL_VENTAS). Si no hubo solicitud, se imputa con la última promoción
  conocida de la serie (D9) y, si no hay ninguna, 0.
"""

import pandas as pd

from novamercado.calidad.solicitudes import FACTOR_ATIPICO

CLAVE = ["tienda_id", "familia_id"]


def preparar(ventas: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Devuelve (ventas para entrenar, resumen de lo que se hizo)."""
    v = ventas.sort_values(CLAVE + ["fecha"]).reset_index(drop=True)
    origen = v["origen"] if "origen" in v else pd.Series("historico", index=v.index)
    historico = v[origen == "historico"]
    tope = (historico if len(historico) else v).groupby("familia_id")["ventas"].max()
    atipica = (origen == "observacion") & (v["ventas"] > FACTOR_ATIPICO * v["familia_id"].map(tope))
    v = v[~atipica.fillna(False)].reset_index(drop=True)

    faltante = v["en_promocion"].isna()
    v["en_promocion"] = v.groupby(CLAVE, sort=False)["en_promocion"].ffill().fillna(0)
    return v, {"filas_atipicas_excluidas": int(atipica.sum()), "promociones_imputadas": int(faltante.sum())}
