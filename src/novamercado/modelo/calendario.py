"""Variables de calendario por tienda y fecha (D13).

Solo dependen de la fecha, de `feriados.csv` y de la ciudad de la tienda: se conocen de antemano,
también para fechas futuras. Nunca usan el reloj del sistema.
"""

import numpy as np
import pandas as pd

TIPOS_EVENTO = ("feriado", "medio_dia", "comercial", "pago")
# Ventana (días) para la distancia al evento más cercano: captura vísperas y días posteriores.
VENTANA_EVENTO = 7


def eventos_por_tienda(feriados: pd.DataFrame, tiendas: pd.DataFrame) -> pd.DataFrame:
    """Un renglón por (tienda, fecha, evento). Los nacionales aplican a todas las tiendas; los
    locales, a las tiendas cuya `ciudad` coincide con el `ambito`."""
    f = feriados.assign(fecha=pd.to_datetime(feriados["fecha"]))
    t = tiendas[["tienda_id", "ciudad"]]
    nacionales = f[f["ambito"] == "nacional"].merge(t[["tienda_id"]], how="cross")
    locales = f[f["ambito"] != "nacional"].merge(t, left_on="ambito", right_on="ciudad")
    cols = ["tienda_id", "fecha", "nombre", "tipo"]
    return pd.concat([nacionales[cols], locales[cols]], ignore_index=True)


def variables(objetivos: pd.DataFrame, feriados: pd.DataFrame, tiendas: pd.DataFrame,
              nombres_evento: list[str]) -> pd.DataFrame:
    """Variables de calendario para cada fila de `objetivos` (columnas tienda_id, fecha).

    `nombres_evento` fija la codificación del evento (la guarda el modelo): un evento que el modelo
    no vio queda en NaN, pero conserva sus marcas por tipo y su distancia.
    """
    o = objetivos[["tienda_id", "fecha"]].copy()
    fecha = pd.to_datetime(o["fecha"])
    out = pd.DataFrame(index=o.index)
    out["dia_semana"] = fecha.dt.dayofweek
    out["dia_mes"] = fecha.dt.day
    out["mes"] = fecha.dt.month
    out["dia_anio"] = fecha.dt.dayofyear
    out["dias_al_fin_mes"] = (fecha.dt.days_in_month - fecha.dt.day).astype(int)
    # Quincena: el 15 y el último día del mes (D13); feriados.csv solo trae Bono 14 y aguinaldo.
    out["quincena"] = ((fecha.dt.day == 15) | (out["dias_al_fin_mes"] == 0)).astype(int)

    ev = eventos_por_tienda(feriados, tiendas)
    codigo = {n: i for i, n in enumerate(nombres_evento)}
    claves = pd.DataFrame({"tienda_id": o["tienda_id"].to_numpy(), "fecha": fecha.to_numpy()}, index=o.index)

    del_dia = ev.groupby(["tienda_id", "fecha"]).agg(
        nombre=("nombre", "first"), tipos=("tipo", lambda s: set(s))).reset_index()
    unido = claves.reset_index().merge(del_dia, on=["tienda_id", "fecha"], how="left").set_index("index")
    for tipo in TIPOS_EVENTO:
        out[f"ev_{tipo}"] = unido["tipos"].map(lambda s, t=tipo: int(isinstance(s, set) and t in s))
    out["evento"] = unido["nombre"].map(codigo).astype(float)  # NaN = sin evento o evento no visto

    # Distancia (con signo) al evento más cercano de tipo feriado, medio día o comercial, por tienda.
    relevantes = ev[ev["tipo"] != "pago"]
    out["dias_a_evento"] = np.nan
    out["dias_desde_evento"] = np.nan
    for tienda, idx in claves.groupby("tienda_id").groups.items():
        fechas_ev = np.sort(relevantes.loc[relevantes["tienda_id"] == tienda, "fecha"].unique())
        if len(fechas_ev) == 0:
            continue
        f = claves.loc[idx, "fecha"].to_numpy(dtype="datetime64[D]")
        fe = fechas_ev.astype("datetime64[D]")
        pos = np.searchsorted(fe, f)
        siguiente = np.where(pos < len(fe), (fe[np.minimum(pos, len(fe) - 1)] - f).astype(int), 10**6)
        anterior = np.where(pos > 0, (f - fe[np.maximum(pos - 1, 0)]).astype(int), 10**6)
        out.loc[idx, "dias_a_evento"] = np.where(siguiente <= VENTANA_EVENTO, siguiente, np.nan)
        out.loc[idx, "dias_desde_evento"] = np.where(anterior <= VENTANA_EVENTO, anterior, np.nan)
    return out
