"""DAG de reentrenamiento (D15). Se dispara desde POST /admin/reentrenar (sin programación).

entrenar_retador -> decidir. Solo orquesta: la lógica vive en `novamercado.reentrenamiento`.
Si una tarea falla, el callback deja la ejecución como `fallido` y el modelo vigente no cambia
(el alias solo se mueve en `decidir`, al final). Una sola ejecución a la vez.
"""

from datetime import datetime, timedelta

from airflow.sdk import dag, task


def _al_fallar(context):
    from novamercado import reentrenamiento

    ti = context.get("task_instance")
    excepcion = context.get("exception")
    motivo = f"{getattr(ti, 'task_id', None) or context.get('reason') or 'ejecución'}: " \
             f"{type(excepcion).__name__ if excepcion else 'falló o superó el tiempo máximo'}"
    if excepcion:
        motivo += f" ({str(excepcion)[:300]})"
    reentrenamiento.registrar_fallo(context["dag_run"].run_id, motivo)


@dag(
    dag_id="reentrenamiento",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=10),  # requisito: cada reentrenamiento en menos de 10 minutos
    default_args={"retries": 0, "execution_timeout": timedelta(minutes=9), "on_failure_callback": _al_fallar},
    on_failure_callback=_al_fallar,  # también si vence dagrun_timeout (no hay tarea que falle)
    tags=["novamercado"],
    doc_md=__doc__,
)
def reentrenamiento():
    @task
    def entrenar_retador(**contexto) -> dict:
        from novamercado import reentrenamiento as r

        return r.entrenar_retador(contexto["dag_run"].run_id)

    @task
    def decidir(info: dict, **contexto) -> dict:
        from novamercado import reentrenamiento as r

        return r.decidir(contexto["dag_run"].run_id, info)

    decidir(entrenar_retador())


reentrenamiento()
