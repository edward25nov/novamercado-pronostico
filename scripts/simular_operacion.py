"""Simulador de la operación diaria, como el programa de evaluación del enunciado (F7).

Cada día del periodo simulado (posterior al histórico):
  1. las tiendas reportan las ventas reales del día anterior (POST /v1/observaciones);
  2. cada tienda pide el pronóstico del día (POST /v1/prediccion); una fracción llega con problemas
     generados al azar (no solo los del catálogo);
  3. cada `--cada` días se pide un reentrenamiento (POST /admin/reentrenar) y se espera su resultado.
Eventos: un cambio de demanda desde `--cambio-desde`, una caída de MLflow y un reinicio completo del
producto (`docker compose down` + `up`, sin borrar volúmenes).

Las ventas "reales" del periodo no existen: se generan con el mismo día de la semana del año anterior
(364 días antes) × crecimiento × cambio de demanda × ruido. El informe compara el costo de las
cantidades sugeridas contra una regla ingenua (sugerir lo vendido el mismo día de la semana anterior).

Uso (con el producto recién levantado desde cero):
    python scripts/simular_operacion.py --desde 2026-03-01 --dias 56
Escribe evidencia/simulacion.md y evidencia/simulacion.json.
"""

import argparse
import json
import random
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CAMPOS_CONTRATO = {"tienda_id", "fecha", "version_modelo", "predicciones", "calidad"}


# --- datos "reales" del periodo simulado

def ventas_reales(h: pd.DataFrame, dia: date, crecimiento: float, cambio: dict[str, float], rng) -> pd.DataFrame:
    base = h[h["fecha"] == pd.Timestamp(dia) - pd.Timedelta(days=364)].copy()
    factor = base["familia_id"].map(cambio).fillna(1.0)
    base["ventas"] = rng.poisson(np.maximum(base["ventas"] * crecimiento * factor, 0)).astype(int)
    base["fecha"] = pd.Timestamp(dia)
    return base


# --- solicitudes con problemas (genéricos)

def corromper(cuerpo: dict, rng: random.Random) -> tuple[dict | bytes, str]:
    c = json.loads(json.dumps(cuerpo))
    tipo = rng.choice(["tienda_texto", "fecha_formato", "familia_forma", "promo_texto", "faltan_familias",
                       "familia_repetida", "campo_renombrado", "campo_extra", "tienda_inexistente",
                       "fecha_imposible", "cuerpo_roto", "promo_invalida", "familia_desconocida"])
    fams = c["familias"]
    if tipo == "tienda_texto":
        c["tienda_id"] = rng.choice([f"T{c['tienda_id']:02d}", str(c["tienda_id"]), f"tienda-{c['tienda_id']}"])
    elif tipo == "fecha_formato":
        f = date.fromisoformat(c["fecha"])
        c["fecha"] = rng.choice([f"{f.day:02d}/{f.month:02d}/{f.year}", f"{c['fecha']}T00:00:00", f.strftime("%Y%m%d")])
    elif tipo == "familia_forma":
        i = rng.randrange(len(fams))
        fams[i]["familia_id"] = rng.choice([fams[i]["familia_id"].upper(), fams[i]["familia_id"].replace("_", " ").title(),
                                            f" {fams[i]['familia_id']} "])
    elif tipo == "promo_texto":
        i = rng.randrange(len(fams))
        fams[i]["en_promocion"] = rng.choice([str(fams[i]["en_promocion"]), float(fams[i]["en_promocion"])])
    elif tipo == "faltan_familias":
        rng.shuffle(fams)
        c["familias"] = fams[: rng.randint(6, 11)]
    elif tipo == "familia_repetida":
        fams.append({"familia_id": fams[0]["familia_id"], "en_promocion": fams[0]["en_promocion"] + rng.randint(1, 4)})
    elif tipo == "campo_renombrado":
        c[rng.choice(["tienda", "store_id", "id_tienda"])] = c.pop("tienda_id")
    elif tipo == "campo_extra":
        c["sistema"] = "pos-v3"
    elif tipo == "tienda_inexistente":
        c["tienda_id"] = rng.choice([99, 0, "T42"])
    elif tipo == "fecha_imposible":
        c["fecha"] = rng.choice(["2026-02-30", "mañana", ""])
    elif tipo == "cuerpo_roto":
        return b'{"tienda_id": 5, "fecha": ', tipo
    elif tipo == "promo_invalida":
        fams[rng.randrange(len(fams))]["en_promocion"] = rng.choice([-2, "muchas", None, 2.5])
    elif tipo == "familia_desconocida":
        fams.append({"familia_id": "ferreteria", "en_promocion": 0})
    return c, tipo


