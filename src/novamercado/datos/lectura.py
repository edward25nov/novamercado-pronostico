"""Lectura de la base del producto para entrenar y predecir."""

from dataclasses import dataclass

import pandas as pd
import psycopg

# en_promocion: el del histórico o, para las observaciones (que no lo traen), el de la última
# solicitud de pronóstico registrada para esa tienda, familia y fecha (D13, D20).
SQL_VENTAS = """
SELECT v.tienda_id, v.familia_id, v.fecha, v.ventas,
       COALESCE(v.en_promocion, p.en_promocion) AS en_promocion, v.origen
FROM ventas v
LEFT JOIN LATERAL (
    SELECT en_promocion FROM predicciones p
    WHERE p.tienda_id = v.tienda_id AND p.fecha = v.fecha AND p.familia_id = v.familia_id
    ORDER BY p.id DESC LIMIT 1
) p ON true
{filtro}
ORDER BY v.tienda_id, v.familia_id, v.fecha
"""


@dataclass
class Catalogos:
    tiendas: pd.DataFrame
    familias: pd.DataFrame
    feriados: pd.DataFrame
    costos: pd.DataFrame


def _df(con: psycopg.Connection, consulta: str, params=None) -> pd.DataFrame:
    cur = con.execute(consulta, params)
    cols = [c.name for c in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)


def catalogos(con: psycopg.Connection) -> Catalogos:
    tiendas = _df(con, "SELECT * FROM tiendas ORDER BY tienda_id")
    feriados = _df(con, "SELECT * FROM feriados ORDER BY fecha")
    feriados["fecha"] = pd.to_datetime(feriados["fecha"])
    return Catalogos(
        tiendas=tiendas,
        familias=_df(con, "SELECT * FROM familias ORDER BY familia_id"),
        feriados=feriados,
        costos=_df(con, "SELECT * FROM costos ORDER BY familia_id"),
    )


def ventas(con: psycopg.Connection, desde=None, hasta_excluida=None, tienda_id=None) -> pd.DataFrame:
    """Ventas conocidas, opcionalmente en [desde, hasta_excluida) y de una tienda."""
    condiciones, params = [], []
    if desde is not None:
        condiciones.append("v.fecha >= %s")
        params.append(desde)
    if hasta_excluida is not None:
        condiciones.append("v.fecha < %s")
        params.append(hasta_excluida)
    if tienda_id is not None:
        condiciones.append("v.tienda_id = %s")
        params.append(tienda_id)
    filtro = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    df = _df(con, SQL_VENTAS.format(filtro=filtro), params)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["ventas"] = df["ventas"].astype(float)
    df["en_promocion"] = pd.to_numeric(df["en_promocion"]).astype(float)
    return df
