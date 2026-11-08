"""Perfil de los archivos publicados: genera docs/perfil_datos.md.

Uso:
    python scripts/perfilar_datos.py [carpeta_datos]   (por defecto datos/publicados)

Solo lee los archivos; los números que respaldan DECISIONES.md salen de aquí.
"""

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


def tabla(df: pd.DataFrame) -> str:
    """DataFrame -> tabla Markdown (sin depender de tabulate)."""
    cols = [str(c) for c in df.columns]
    filas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        filas.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(filas)


def main(carpeta: Path) -> str:
    h = pd.read_csv(carpeta / "historico_ventas.csv", parse_dates=["fecha"])
    tiendas = pd.read_csv(carpeta / "tiendas.csv")
    familias = pd.read_csv(carpeta / "familias.csv")
    feriados = pd.read_csv(carpeta / "feriados.csv", parse_dates=["fecha"])
    costos = pd.read_csv(carpeta / "costos.csv")

    out = ["# Perfil de los datos publicados", "",
           "Generado con `python scripts/perfilar_datos.py`. No editar a mano.", ""]

    # Histórico
    dias = pd.date_range(h.fecha.min(), h.fecha.max())
    out += ["## Histórico de ventas", "",
            f"- Filas: {len(h):,}; fechas {h.fecha.min().date()} a {h.fecha.max().date()} "
            f"({h.fecha.nunique()} días; faltan {len(set(dias) - set(h.fecha))}).",
            f"- Tiendas: {h.tienda_id.nunique()}; familias: {h.familia_id.nunique()}; "
            f"combinaciones tienda×familia: {h.groupby(['tienda_id', 'familia_id']).ngroups}.",
            f"- Nulos: {int(h.isna().sum().sum())}; duplicados (fecha, tienda, familia): "
            f"{int(h.duplicated(['fecha', 'tienda_id', 'familia_id']).sum())}; "
            f"ventas negativas: {int((h.ventas < 0).sum())}; ventas en cero: {int((h.ventas == 0).sum())}.",
            ""]
    por_tienda = (h.groupby("tienda_id").agg(desde=("fecha", "min"), hasta=("fecha", "max"),
                                              filas=("ventas", "size"), venta_media=("ventas", "mean"))
                  .reset_index().merge(tiendas[["tienda_id", "ciudad", "tipo", "fecha_apertura"]]))
    por_tienda["desde"] = por_tienda.desde.dt.date
    por_tienda["hasta"] = por_tienda.hasta.dt.date
    por_tienda["venta_media"] = por_tienda.venta_media.round(1)
    out += ["### Por tienda", "", tabla(por_tienda), ""]

    por_familia = (h.groupby("familia_id").agg(
        venta_media=("ventas", "mean"), desv=("ventas", "std"), maximo=("ventas", "max"),
        promo_max=("en_promocion", "max"),
        pct_dias_con_promo=("en_promocion", lambda s: (s > 0).mean() * 100))
        .round(1).reset_index())
    out += ["### Por familia", "", tabla(por_familia), ""]

    # Patrones de calendario
    total = h.groupby("fecha").ventas.sum()
    mensual = total.resample("MS").mean().round(0).astype(int)
    anual = (mensual.iloc[12:].values / mensual.iloc[:12].values - 1) * 100
    out += ["## Patrones", "",
            f"- Crecimiento interanual de la venta diaria total (mes contra mismo mes): "
            f"mediana {pd.Series(anual).median():.1f} %.",
            ""]
    dow = (h.assign(d=h.fecha.dt.dayofweek).groupby("d").ventas.mean())
    dow = (dow / dow.mean()).round(2)
    nombres = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    out += ["- Índice por día de la semana (1 = promedio): "
            + ", ".join(f"{nombres[i]} {v}" for i, v in dow.items()) + "."]
    dom = h.assign(d=h.fecha.dt.day).groupby("d").ventas.mean()
    dom = (dom / dom.median()).round(2)
    out += ["- Índice por día del mes (1 = mediana); los mayores: "
            + ", ".join(f"día {i}: {v}" for i, v in dom.sort_values(ascending=False).head(6).items())
            + ". La quincena (15) y el fin de mes suben aunque `feriados.csv` solo marca "
            f"{int((feriados.tipo == 'pago').sum())} fechas de pago (Bono 14 y aguinaldo).", ""]

    # Efecto de feriados: venta total del día / media de los 14 días previos
    filas = []
    for _, f in feriados[(feriados.fecha >= h.fecha.min()) & (feriados.fecha <= h.fecha.max())].iterrows():
        if f.ambito == "nacional":
            serie = total
        else:
            ids = tiendas.loc[tiendas.ciudad == f.ambito, "tienda_id"]
            serie = h[h.tienda_id.isin(ids)].groupby("fecha").ventas.sum()
        previo = serie[(serie.index < f.fecha) & (serie.index >= f.fecha - pd.Timedelta(days=14))].mean()
        filas.append({"fecha": f.fecha.date(), "nombre": f.nombre, "tipo": f.tipo, "ambito": f.ambito,
                      "indice": round(serie.get(f.fecha) / previo, 2)})
    out += ["### Efecto de feriados y fechas especiales en el histórico", "",
            "`indice` = venta del día / media de los 14 días previos (tiendas del ámbito).", "",
            tabla(pd.DataFrame(filas)), "",
            f"- `feriados.csv` cubre de {feriados.fecha.min().date()} a {feriados.fecha.max().date()}; "
            f"ámbitos locales: {sorted(feriados.loc[feriados.ambito != 'nacional', 'ambito'].unique())}, "
            f"todos presentes en `tiendas.ciudad`: "
            f"{set(feriados.ambito) - {'nacional'} <= set(tiendas.ciudad)}.", ""]

    # Promociones
    h = h.sort_values(["tienda_id", "familia_id", "fecha"])
    g = h.groupby(["tienda_id", "familia_id"])
    h["promo_ayer"] = g.en_promocion.shift()
    h["nivel28"] = g.ventas.transform(lambda s: s.shift().rolling(28).mean())
    h["ratio"] = h.ventas / h.nivel28
    efecto = h.groupby(pd.cut(h.en_promocion, [-1, 0, 2, 5, 10, 20]), observed=True).ratio.mean().round(2)
    out += ["## Promociones", "",
            f"- Correlación de `en_promocion` con la del día anterior: "
            f"{h[['en_promocion', 'promo_ayer']].corr().iloc[0, 1]:.2f}; "
            f"igual al día anterior en {(h.en_promocion == h.promo_ayer).mean() * 100:.0f} % de las filas.",
            "- Venta relativa a la media de los 28 días previos, por número de productos en promoción: "
            + ", ".join(f"{k}: {v}" for k, v in efecto.items()) + ".", ""]

    # Costos
    c = costos.copy()
    c["tau_critico"] = (c.costo_faltante / (c.costo_faltante + c.costo_sobrante)).round(3)
    out += ["## Costos", "",
            "`tau_critico` = c_faltante / (c_faltante + c_sobrante): cuantil de la demanda que minimiza el "
            "costo esperado (newsvendor). Mayor a 0.5 = conviene sugerir por encima del pronóstico.", "",
            tabla(c), ""]

    # Catálogos y ejemplos
    out += ["## Catálogos y ejemplos", "",
            f"- Familias: {', '.join(familias.familia_id)} (nombres con tildes y espacios: "
            f"{', '.join(familias.nombre)}).",
            f"- Tiendas: {len(tiendas)}; tipos {tiendas.tipo.value_counts().to_dict()}.", ""]
    ej = json.loads((carpeta / "ejemplos" / "observacion_valida.json").read_text())
    hist = h[(h.tienda_id == ej["tienda_id"]) & (h.fecha == ej["fecha"])].set_index("familia_id").ventas
    errores = sorted(p.stem for p in (carpeta / "ejemplos" / "errores").glob("*.json"))
    iguales = sum(int(v["ventas"]) == int(hist.get(v["familia_id"], -1)) for v in ej["ventas"])
    out += [f"- `ejemplos/observacion_valida.json` ({ej['tienda_id']}, {ej['fecha']}): {iguales} de "
            f"{len(ej['ventas'])} valores son idénticos al histórico.",
            f"- Ejemplos de error: {', '.join(errores)}.",
            ""]
    return "\n".join(out)


if __name__ == "__main__":
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "datos" / "publicados"
    destino = RAIZ / "docs" / "perfil_datos.md"
    destino.write_text(main(carpeta), encoding="utf-8")
    print(f"escrito {destino}")
