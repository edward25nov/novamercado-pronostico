"""Resultado de la limpieza: observaciones de calidad y rechazos (D7)."""

from dataclasses import dataclass

REPARAR = "reparar"
ADVERTIR = "advertir"


@dataclass(frozen=True)
class Observacion:
    campo: str      # ruta del dato tal como llegó, p. ej. "familias[2].familia_id"
    accion: str     # "reparar" | "advertir"
    detalle: str
    regla: str      # clase de problema (D8); se registra, no forma parte del contrato

    def contrato(self) -> dict:
        return {"campo": self.campo, "accion": self.accion, "detalle": self.detalle}


class Rechazo(Exception):
    """La solicitud no se puede responder: 422 con `detail` (D7)."""

    def __init__(self, detalle: str, campo: str | None = None, regla: str = "rechazo"):
        super().__init__(detalle)
        self.detalle = detalle
        self.campo = campo
        self.regla = regla


def estado(observaciones: list[Observacion]) -> str:
    """ok sin observaciones; advertencia si alguna es advertir; si no, corregido (contrato)."""
    if not observaciones:
        return "ok"
    if any(o.accion == ADVERTIR for o in observaciones):
        return "advertencia"
    return "corregido"


class Registro:
    """Acumula observaciones durante la limpieza."""

    def __init__(self):
        self.observaciones: list[Observacion] = []

    def reparar(self, campo: str, detalle: str, regla: str):
        self.observaciones.append(Observacion(campo, REPARAR, detalle, regla))

    def advertir(self, campo: str, detalle: str, regla: str):
        self.observaciones.append(Observacion(campo, ADVERTIR, detalle, regla))
