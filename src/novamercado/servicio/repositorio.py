"""Operaciones de la API sobre la base del producto (registro de la operación, D6 y D20)."""

import json
from datetime import date, timedelta

import pandas as pd
import psycopg

from novamercado.calidad import Catalogo
from novamercado.calidad.esquemas import ObservacionCanonica, PrediccionCanonica
from novamercado.calidad.resultado import Observacion
from novamercado.datos import lectura
from novamercado.modelo import variables as V

# Ventas anteriores a la fecha pedida que se leen para construir las variables (rezago de 28 días y
# media de 28, con margen). Con más historia las variables no cambian: solo miran 28 días atrás.
DIAS_HISTORIA_PREDICCION = 2 * V.DIAS_HISTORIA


def conectar(url: str, timeout_s: int = 3) -> psycopg.Connection:
    return psycopg.connect(url, connect_timeout=timeout_s, autocommit=True)


# --- catálogo para la limpieza

def catalogo(con: psycopg.Connection) -> tuple[Catalogo, lectura.Catalogos]:
    cats = lectura.catalogos(con)
    resumen = lectura._df(con, "SELECT familia_id, COALESCE(max(en_promocion), 0) AS promo_max, "
                               "max(ventas) AS ventas_max FROM ventas GROUP BY familia_id")
    rango = con.execute("SELECT min(fecha), max(fecha) FROM ventas").fetchone()
    cat = Catalogo.desde_tablas(cats.tiendas, cats.familias, cats.costos, cats.feriados, resumen, rango[0], rango[1])
    return cat, cats


def ultima_fecha_ventas(con: psycopg.Connection) -> date | None:
    """Última fecha con ventas, o None si no hay ventas (o si el esquema aún no existe)."""
    try:
        return con.execute("SELECT max(fecha) FROM ventas").fetchone()[0]
    except psycopg.errors.UndefinedTable:
        return None


# --- predicción

def ultima_promocion(con: psycopg.Connection, tienda_id: int, familia_id: str, fecha: date) -> int | None:
    """Última promoción conocida para la tienda y familia hasta `fecha` (D9): la de la solicitud más
    reciente para una fecha <= `fecha` o, si es más reciente, la del histórico. Nunca mira fechas
    posteriores (una solicitud adelantada no define el pasado)."""
    fila = con.execute(
        "SELECT en_promocion FROM ("
        "  SELECT fecha, id, en_promocion FROM predicciones WHERE tienda_id = %(t)s AND familia_id = %(f)s "
        "    AND fecha <= %(d)s "
        "  UNION ALL "
        "  SELECT fecha, -1 AS id, en_promocion FROM ventas WHERE tienda_id = %(t)s AND familia_id = %(f)s "
        "    AND fecha < %(d)s AND en_promocion IS NOT NULL"
        ") x ORDER BY fecha DESC, id DESC LIMIT 1", {"t": tienda_id, "f": familia_id, "d": fecha}).fetchone()
    return int(fila[0]) if fila else None


def ventas_para_predecir(con: psycopg.Connection, tienda_id: int, fecha: date) -> pd.DataFrame:
    """Ventas de la tienda en los días anteriores a `fecha` (nunca la fecha misma ni posteriores)."""
    return lectura.ventas(con, desde=fecha - timedelta(days=DIAS_HISTORIA_PREDICCION), hasta_excluida=fecha,
                          tienda_id=tienda_id)


# --- registro

def registrar_solicitud(con: psycopg.Connection, endpoint: str, cuerpo: bytes, codigo: int,
                        canonica=None, estado: str | None = None, detalle: str | None = None,
                        observaciones: list[Observacion] = ()) -> int:
    texto = cuerpo.decode("utf-8", errors="replace") if isinstance(cuerpo, (bytes, bytearray)) else str(cuerpo)
    normalizado = json.dumps(canonica.model_dump(mode="json"), ensure_ascii=False) if canonica is not None else None
    sid = con.execute(
        "INSERT INTO solicitudes (endpoint, cuerpo_crudo, cuerpo_normalizado, tienda_id, fecha, codigo_http, "
        "estado_calidad, detalle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (endpoint, texto.replace("\x00", ""), normalizado, getattr(canonica, "tienda_id", None),
         getattr(canonica, "fecha", None), codigo, estado, detalle)).fetchone()[0]
    if observaciones:
        with con.cursor() as cur:
            cur.executemany("INSERT INTO correcciones (solicitud_id, campo, accion, detalle) VALUES (%s, %s, %s, %s)",
                            [(sid, o.campo, o.accion, o.detalle) for o in observaciones])
    return sid


def registrar_predicciones(con: psycopg.Connection, solicitud_id: int, sol: PrediccionCanonica,
                           resultado: pd.DataFrame, version: str) -> None:
    promos = {f.familia_id: f.en_promocion for f in sol.familias}
    with con.cursor() as cur:
        cur.executemany(
            "INSERT INTO predicciones (solicitud_id, tienda_id, fecha, familia_id, en_promocion, venta_esperada, "
            "cantidad_sugerida, version_modelo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(solicitud_id, sol.tienda_id, sol.fecha, r.familia_id, promos[r.familia_id], float(r.venta_esperada),
              int(r.cantidad_sugerida), version) for r in resultado.itertuples(index=False)])


def guardar_observacion(con: psycopg.Connection, solicitud_id: int, obs: ObservacionCanonica) -> int:
    """Inserta o actualiza las ventas del día. Devuelve cuántas filas son nuevas o cambiaron (D6):
    reenviar lo mismo (o lo que ya estaba en el histórico) devuelve 0. Un cambio de valor queda en
    `ventas_historial`. Seguro ante envíos simultáneos (INSERT … ON CONFLICT y SELECT … FOR UPDATE)."""
    guardados = 0
    with con.transaction():
        for v in obs.ventas:
            clave = (obs.tienda_id, obs.fecha, v.familia_id)
            nueva = con.execute(
                "INSERT INTO ventas (tienda_id, fecha, familia_id, ventas, origen, solicitud_id) "
                "VALUES (%s, %s, %s, %s, 'observacion', %s) ON CONFLICT DO NOTHING RETURNING 1",
                (*clave, v.ventas, solicitud_id)).fetchone()
            if nueva:
                guardados += 1
                continue
            anterior = con.execute(
                "SELECT ventas FROM ventas WHERE tienda_id = %s AND fecha = %s AND familia_id = %s FOR UPDATE",
                clave).fetchone()[0]
            if anterior == v.ventas:
                continue
            con.execute(
                "UPDATE ventas SET ventas = %s, origen = 'observacion', solicitud_id = %s, actualizado_en = now() "
                "WHERE tienda_id = %s AND fecha = %s AND familia_id = %s", (v.ventas, solicitud_id, *clave))
            con.execute(
                "INSERT INTO ventas_historial (tienda_id, fecha, familia_id, ventas_anterior, ventas_nueva, "
                "solicitud_id) VALUES (%s, %s, %s, %s, %s, %s)", (*clave, anterior, v.ventas, solicitud_id))
            guardados += 1
    return guardados
