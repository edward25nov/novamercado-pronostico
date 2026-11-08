"""Catálogo de prueba armado a mano con la misma estructura que el publicado (no son los datos
publicados): 12 familias con sus ids, y tiendas con una ciudad de tres tiendas y una abierta tarde."""

from datetime import date

import pandas as pd

from novamercado.calidad import Catalogo

FAMILIAS = {
    "abarrotes": "Abarrotes", "bebidas": "Bebidas", "lacteos": "Lácteos", "carnes": "Carnes",
    "panaderia": "Panadería", "frutas_verduras": "Frutas y verduras", "limpieza": "Limpieza",
    "cuidado_personal": "Cuidado personal", "licores": "Licores", "snacks": "Snacks y dulces",
    "bebe": "Bebé", "mascotas": "Mascotas",
}
TAU_BAJO = {"lacteos", "carnes", "panaderia", "frutas_verduras"}  # cuesta más sobrar


def catalogo() -> Catalogo:
    tiendas = pd.DataFrame([
        (1, "NovaMercado Zona 10", "Guatemala", "2019-01-01"),
        (2, "NovaMercado Mixco", "Mixco", "2019-01-01"),
        (4, "NovaMercado Express Zona 1", "Guatemala", "2019-01-01"),
        (5, "NovaMercado Quetzaltenango", "Quetzaltenango", "2019-01-01"),
        (8, "NovaMercado Cobán", "Cobán", "2019-01-01"),
        (10, "NovaMercado Express Zona 16", "Guatemala", "2025-03-15"),
    ], columns=["tienda_id", "nombre", "ciudad", "fecha_apertura"])
    familias = pd.DataFrame(list(FAMILIAS.items()), columns=["familia_id", "nombre"])
    costos = pd.DataFrame([(f, 1.0, 2.0 if f in TAU_BAJO else 0.2) for f in FAMILIAS],
                          columns=["familia_id", "costo_faltante", "costo_sobrante"])
    feriados = pd.DataFrame({"fecha": ["2024-03-28", "2026-12-31"]})
    resumen = pd.DataFrame([(f, 19, 3000) for f in FAMILIAS], columns=["familia_id", "promo_max", "ventas_max"])
    return Catalogo.desde_tablas(tiendas, familias, costos, feriados, resumen, date(2024, 3, 1))


def prediccion(**cambios) -> dict:
    """Solicitud válida (tienda 5, 2025-11-17, las 12 familias) con cambios opcionales."""
    base = {"tienda_id": 5, "fecha": "2025-11-17",
            "familias": [{"familia_id": f, "en_promocion": 8 if f == "bebidas" else 0} for f in FAMILIAS]}
    base.update(cambios)
    return base


def observacion(**cambios) -> dict:
    base = {"tienda_id": 5, "fecha": "2025-11-17",
            "ventas": [{"familia_id": f, "ventas": 100 + i} for i, f in enumerate(FAMILIAS)]}
    base.update(cambios)
    return base
