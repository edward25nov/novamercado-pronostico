"""Modelos de Pydantic del contrato (Anexo del enunciado).

- Canónicos (`*Canonica`): lo que sale de la limpieza; estrictos, sin campos extra. Si una regla
  dejara pasar algo fuera del contrato, la validación lo detiene.
- Respuestas: lo que devuelve la API. Pueden tener campos adicionales, pero no omitir ni renombrar.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

NoNegativo = Annotated[int, Field(ge=0, strict=True)]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class FamiliaCanonica(_Estricto):
    familia_id: str
    en_promocion: NoNegativo


class PrediccionCanonica(_Estricto):
    tienda_id: int
    fecha: date
    familias: Annotated[list[FamiliaCanonica], Field(min_length=1)]


class VentaCanonica(_Estricto):
    familia_id: str
    ventas: NoNegativo


class ObservacionCanonica(_Estricto):
    tienda_id: int
    fecha: date
    ventas: Annotated[list[VentaCanonica], Field(min_length=1)]


# --- Respuestas del contrato

class ObservacionCalidad(BaseModel):
    campo: str
    accion: Literal["reparar", "advertir"]
    detalle: str


class Calidad(BaseModel):
    estado: Literal["ok", "corregido", "advertencia"]
    observaciones: list[ObservacionCalidad]


class PrediccionFamilia(BaseModel):
    familia_id: str
    venta_esperada: float
    cantidad_sugerida: NoNegativo


class RespuestaPrediccion(BaseModel):
    tienda_id: int
    fecha: date
    version_modelo: str
    predicciones: list[PrediccionFamilia]
    calidad: Calidad


class RespuestaObservaciones(BaseModel):
    registros_guardados: NoNegativo
    calidad: Calidad


class RespuestaRechazo(BaseModel):
    detail: str
