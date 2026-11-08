"""El artefacto que se registra en MLflow y que usa la API.

Un `Pronosticador` reúne todo lo que hace falta para pasar de ventas conocidas a la respuesta:
la codificación de categorías, el modelo, los factores de cantidad sugerida por familia (D14) y
la información de su entrenamiento. Cambiar de champion cambia todo eso junto.
"""

import pickle
from dataclasses import dataclass, field
from pathlib import Path

import mlflow.pyfunc
import numpy as np
import pandas as pd

from novamercado.modelo import costos as C
from novamercado.modelo import variables as V

ARCHIVO = "pronosticador.pkl"
# Sube cuando cambian los atributos del Pronosticador; __setstate__ completa los que falten en
# artefactos de versiones anteriores, para que un champion viejo siga cargando.
VERSION_FORMATO = 2  # 2: GBM.columnas (F5); los atributos nuevos tienen valor por defecto al cargar


@dataclass
class Pronosticador:
    modelo: object                      # Baseline o GBM (interfaz ajustar/predecir)
    codigos: dict                       # codificación de categorías (variables.codigos_desde)
    factores: dict[str, float]          # factor k por familia: cantidad = ceil(venta · k)
    info: dict = field(default_factory=dict)  # fecha de corte, ventanas, métricas, etc.
    version_formato: int = VERSION_FORMATO

    def __setstate__(self, estado: dict):
        # Valores por defecto de atributos agregados después de serializar (compatibilidad).
        base = {"info": {}, "version_formato": 0}
        self.__dict__.update({**base, **estado})

    def variables(self, ventas: pd.DataFrame, objetivos: pd.DataFrame, tiendas: pd.DataFrame,
                  feriados: pd.DataFrame) -> pd.DataFrame:
        return V.construir(ventas, objetivos, tiendas, feriados, self.codigos)

    def predecir(self, ventas: pd.DataFrame, objetivos: pd.DataFrame, tiendas: pd.DataFrame,
                 feriados: pd.DataFrame) -> pd.DataFrame:
        """objetivos: tienda_id, familia_id, fecha, en_promocion. ventas: solo fechas anteriores
        importan (las posteriores se ignoran por construcción). Devuelve venta_esperada (1 decimal)
        y cantidad_sugerida (entero >= 0), alineadas con `objetivos`."""
        X = self.variables(ventas, objetivos, tiendas, feriados)
        venta = np.round(self.modelo.predecir(X), 1)
        factor = objetivos["familia_id"].map(self.factores).fillna(1.0).to_numpy()
        return pd.DataFrame({"venta_esperada": venta, "cantidad_sugerida": C.cantidad(venta, factor)},
                            index=objetivos.index)

    def guardar(self, carpeta: Path) -> Path:
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / ARCHIVO
        # pickle estándar (no joblib/dill): lección del Lab 1 dentro de Airflow (D3).
        with ruta.open("wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
        return ruta

    @staticmethod
    def cargar(ruta: Path) -> "Pronosticador":
        with Path(ruta).open("rb") as f:
            return pickle.load(f)  # noqa: S301 - artefacto propio, de nuestro MLflow


class EnvolturaPyfunc(mlflow.pyfunc.PythonModel):
    """Envoltura mínima para registrar el Pronosticador como modelo de MLflow.

    El servicio no usa `predict` de pyfunc: carga el Pronosticador del artefacto, porque necesita
    las ventas conocidas y los catálogos además de la solicitud.
    """

    def load_context(self, context):
        self.pronosticador = Pronosticador.cargar(context.artifacts["pronosticador"])

    def predict(self, context, model_input, params=None):
        raise NotImplementedError("usar Pronosticador.predecir con ventas y catálogos")
