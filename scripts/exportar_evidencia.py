"""Exporta la evidencia de MLflow y de Airflow del producto en ejecución (entregable del enunciado):
experimentos y versiones del modelo, y ejecuciones del DAG de reentrenamiento.

Uso:
    python scripts/exportar_evidencia.py [--mlflow http://localhost:5000] [--airflow http://localhost:8080]
Escribe evidencia/mlflow.md y evidencia/airflow.md. Usuario y clave de Airflow: AIRFLOW_ADMIN_* del .env.
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

import httpx
import mlflow
from mlflow.tracking import MlflowClient

RAIZ = Path(__file__).resolve().parents[1]
MODELO = "novamercado-ventas"


def leer_env() -> dict:
    ruta = RAIZ / ".env"
    if not ruta.is_file():
        return {}
    return dict(linea.split("=", 1) for linea in ruta.read_text().splitlines() if "=" in linea and not linea.startswith("#"))


def mlflow_md(uri: str) -> str:
    mlflow.set_tracking_uri(uri)
    c = MlflowClient()
    exp = c.get_experiment_by_name(MODELO)
    out = ["# Evidencia de MLflow", "", f"Exportado con `python scripts/exportar_evidencia.py` desde {uri}.", "",
           f"## Experimento `{MODELO}`", ""]
    tandas = c.search_runs([exp.experiment_id], "tags.tipo = 'tanda'", order_by=["attributes.start_time ASC"])
    out += ["| tanda (run padre) | origen | fecha de corte | filas | observaciones | atípicas excluidas | "
            "promos imputadas | costo validación (producción) |", "|---|---|---|---|---|---|---|---|"]
    for r in tandas:
        p, m, t = r.data.params, r.data.metrics, r.data.tags
        out.append(f"| {r.info.run_name} (`{r.info.run_id[:8]}`) | {t.get('origen')} | {p.get('datos_fecha_max')} | "
                   f"{p.get('datos_filas')} | {p.get('datos_filas_observacion')} | {p.get('datos_filas_atipicas_excluidas', '—')} | "
                   f"{p.get('datos_promociones_imputadas', '—')} | {m.get('costo_validacion_produccion', 0):,.0f} |")
    if tandas:
        ultima = tandas[-1]
        hijos = c.search_runs([exp.experiment_id], f"tags.mlflow.parentRunId = '{ultima.info.run_id}'")
        out += ["", f"### Escalera de la última tanda ({ultima.info.run_name})", "",
                "| modelo | WAPE | sesgo | costo | producción |", "|---|---|---|---|---|"]
        for h in sorted(hijos, key=lambda h: h.data.metrics.get("costo_total_validacion", 0), reverse=True):
            mm = h.data.metrics
            out.append(f"| {h.info.run_name} | {mm.get('wape_validacion', 0):.4f} | {mm.get('sesgo_validacion', 0):+.4f} | "
                       f"{mm.get('costo_total_validacion', 0):,.0f} | {h.data.tags.get('produccion')} |")
    reg = c.get_registered_model(MODELO)
    out += ["", f"## Model Registry: `{MODELO}`", "", f"Aliases: {dict(reg.aliases)}", "",
            "| versión | origen | decisión | fue champion | fecha de corte | costo validación | motivo |",
            "|---|---|---|---|---|---|---|"]
    for v in sorted(c.search_model_versions(f"name='{MODELO}'"), key=lambda v: int(v.version)):
        t = v.tags
        out.append(f"| {v.version} | {t.get('origen')} | {t.get('decision', '—')} | {t.get('fue_champion', '—')} | "
                   f"{t.get('fecha_corte')} | {t.get('costo_validacion')} | {t.get('motivo', '—')} |")
    return "\n".join(out) + "\n"


def airflow_md(url: str, usuario: str, clave: str) -> str:
    tok = httpx.post(f"{url}/auth/token", json={"username": usuario, "password": clave}, timeout=10).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    corridas = httpx.get(f"{url}/api/v2/dags/reentrenamiento/dagRuns", headers=h,
                         params={"limit": 100, "order_by": "start_date"}, timeout=10).json()["dag_runs"]
    out = ["# Evidencia de Airflow", "", f"Exportado con `python scripts/exportar_evidencia.py` desde {url}.", "",
           "## Ejecuciones del DAG `reentrenamiento`", "",
           "| dag_run_id | estado | inicio | duración | tareas |", "|---|---|---|---|---|"]
    for r in corridas:
        tis = httpx.get(f"{url}/api/v2/dags/reentrenamiento/dagRuns/{r['dag_run_id']}/taskInstances", headers=h,
                        timeout=10).json().get("task_instances", [])
        tareas = ", ".join(f"{t['task_id']}={t['state']} ({(t.get('duration') or 0):.0f} s)" for t in tis)
        ini, fin = r.get("start_date"), r.get("end_date")
        dur = (datetime.fromisoformat(fin) - datetime.fromisoformat(ini)).total_seconds() if ini and fin else None
        out.append(f"| {r['dag_run_id']} | {r['state']} | {ini[:19] if ini else '—'} | "
                   f"{f'{dur:.0f} s' if dur is not None else '—'} | {tareas} |")
    return "\n".join(out) + "\n"


def main():
    env = leer_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlflow", default=f"http://localhost:{env.get('MLFLOW_PUERTO_HOST', '5000')}")
    ap.add_argument("--airflow", default=f"http://localhost:{env.get('AIRFLOW_PUERTO_HOST', '8080')}")
    a = ap.parse_args()
    (RAIZ / "evidencia" / "mlflow.md").write_text(mlflow_md(a.mlflow))
    (RAIZ / "evidencia" / "airflow.md").write_text(airflow_md(
        a.airflow, os.environ.get("AIRFLOW_ADMIN_USUARIO", env.get("AIRFLOW_ADMIN_USUARIO", "admin")),
        os.environ.get("AIRFLOW_ADMIN_CLAVE", env.get("AIRFLOW_ADMIN_CLAVE", "admin"))))
    print("escrito evidencia/mlflow.md y evidencia/airflow.md")


if __name__ == "__main__":
    main()
