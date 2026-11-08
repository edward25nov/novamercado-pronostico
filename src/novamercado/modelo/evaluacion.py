"""Validación temporal común a todos los modelos (D22).

Origen móvil: N ventanas consecutivas de 28 días que terminan en la última fecha con ventas. Para
cada ventana, el modelo se entrena con filas de fechas anteriores a su inicio y predice la ventana
un día a la vez con las ventas reales hasta el día anterior, igual que en producción (las
variables ya están construidas así). Todos los modelos ven exactamente las mismas filas.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from novamercado.modelo import costos as C

DIAS_VENTANA = 28


@dataclass(frozen=True)
class Ventana:
    inicio: pd.Timestamp
    fin: pd.Timestamp  # inclusive

    def __str__(self):
        return f"{self.inicio.date()}..{self.fin.date()}"


def ventanas(ultima_fecha, n: int, dias: int = DIAS_VENTANA) -> list[Ventana]:
    fin = pd.Timestamp(ultima_fecha)
    out = []
    for i in range(n):
        f = fin - pd.Timedelta(days=dias * i)
        out.append(Ventana(f - pd.Timedelta(days=dias - 1), f))
    return out[::-1]


def predecir_ventanas(fabrica, X: pd.DataFrame, y, fechas: pd.Series, vs: list[Ventana]) -> pd.Series:
    """Predicciones fuera de muestra para las filas de las ventanas (índice de X)."""
    fechas = pd.to_datetime(fechas)
    partes = []
    for v in vs:
        entrenar = (fechas < v.inicio) & pd.Series(np.isfinite(np.asarray(y, float)), index=X.index)
        evaluar = (fechas >= v.inicio) & (fechas <= v.fin)
        modelo = fabrica().ajustar(X[entrenar], np.asarray(y)[entrenar.to_numpy()], fechas[entrenar])
        partes.append(pd.Series(modelo.predecir(X[evaluar]), index=X.index[evaluar]))
    return pd.concat(partes)


def metricas(real, pred, sugerido, familia: pd.Series, costos: pd.DataFrame) -> dict[str, float]:
    real = np.asarray(real, float)
    pred = np.asarray(pred, float)
    err = pred - real
    costo = C.costo_por_fila(familia, real, sugerido, costos)
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "wape": float(np.sum(np.abs(err)) / max(np.sum(real), 1)),
        "sesgo": float(np.sum(err) / max(np.sum(real), 1)),
        "costo_total": float(costo.sum()),
        "costo_medio": float(costo.mean()),
    }