def valida_contrato(d: dict) -> list[str]:
    errores = []
    if not CAMPOS_CONTRATO <= set(d):
        errores.append(f"faltan campos {CAMPOS_CONTRATO - set(d)}")
    if not isinstance(d.get("version_modelo"), str):
        errores.append("version_modelo no es texto")
    cal = d.get("calidad", {})
    if cal.get("estado") not in ("ok", "corregido", "advertencia"):
        errores.append("calidad.estado inválido")
    obs = cal.get("observaciones", [])
    if cal.get("estado") == "ok" and obs:
        errores.append("ok con observaciones")
    if cal.get("estado") == "corregido" and any(o["accion"] != "reparar" for o in obs):
        errores.append("corregido con advertir")
    if cal.get("estado") == "advertencia" and not any(o["accion"] == "advertir" for o in obs):
        errores.append("advertencia sin advertir")
    for p in d.get("predicciones", []):
        if not (isinstance(p.get("cantidad_sugerida"), int) and p["cantidad_sugerida"] >= 0):
            errores.append("cantidad_sugerida inválida")
    return errores


# --- eventos de operación

PROYECTO: list[str] = []  # ["-p", nombre] y/o ["-f", archivo] para actuar sobre otro stack


def compose(*args) -> None:
    subprocess.run(["docker", "compose", *PROYECTO, *args], cwd=RAIZ, check=True, capture_output=True)


def esperar(cliente: httpx.Client, condicion, limite_s: float, pausa: float = 1.0) -> float | None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite_s:
        try:
            if condicion(cliente.get("/health")):
                return time.monotonic() - t0
        except httpx.HTTPError:
            pass
        time.sleep(pausa)
    return None


def reentrenar(cliente: httpx.Client, limite_s: float = 660) -> dict:
    t0 = time.monotonic()
    r = cliente.post("/admin/reentrenar")
    if r.status_code != 202:
        return {"estado": f"no iniciado ({r.status_code})", "segundos": 0}
    rid = r.json()["id"]
    while time.monotonic() - t0 < limite_s:
        d = cliente.get(f"/admin/reentrenar/{rid}").json()
        if d.get("estado") in ("exitoso", "fallido"):
            return {"id": rid, **d, "segundos": round(time.monotonic() - t0)}
        time.sleep(5)
    return {"id": rid, "estado": "no terminó a tiempo", "segundos": round(time.monotonic() - t0)}


