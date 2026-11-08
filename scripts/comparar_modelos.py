"""Comparación de modelos que respalda D13, D14 y D22: genera docs/comparacion_modelos.md.

Uso:
    python scripts/comparar_modelos.py [carpeta_datos]   (por defecto datos/publicados)

1. Escalera con validación temporal (4 ventanas de 28 días): costo, WAPE y sesgo.
2. Robustez ante cambios de demanda: el modelo se entrena hasta 2026-01-03 y se evalúa del
   2026-01-18 al 2026-02-28 sobre ventas alteradas desde 2026-01-04 (sin reentrenar).
3. Variantes de la cantidad sugerida.
No usa MLflow ni la base de datos: lee los CSV publicados.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from novamercado.datos.lectura import Catalogos
from novamercado.modelo import costos as C
from novamercado.modelo import entrenamiento as T
from novamercado.modelo import evaluacion as E
from novamercado.modelo import modelos as M
from novamercado.modelo import variables as V

RAIZ = Path(__file__).resolve().parents[1]
EXTRA = {
    "gbm_relativo_sin_escala_vm180": lambda: M.GBM("relativo", 180),
    "gbm_sin_escala_lr0.1": lambda: M.GBM("relativo", learning_rate=0.1, max_iter=300),
    "gbm_sin_escala_lr0.03": lambda: M.GBM("relativo", learning_rate=0.03, max_iter=1000),
    "gbm_sin_escala_msl100": lambda: M.GBM("relativo", min_samples_leaf=100),
}
ESCENARIOS = {
    "bebidas y snacks +40 %, carnes −30 %": {"bebidas": 1.4, "snacks": 1.4, "carnes": 0.7},
    "todas las familias +25 %": "todas:1.25",
}


def tabla(df: pd.DataFrame) -> str:
    cols = ["modelo", *map(str, df.columns)]
    filas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in df.iterrows():
        filas.append("| " + " | ".join([str(i), *(str(v) for v in r.values)]) + " |")
    return "\n".join(filas)


def main(d: Path) -> str:
    h = pd.read_csv(d / "historico_ventas.csv", parse_dates=["fecha"])
    cat = Catalogos(pd.read_csv(d / "tiendas.csv"), pd.read_csv(d / "familias.csv"),
                    pd.read_csv(d / "feriados.csv", parse_dates=["fecha"]), pd.read_csv(d / "costos.csv"))
    cod = V.codigos_desde(cat.tiendas, cat.familias, cat.feriados)
    X = V.construir(h, h, cat.tiendas, cat.feriados, cod)
    y = h["ventas"].to_numpy(float)
    vs = E.ventanas(h["fecha"].max(), T.N_VENTANAS)
    out = ["# Comparación de modelos", "", "Generado con `python scripts/comparar_modelos.py`. No editar a mano.",
           "", f"Ventanas de validación: {', '.join(map(str, vs))}.", ""]

    filas, preds = {}, {}
    for nombre, fab in {**T.ESCALERA, **EXTRA}.items():
        t0 = time.perf_counter()
        p = E.predecir_ventanas(fab, X, y, h["fecha"], vs)
        s = h.loc[p.index]
        k = C.elegir_factores(s["familia_id"], p, s["ventas"], cat.costos)
        m = E.metricas(s["ventas"], p, C.cantidad(p, s["familia_id"].map(k)), s["familia_id"], cat.costos)
        m1 = E.metricas(s["ventas"], p, C.cantidad(p, 1.0), s["familia_id"], cat.costos)
        filas[nombre] = {"wape": round(m["wape"], 4), "sesgo": round(m["sesgo"], 4), "mae": round(m["mae"], 1),
                         "costo": round(m["costo_total"]), "costo_k_1": round(m1["costo_total"]),
                         "pred_max": round(float(p.max())), "segundos": round(time.perf_counter() - t0)}
        preds[nombre] = p
    res = pd.DataFrame(filas).T
    res["vs_baseline"] = (res["costo"] / res.loc["baseline", "costo"] - 1).round(3)
    out += ["## 1. Escalera (validación temporal)", "",
            "`costo` usa el factor por familia elegido en validación; `costo_k_1` sugiere exactamente "
            "la venta esperada.", "", tabla(res), ""]

    out += ["## 2. Cambio de demanda sin reentrenar", "",
            "Sesgo = venta esperada total / venta real total − 1 por familia, del 2026-01-18 al 2026-02-28.", ""]
    for titulo, cambios in ESCENARIOS.items():
        if cambios == "todas:1.25":
            cambios = {f: 1.25 for f in cat.familias["familia_id"]}
        hh = h.copy()
        m = hh["fecha"] >= "2026-01-04"
        for fam, fac in cambios.items():
            sel = m & (hh["familia_id"] == fam)
            hh.loc[sel, "ventas"] = (hh.loc[sel, "ventas"] * fac).round()
        XX = V.construir(hh, hh, cat.tiendas, cat.feriados, cod)
        yy = hh["ventas"].to_numpy(float)
        ent, ev = hh["fecha"] < "2026-01-04", hh["fecha"] >= "2026-01-18"
        sesgos = {}
        for nombre, fab in T.ESCALERA.items():
            p = fab().ajustar(XX[ent], yy[ent.to_numpy()], hh["fecha"][ent]).predecir(XX[ev])
            s = hh[ev]
            sesgos[nombre] = {f: round(float(p[(s["familia_id"] == f).to_numpy()].sum()
                                             / s.loc[s["familia_id"] == f, "ventas"].sum() - 1), 3)
                              for f in ["bebidas", "snacks", "carnes", "abarrotes"]}
        out += [f"### {titulo}", "", tabla(pd.DataFrame(sesgos).T), ""]

    p = preds[T.PRODUCCION]
    s = h.loc[p.index]
    fam = s["familia_id"]
    k = C.elegir_factores(fam, p, s["ventas"], cat.costos)
    anidado = np.full(len(p), np.nan)
    for v in vs[1:]:
        mv = ((s["fecha"] >= v.inicio) & (s["fecha"] <= v.fin)).to_numpy()
        prev = (s["fecha"] < v.inicio).to_numpy()
        kk = C.elegir_factores(fam[prev], p[prev], s["ventas"][prev], cat.costos)
        anidado[mv] = C.cantidad(p[mv], fam[mv].map(kk))
    mv = ~np.isnan(anidado)
    en_muestra = C.costo_por_fila(fam[mv], s["ventas"][mv], C.cantidad(p, fam.map(k))[mv], cat.costos).sum()
    fuera = C.costo_por_fila(fam[mv], s["ventas"][mv], anidado[mv], cat.costos).sum()
    out += ["## 3. Cantidad sugerida", "", f"Modelo de producción: `{T.PRODUCCION}`.", "",
            f"- Factores por familia: {k}.",
            f"- Ventanas 2 a 4 con el factor elegido en las ventanas anteriores (fuera de muestra): "
            f"{fuera:,.0f}; con el factor elegido usando todas las ventanas: {en_muestra:,.0f} "
            f"({fuera / en_muestra - 1:+.1%}).", ""]
    return "\n".join(out)


if __name__ == "__main__":
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "datos" / "publicados"
    destino = RAIZ / "docs" / "comparacion_modelos.md"
    destino.write_text(main(carpeta), encoding="utf-8")
    print(f"escrito {destino}")
