"""Variables del modelo (D13). La misma función sirve para entrenar y para predecir.

Regla: las variables de la fila (tienda, familia, d) solo usan ventas de fechas < d. Se construye una
grilla diaria completa por serie y todo se calcula con desplazamientos hacia el pasado, así una venta
del mismo día nunca entra en sus propias variables (hay una prueba que lo verifica alterando el
futuro). Un día sin dato queda en NaN: los rezagos lo reflejan y las medias móviles lo saltan.
"""

import numpy as np
import pandas as pd

from novamercado.modelo import calendario

CLAVE = ["tienda_id", "familia_id"]
REZAGOS = (1, 2, 7, 14, 21, 28)
# Historia mínima que necesita una predicción: el rezago más largo y la ventana de 28 días.
DIAS_HISTORIA = 35

CATEGORICAS = ["tienda", "familia", "tipo_tienda", "evento", "dia_semana"]
NUMERICAS = (
    [f"lag_{k}" for k in REZAGOS]
    + ["media_7", "media_28", "mismo_dia_4sem", "desv_28", "dias_sin_dato", "en_promocion", "promo_lag_1"]
    + ["dia_mes", "mes", "dia_anio", "dias_al_fin_mes", "quincena"]
    + [f"ev_{t}" for t in calendario.TIPOS_EVENTO]
    + ["dias_a_evento", "dias_desde_evento"]
)
COLUMNAS = CATEGORICAS + NUMERICAS


def _grilla(ventas: pd.DataFrame, objetivos: pd.DataFrame) -> pd.DataFrame:
    """Grilla diaria completa por serie, desde su primer dato hasta la fecha objetivo más tardía."""
    conocidas = ventas[CLAVE + ["fecha", "ventas", "en_promocion"]]
    obj = objetivos[CLAVE + ["fecha"]]
    base = pd.concat([conocidas[CLAVE + ["fecha"]], obj], ignore_index=True)
    rangos = base.groupby(CLAVE)["fecha"].agg(["min", "max"]).reset_index()
    fin = obj["fecha"].max()
    partes = [
        pd.DataFrame({"tienda_id": r.tienda_id, "familia_id": r.familia_id,
                      "fecha": pd.date_range(r.min, max(r.max, fin) if pd.notna(fin) else r.max)})
        for r in rangos.itertuples(index=False)
    ]
    grilla = pd.concat(partes, ignore_index=True)
    return grilla.merge(conocidas, on=CLAVE + ["fecha"], how="left").sort_values(CLAVE + ["fecha"])


def construir(ventas: pd.DataFrame, objetivos: pd.DataFrame, tiendas: pd.DataFrame,
              feriados: pd.DataFrame, codigos: dict) -> pd.DataFrame:
    """Variables para cada fila de `objetivos` (tienda_id, familia_id, fecha, en_promocion).

    `ventas`: ventas conocidas (tienda_id, familia_id, fecha, ventas, en_promocion). Puede incluir
    fechas iguales o posteriores a los objetivos: no se usan para esas filas.
    `codigos`: codificación de categorías que guarda el modelo (familias, tiendas, tipos, eventos).
    Devuelve un DataFrame alineado con el índice de `objetivos`, con las columnas de COLUMNAS.
    """
    ventas = ventas.assign(fecha=pd.to_datetime(ventas["fecha"]))
    obj = objetivos.assign(fecha=pd.to_datetime(objetivos["fecha"]))
    g = _grilla(ventas, obj)
    s = g.groupby(CLAVE, sort=False)["ventas"]
    pasado = s.shift(1)  # ventas del día anterior: lo más reciente que se puede usar
    for k in REZAGOS:
        g[f"lag_{k}"] = s.shift(k)
    gp = pasado.groupby([g["tienda_id"], g["familia_id"]], sort=False)
    g["media_7"] = gp.transform(lambda x: x.rolling(7, min_periods=3).mean())
    g["media_28"] = gp.transform(lambda x: x.rolling(28, min_periods=7).mean())
    g["desv_28"] = gp.transform(lambda x: x.rolling(28, min_periods=7).std())
    g["mismo_dia_4sem"] = g[[f"lag_{k}" for k in (7, 14, 21, 28)]].mean(axis=1, skipna=True)
    # Días desde el último dato conocido antes de d (1 = hubo dato ayer).
    conocido = g["fecha"].where(g["ventas"].notna())
    ultimo = conocido.groupby([g["tienda_id"], g["familia_id"]], sort=False).transform(
        lambda x: x.shift(1).ffill())
    g["dias_sin_dato"] = (g["fecha"] - ultimo).dt.days
    g["promo_lag_1"] = g.groupby(CLAVE, sort=False)["en_promocion"].shift(1)

    cols = CLAVE + ["fecha"] + [c for c in g.columns if c.startswith(("lag_", "media_", "desv_", "mismo_"))] \
        + ["dias_sin_dato", "promo_lag_1"]
    unido = obj.reset_index().merge(g[cols], on=CLAVE + ["fecha"], how="left").set_index("index")

    out = pd.DataFrame(index=obj.index)
    tipo = tiendas.set_index("tienda_id")["tipo"]
    out["tienda"] = obj["tienda_id"].map(codigos["tiendas"]).astype(float)
    out["familia"] = obj["familia_id"].map(codigos["familias"]).astype(float)
    out["tipo_tienda"] = obj["tienda_id"].map(tipo).map(codigos["tipos_tienda"]).astype(float)
    for c in cols[3:]:
        out[c] = unido[c].astype(float)
    out["en_promocion"] = obj["en_promocion"].astype(float)
    cal = calendario.variables(obj, feriados, tiendas, codigos["eventos"])
    for c in cal.columns:
        out[c] = cal[c].astype(float)
    return out[COLUMNAS]


def codigos_desde(tiendas: pd.DataFrame, familias: pd.DataFrame, feriados: pd.DataFrame) -> dict:
    """Codificación estable de categorías (se guarda con el modelo)."""
    return {
        "tiendas": {int(t): i for i, t in enumerate(sorted(tiendas["tienda_id"]))},
        "familias": {f: i for i, f in enumerate(sorted(familias["familia_id"]))},
        "tipos_tienda": {t: i for i, t in enumerate(sorted(tiendas["tipo"].unique()))},
        "eventos": sorted(feriados["nombre"].unique()),
    }


def nivel(X: pd.DataFrame, respaldo: dict | None = None) -> np.ndarray:
    """Nivel reciente de la serie: media de 28 días o, si falta, lo más cercano disponible.

    Sin ninguna historia (serie nueva), `respaldo` da el nivel típico por "familia|tipo_tienda"
    (lo calcula el modelo al entrenar). Mínimo 1 para no dividir entre cero.
    """
    base = X["media_28"].fillna(X["media_7"]).fillna(X["mismo_dia_4sem"]).fillna(X["lag_1"])
    if respaldo:
        clave = X["familia"].astype("Int64").astype(str) + "|" + X["tipo_tienda"].astype("Int64").astype(str)
        base = base.fillna(clave.map(respaldo))
    return np.maximum(base.fillna(1.0).to_numpy(dtype=float), 1.0)


def con_historia(X: pd.DataFrame) -> pd.Series:
    """Filas cuya serie tiene nivel de 28 días definido (al menos 7 días con dato en la ventana)."""
    return X["media_28"].notna()