# --- simulación

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--datos", default=str(RAIZ / "datos" / "publicados"))
    ap.add_argument("--desde", default="2026-03-01")
    ap.add_argument("--dias", type=int, default=56)
    ap.add_argument("--cada", type=int, default=14, help="días entre reentrenamientos")
    ap.add_argument("--crecimiento", type=float, default=1.10)
    ap.add_argument("--cambio-desde", default="2026-03-29", help="desde cuándo cambia la demanda")
    ap.add_argument("--cambio", default="bebidas=1.35,snacks=1.35,carnes=0.75,abarrotes=1.15")
    ap.add_argument("--defectuosas", type=float, default=0.3, help="fracción de solicitudes con problemas")
    ap.add_argument("--caida-mlflow-dia", type=int, default=20)
    ap.add_argument("--reinicio-dia", type=int, default=35)
    ap.add_argument("--sin-eventos", action="store_true", help="no detener MLflow ni reiniciar el producto")
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--proyecto", help="proyecto de Compose sobre el que actúan los eventos (por defecto, el del .yml)")
    ap.add_argument("--compose-file", action="append", default=[],
                    help="archivo de Compose; se puede repetir (base y override), como `docker compose -f`")
    a = ap.parse_args()
    PROYECTO.extend((["-p", a.proyecto] if a.proyecto else []) + [x for f in a.compose_file for x in ("-f", f)])

    rng, nrng = random.Random(a.semilla), np.random.default_rng(a.semilla)
    h = pd.read_csv(Path(a.datos) / "historico_ventas.csv", parse_dates=["fecha"])
    costos = pd.read_csv(Path(a.datos) / "costos.csv").set_index("familia_id")
    cambio = {k: float(v) for k, v in (x.split("=") for x in a.cambio.split(","))}
    c = httpx.Client(base_url=a.url, timeout=60)
    assert esperar(c, lambda r: r.status_code == 200, 600) is not None, "el producto no está listo"

    reales: dict[date, pd.DataFrame] = {}
    filas, eventos, reentrenos, errores_contrato = [], [], [], []
    codigos: dict[str, int] = {}
    tipos: dict[str, dict[str, int]] = {}
    inicio = date.fromisoformat(a.desde)
    t_total = time.monotonic()
    for n in range(a.dias):
        dia = inicio + timedelta(days=n)
        cambio_hoy = cambio if dia >= date.fromisoformat(a.cambio_desde) else {}
        reales[dia] = ventas_reales(h, dia, a.crecimiento, cambio_hoy, nrng)
        h = pd.concat([h, reales[dia].assign(ventas=reales[dia]["ventas"])], ignore_index=True)

        if not a.sin_eventos and n == a.caida_mlflow_dia:
            compose("stop", "mlflow")
            t = esperar(c, lambda r: r.json().get("estado") == "degradado", 90)
            eventos.append({"dia": str(dia), "evento": "MLflow detenido", "segundos_hasta_degradado": t})
        if not a.sin_eventos and n == a.caida_mlflow_dia + 3:
            compose("start", "mlflow")
            t = esperar(c, lambda r: r.json().get("estado") == "ok", 180)
            eventos.append({"dia": str(dia), "evento": "MLflow de vuelta", "segundos_hasta_ok": t})
        if not a.sin_eventos and n == a.reinicio_dia:
            t0 = time.monotonic()
            compose("down")
            compose("up", "-d")
            t = esperar(c, lambda r: r.status_code == 200 and r.json().get("estado") == "ok", 600, 2)
            eventos.append({"dia": str(dia), "evento": "down + up (volúmenes conservados)",
                            "segundos_hasta_ok": round(time.monotonic() - t0) if t is not None else None})

        # 1. observaciones del día anterior
        ayer = dia - timedelta(days=1)
        if ayer in reales:
            for t, g in reales[ayer].groupby("tienda_id"):
                cuerpo = {"tienda_id": int(t), "fecha": str(ayer),
                          "ventas": [{"familia_id": r.familia_id, "ventas": int(r.ventas)} for r in g.itertuples()]}
                r = c.post("/v1/observaciones", json=cuerpo)
                codigos[f"obs {r.status_code}"] = codigos.get(f"obs {r.status_code}", 0) + 1

        # 2. solicitudes de pronóstico
        for t, g in reales[dia].groupby("tienda_id"):
            cuerpo = {"tienda_id": int(t), "fecha": str(dia),
                      "familias": [{"familia_id": r.familia_id, "en_promocion": int(r.en_promocion)}
                                   for r in g.itertuples()]}
            tipo = "valida"
            if rng.random() < a.defectuosas:
                cuerpo, tipo = corromper(cuerpo, rng)
            envio = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
            r = c.post("/v1/prediccion", content=envio, headers={"content-type": "application/json"})
            codigos[f"pred {r.status_code}"] = codigos.get(f"pred {r.status_code}", 0) + 1
            tipos.setdefault(tipo, {})
            clave = str(r.status_code) if r.status_code != 200 else r.json()["calidad"]["estado"]
            tipos[tipo][clave] = tipos[tipo].get(clave, 0) + 1
            if r.status_code != 200:
                continue
            d = r.json()
            if e := valida_contrato(d):
                errores_contrato.append({"dia": str(dia), "tienda": int(t), "errores": e})
            real = g.set_index("familia_id")["ventas"]
            semana = h[(h["fecha"] == pd.Timestamp(dia) - pd.Timedelta(days=7)) & (h["tienda_id"] == t)]
            ingenuo = semana.set_index("familia_id")["ventas"]
            for p in d["predicciones"]:
                f = p["familia_id"]
                if f not in real:
                    continue
                cf, cs = costos.loc[f, "costo_faltante"], costos.loc[f, "costo_sobrante"]

                def costo(q, rv=real[f], cf=cf, cs=cs):
                    return cf * max(rv - q, 0) + cs * max(q - rv, 0)

                filas.append({"fecha": str(dia), "tienda_id": int(t), "familia_id": f, "real": int(real[f]),
                              "venta_esperada": p["venta_esperada"], "sugerida": p["cantidad_sugerida"],
                              "version": d["version_modelo"], "costo": costo(p["cantidad_sugerida"]),
                              "costo_ingenuo": costo(float(ingenuo.get(f, real[f])))})

        # 3. reentrenamiento periódico
        if (n + 1) % a.cada == 0:
            reentrenos.append({"dia": str(dia), **reentrenar(c)})
            print(f"{dia}: reentrenamiento {reentrenos[-1]}", flush=True)
        if n % 7 == 0:
            print(f"{dia}: {sum(codigos.values())} solicitudes", flush=True)

    df = pd.DataFrame(filas)
    df["semana"] = pd.to_datetime(df["fecha"]).dt.to_period("W").astype(str)
    por_semana = df.groupby("semana").agg(costo=("costo", "sum"), costo_ingenuo=("costo_ingenuo", "sum"),
                                          wape=("real", "size"), versiones=("version", lambda s: ",".join(sorted(set(s)))))
    err = df.assign(e=(df["venta_esperada"] - df["real"]).abs()).groupby("semana").agg(e=("e", "sum"), r=("real", "sum"))
    por_semana["wape"] = (err["e"] / err["r"]).round(3)
    por_semana["vs_ingenuo"] = (por_semana["costo"] / por_semana["costo_ingenuo"] - 1).round(3)
    resumen = {"periodo": f"{inicio}..{inicio + timedelta(days=a.dias - 1)}", "minutos": round((time.monotonic() - t_total) / 60, 1),
               "codigos": codigos, "respuestas_5xx": sum(v for k, v in codigos.items() if k.split()[1].startswith("5")),
               "errores_de_contrato": len(errores_contrato), "costo_total": round(df["costo"].sum()),
               "costo_ingenuo": round(df["costo_ingenuo"].sum()), "cambio_de_demanda": {"desde": a.cambio_desde, **cambio},
               "eventos": eventos, "reentrenamientos": reentrenos, "por_tipo_de_solicitud": tipos}
    (RAIZ / "evidencia" / "simulacion.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=str))
    md = ["# Simulación de la operación", "", f"Generado con `python scripts/simular_operacion.py` "
          f"(periodo {resumen['periodo']}, {resumen['minutos']} min).", "",
          f"- Respuestas: {codigos}; **5xx: {resumen['respuestas_5xx']}**; errores de contrato en respuestas 200: "
          f"**{len(errores_contrato)}**.",
          f"- Costo de las cantidades sugeridas: **{resumen['costo_total']:,}** contra {resumen['costo_ingenuo']:,} de "
          f"sugerir lo vendido el mismo día de la semana anterior ({resumen['costo_total'] / resumen['costo_ingenuo'] - 1:+.1%}).",
          f"- Cambio de demanda desde {a.cambio_desde}: {cambio}.", "", "## Por semana", "",
          "| semana | costo | costo ingenuo | vs ingenuo | WAPE | versiones |\n|---|---|---|---|---|---|\n" + "\n".join(
              f"| {s} | {r.costo:,.0f} | {r.costo_ingenuo:,.0f} | {r.vs_ingenuo:+.1%} | {r.wape} | {r.versiones} |"
              for s, r in por_semana.iterrows()), "", "## Reentrenamientos", ""]
    md += [f"- {r['dia']}: {r.get('estado')} en {r.get('segundos')} s — promovido: {r.get('promovido')}, versión "
           f"{r.get('version')}. {r.get('motivo', '')}" for r in reentrenos]
    md += ["", "## Eventos", ""] + ([f"- {e}" for e in eventos] or ["- (sin eventos)"])
    md += ["", "## Solicitudes por tipo de problema (código o estado de calidad)", "",
           "| tipo | resultado |", "|---|---|"] + [f"| {t} | {v} |" for t, v in sorted(tipos.items())]
    if errores_contrato:
        md += ["", "## Errores de contrato", ""] + [f"- {e}" for e in errores_contrato[:20]]
    (RAIZ / "evidencia" / "simulacion.md").write_text("\n".join(md) + "\n")
    print(json.dumps({k: resumen[k] for k in ("codigos", "respuestas_5xx", "errores_de_contrato", "costo_total",
                                              "costo_ingenuo")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
