"""Modelos candidatos: baseline y gradient boosting (D13, D22).

Interfaz común: ajustar(X, y, fechas) y predecir(X) -> venta esperada (>= 0, en unidades).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from novamercado.modelo import variables as V


class Baseline:
    """Media de las ventas del mismo día de la semana en las 4 semanas anteriores.
    Si falta, el nivel reciente de la serie."""

    nombre = "baseline_mismo_dia_4sem"

    def __init__(self):
        self.respaldo: dict = {}

    def ajustar(self, X, y, fechas):
        self.respaldo = nivel_respaldo(X, y, fechas)
        return self

    def predecir(self, X: pd.DataFrame) -> np.ndarray:
        base = X["mismo_dia_4sem"].to_numpy(dtype=float)
        return np.where(np.isnan(base), V.nivel(X, self.respaldo), base).clip(min=0)

    def parametros(self) -> dict:
        return {}


ESCALABLES = [f"lag_{k}" for k in V.REZAGOS] + ["media_7", "media_28", "mismo_dia_4sem", "desv_28"]


# Tope del objetivo relativo al entrenar: el percentil 99,9 real de ventas / nivel es ~1,8 con
# historia suficiente; los valores extremos vienen de series sin historia (nivel mínimo).
TOPE_RATIO_ENTRENAMIENTO = 10.0


def nivel_respaldo(X: pd.DataFrame, y, fechas) -> dict:
    """Venta media por "familia|tipo_tienda" en los últimos 28 días de entrenamiento."""
    f = pd.to_datetime(pd.Series(np.asarray(fechas), index=X.index))
    reciente = f >= f.max() - pd.Timedelta(days=27)
    clave = X["familia"].astype("Int64").astype(str) + "|" + X["tipo_tienda"].astype("Int64").astype(str)
    return pd.Series(np.asarray(y, float), index=X.index)[reciente].groupby(clave[reciente]).mean().to_dict()


def sin_escala(X: pd.DataFrame, con_nivel: bool, respaldo: dict | None = None) -> pd.DataFrame:
    """Divide rezagos y medias entre el nivel reciente: el modelo aprende patrones relativos, que se
    mantienen cuando la demanda cambia de nivel (D13)."""
    Z = X[V.COLUMNAS].copy()
    n = V.nivel(X, respaldo)
    for c in ESCALABLES:
        Z[c] = Z[c] / n
    if con_nivel:
        Z["log_nivel"] = np.log(n)
    return Z


class GBM:
    """HistGradientBoosting global (todas las tiendas y familias).

    objetivo="directo": ventas con pérdida Poisson.
    objetivo="relativo": ventas / nivel reciente (D13), pérdida Poisson; se multiplica de vuelta.
    `vida_media_dias`: peso de cada fila = 0.5 ** (antigüedad / vida_media); None = sin pesos.
    """

    def __init__(self, objetivo="relativo", vida_media_dias=None, escala="relativa", learning_rate=0.05,
                 max_iter=600, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0, semilla=0):
        self.objetivo = objetivo
        self.vida_media_dias = vida_media_dias
        # escala: "absoluta" (variables en unidades), "relativa" (rezagos / nivel) o
        # "relativa_nivel" (rezagos / nivel y además log del nivel). Solo con objetivo relativo.
        self.escala = escala
        self.hp = dict(learning_rate=learning_rate, max_iter=max_iter, max_leaf_nodes=max_leaf_nodes,
                       min_samples_leaf=min_samples_leaf, l2_regularization=l2_regularization)
        self.semilla = semilla
        self.modelo = None
        self.respaldo: dict = {}
        self.ratio_max: float | None = None
        self.columnas: list[str] = []

    def __setstate__(self, estado: dict):
        # Compatibilidad con artefactos anteriores (D24): atributos agregados después de F3.
        # columnas = [] significa "todas las de la entrada" (como entrenaban las versiones de F3).
        base = {"columnas": [], "respaldo": {}, "ratio_max": None, "escala": "absoluta"}
        self.__dict__.update({**base, **estado})

    @property
    def nombre(self):
        pesos = f"_vm{self.vida_media_dias}" if self.vida_media_dias else ""
        escala = "" if self.escala == "absoluta" else f"_{self.escala}"
        return f"gbm_{self.objetivo}{escala}{pesos}"

    def parametros(self) -> dict:
        return {"objetivo": self.objetivo, "escala": self.escala, "vida_media_dias": self.vida_media_dias,
                **self.hp}

    def _entrada(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.escala == "absoluta":
            return X[V.COLUMNAS]
        return sin_escala(X, con_nivel=self.escala == "relativa_nivel", respaldo=self.respaldo)

    def ajustar(self, X: pd.DataFrame, y, fechas):
        y = np.asarray(y, dtype=float)
        fechas = pd.Series(pd.to_datetime(np.asarray(fechas)), index=X.index)
        self.respaldo = nivel_respaldo(X, y, fechas)
        # Solo filas con historia: sin nivel, el objetivo relativo pierde sentido (y puede desbordar
        # la liga logarítmica de Poisson).
        usar = V.con_historia(X).to_numpy()
        X, y, fechas = X[usar], y[usar], fechas[usar]
        if self.objetivo == "relativo":
            objetivo = np.clip(y / V.nivel(X, self.respaldo), 0, TOPE_RATIO_ENTRENAMIENTO)
            self.ratio_max = float(np.quantile(objetivo, 0.999) * 1.5)
        else:
            objetivo = y
            self.ratio_max = None
        pesos = None
        if self.vida_media_dias:
            antiguedad = (fechas.max() - fechas).dt.days.to_numpy()
            pesos = 0.5 ** (antiguedad / self.vida_media_dias)
        Z = self._entrada(X)
        # Solo columnas con más de un valor: una constante (p. ej. ningún evento comercial en el periodo)
        # no aporta y hace fallar al binning de scikit-learn 1.9.1. Se guarda la lista para predecir.
        self.columnas = [c for c in Z.columns if Z[c].nunique(dropna=True) > 1]
        self.modelo = HistGradientBoostingRegressor(
            loss="poisson", categorical_features=[c in V.CATEGORICAS for c in self.columnas],
            random_state=self.semilla, early_stopping=False, **self.hp)
        self.modelo.fit(Z[self.columnas], objetivo, sample_weight=pesos)
        return self

    def predecir(self, X: pd.DataFrame) -> np.ndarray:
        Z = self._entrada(X)
        p = self.modelo.predict(Z[self.columnas] if self.columnas else Z)
        if self.objetivo == "relativo":
            # Tope de seguridad: ninguna predicción supera 1,5 veces el ratio extremo visto al entrenar.
            p = np.clip(p, 0, self.ratio_max) * V.nivel(X, self.respaldo)
        return np.clip(np.nan_to_num(p, nan=0.0, posinf=0.0), 0, None)
