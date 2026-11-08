"""Lo que la limpieza necesita saber de los catálogos y del histórico.

Se arma una vez (desde la base o desde DataFrames) y la limpieza solo lo lee: así las reglas
son funciones puras y se prueban sin base de datos.
"""

import difflib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from novamercado.calidad.normalizar import clave

# Historia mínima antes de la primera fecha que se puede pronosticar (D12): la ventana de 28 días.
DIAS_HISTORIA_MINIMA = 28
SIMILITUD_MINIMA = 0.8


@dataclass(frozen=True)
class Tienda:
    tienda_id: int
    nombre: str
    ciudad: str
    fecha_apertura: date


@dataclass
class Catalogo:
    tiendas: dict[int, Tienda]
    familias: dict[str, str]                 # familia_id -> nombre
    tau: dict[str, float]                    # cuantil crítico por familia (D10)
    promo_max: dict[str, int]                # máximo histórico de en_promocion por familia
    ventas_max: dict[str, int]               # máximo histórico de ventas por familia
    fecha_min_datos: date                    # primer día del histórico
    fecha_max_calendario: date               # último día de feriados.csv
    _claves_familia: dict[str, str] = field(default_factory=dict, repr=False)
    _claves_tienda: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        for fid, nombre in self.familias.items():
            for c in {clave(fid), clave(nombre), clave(fid).replace("_", ""), clave(nombre).replace("_", "")}:
                self._claves_familia.setdefault(c, fid)
        for t in self.tiendas.values():
            sin_marca = re.sub(r"^novamercado_?", "", clave(t.nombre))
            for c in {clave(t.nombre), sin_marca, sin_marca.replace("_", "")}:
                self._claves_tienda.setdefault(c, t.tienda_id)

    @property
    def fecha_min_prediccion(self) -> date:
        return self.fecha_min_datos + timedelta(days=DIAS_HISTORIA_MINIMA)

    # --- familias

    def familia_exacta(self, texto: str) -> str | None:
        """Familia cuya forma normalizada (id o nombre) coincide con el texto."""
        c = clave(texto)
        return self._claves_familia.get(c) or self._claves_familia.get(c.replace("_", ""))

    def familia_parecida(self, texto: str) -> str | None:
        """Única familia suficientemente parecida (p. ej. 'lacteo', 'panaderias'), o None."""
        return _parecido(clave(texto), self._claves_familia)

    # --- tiendas

    def tienda_por_nombre(self, texto: str) -> tuple[int | None, bool]:
        """(tienda, aproximado). Coincidencia exacta del nombre (con o sin 'NovaMercado') o única
        parecida."""
        c = re.sub(r"^novamercado_?", "", clave(texto))
        if c in self._claves_tienda:
            return self._claves_tienda[c], False
        parecida = _parecido(c, self._claves_tienda)
        return parecida, parecida is not None

    def tiendas_en_ciudad(self, texto: str) -> list[int]:
        c = clave(texto)
        return [t.tienda_id for t in self.tiendas.values() if clave(t.ciudad) == c]

    @classmethod
    def desde_tablas(cls, tiendas: pd.DataFrame, familias: pd.DataFrame, costos: pd.DataFrame,
                     feriados: pd.DataFrame, resumen_ventas: pd.DataFrame, fecha_min_datos) -> "Catalogo":
        """resumen_ventas: familia_id, promo_max, ventas_max."""
        c = costos.set_index("familia_id")
        r = resumen_ventas.set_index("familia_id")
        return cls(
            tiendas={int(t.tienda_id): Tienda(int(t.tienda_id), t.nombre, t.ciudad,
                                              pd.Timestamp(t.fecha_apertura).date())
                     for t in tiendas.itertuples(index=False)},
            familias=dict(zip(familias["familia_id"], familias["nombre"], strict=True)),
            tau={f: float(c.loc[f, "costo_faltante"] / (c.loc[f, "costo_faltante"] + c.loc[f, "costo_sobrante"]))
                 for f in c.index},
            promo_max={f: int(r.loc[f, "promo_max"]) for f in r.index},
            ventas_max={f: int(r.loc[f, "ventas_max"]) for f in r.index},
            fecha_min_datos=pd.Timestamp(fecha_min_datos).date(),
            fecha_max_calendario=pd.to_datetime(feriados["fecha"]).max().date(),
        )


def _parecido(c: str, opciones: dict) -> object | None:
    """Valor de la única opción con similitud >= SIMILITUD_MINIMA y claramente mejor que la segunda."""
    if not c:
        return None
    puntajes = {}
    for k, valor in opciones.items():
        r = difflib.SequenceMatcher(None, c, k).ratio()
        puntajes[valor] = max(puntajes.get(valor, 0.0), r)
    orden = sorted(puntajes.items(), key=lambda kv: kv[1], reverse=True)
    if not orden or orden[0][1] < SIMILITUD_MINIMA:
        return None
    if len(orden) > 1 and orden[1][1] >= orden[0][1] - 0.05:
        return None  # dos candidatos casi igual de parecidos: ambiguo
    return orden[0][0]
