# Evidencia de Airflow

Exportado con `python scripts/exportar_evidencia.py` desde http://localhost:8080.

## Ejecuciones del DAG `reentrenamiento`

| dag_run_id | estado | inicio | duración | tareas |
|---|---|---|---|---|
| reentrenamiento-f4fea03b11d2 | success | 2026-11-15T00:03:51 | 48 s | entrenar_retador=success (46 s), decidir=success (1 s) |
| reentrenamiento-38391ef795d4 | success | 2026-11-15T00:05:10 | 47 s | entrenar_retador=success (44 s), decidir=success (1 s) |
| reentrenamiento-8dcd4b6dfefc | success | 2026-11-15T00:06:44 | 51 s | entrenar_retador=success (48 s), decidir=success (1 s) |
| reentrenamiento-268d47a4ad28 | success | 2026-11-15T00:07:56 | 48 s | entrenar_retador=success (45 s), decidir=success (1 s) |
| reentrenamiento-65e8b6252b6e | success | 2026-11-15T00:08:47 | 44 s | entrenar_retador=success (42 s), decidir=success (1 s) |
| reentrenamiento-5e2221743311 | failed | 2026-11-15T00:09:32 | 52 s | entrenar_retador=failed (50 s), decidir=upstream_failed (0 s) |
