# novamercado-pronostico

Servicio de ML en producción (Laboratorio 2, Product Development). Cada mañana cada tienda de
NovaMercado pide el pronóstico de ventas del día por familia de producto; al día siguiente reporta
las ventas reales. El servicio responde aunque los datos lleguen en mal estado, registra todo y se
reentrena solo. Enunciado: `../Laboratorio_2_PD_26_c.pdf` (fuera del repo). Contrato: Anexo del
enunciado, resumido abajo.

## Contrato del servicio (no renombrar ni omitir campos; se pueden agregar)
- Puerto 8000. Fechas `AAAA-MM-DD`. Rechazo = 422 con `detail` que explica el motivo.
- `POST /v1/prediccion` `{tienda_id, fecha, familias:[{familia_id, en_promocion}]}` → 200
  `{tienda_id, fecha, version_modelo (texto), predicciones:[{familia_id, venta_esperada,
  cantidad_sugerida (entero ≥ 0)}], calidad:{estado, observaciones:[{campo, accion, detalle}]}}`.
- `calidad.estado`: `ok` (sin observaciones), `corregido` (solo `reparar`), `advertencia` (hay algún
  `advertir`). `accion` ∈ {`reparar`, `advertir`}. `campo` usa la ruta del dato recibido, p. ej.
  `familias[2].familia_id`.
- `POST /v1/observaciones` `{tienda_id, fecha, ventas:[{familia_id, ventas}]}` → 200
  `{registros_guardados, calidad}`; `registros_guardados` cuenta filas nuevas o modificadas
  (reenvío idéntico = 0).
- `POST /admin/reentrenar` (sin cuerpo) → 202 `{id}` o 503. `GET /admin/reentrenar/{id}` →
  `{estado: en_curso|exitoso|fallido, promovido, version, motivo}` (los tres últimos al terminar;
  `version` = vigente al terminar); id desconocido → 404.
- `GET /modelo` → `{nombre, alias, version}` (texto). `GET /health` → 200 `{estado: ok}` o
  `{estado: degradado, motivo}`; 503 mientras no haya modelo cargado.

## Reglas que no se rompen
- **Nunca usar el reloj del sistema** (`date.today()`, `datetime.now()`) para validar fechas ni para
  decidir qué datos usar. Las fechas son simuladas. El reloj solo puede usarse para marcar cuándo se
  recibió una solicitud (auditoría).
- Al pronosticar la fecha *d* solo se usan ventas de fechas < *d*.
- La limpieza y la política de calidad viven en `src/novamercado/calidad/` como funciones puras con
  pruebas; los endpoints solo orquestan. Ninguna solicitud responde 500 por datos de entrada.
- La política de cada tipo de problema está en `DECISIONES.md` (D7, D8): código y tabla cambian
  juntos.
- `datos/publicados/` es la fuente: solo se lee (montada `:ro` en los contenedores) y no va a Git.
  Las credenciales van en `.env` (no se versiona); `.env.example` sí.
- El modelo vigente es el alias `champion` del Model Registry; solo lo mueve el criterio de
  reemplazo, nunca a mano. Un reentrenamiento fallido o no aprobado no toca el alias.
- Las pruebas (`pytest`) no necesitan MLflow, Airflow ni Docker en ejecución.
- Versiones fijas en `requirements.txt` e imágenes; las mismas dependencias en API, inicializador
  y Airflow.

## Reglas del modelo
- El modelo de producción es `entrenamiento.PRODUCCION` (D13); la escalera completa se evalúa en cada
  tanda con las mismas ventanas (D22). Ventas, factores y codificación viajan juntos en el
  `Pronosticador` (D24).
- Nombre registrado y experimento: `novamercado-ventas`; alias `champion` (vigente) y `anterior`.
- Serializar con `pickle` estándar, nunca joblib (D24).

## Comandos
- `python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
- `.venv/bin/pytest -q` · `.venv/bin/ruff check .`
- `.venv/bin/python scripts/perfilar_datos.py` → regenera `docs/perfil_datos.md`.
- `PYTHONPATH=src .venv/bin/python scripts/comparar_modelos.py` → regenera `docs/comparacion_modelos.md`
  (escalera, robustez ante cambios de demanda y cantidad sugerida; ~3 min, sin MLflow).
- Pruebas de base: Postgres desechable en 55432 y `NOVAMERCADO_TEST_DB_URL` (ver README).

## Estructura
- `src/novamercado/`: paquete del producto.
  - `datos/`: `esquema.sql`, `carga.py` (archivos publicados, idempotente), `lectura.py` (ventas y catálogos).
  - `modelo/`: `calendario.py`, `variables.py` (misma función para entrenar y predecir), `modelos.py`
    (baseline y GBM), `costos.py` (métrica de negocio y factores), `evaluacion.py` (ventanas),
    `pronosticador.py` (artefacto registrado), `entrenamiento.py` (escalera, MLflow, alias).
  - `servicio/`: API FastAPI. `inicializador.py`: esquema, carga y primer modelo.
- `dags/`: DAGs de Airflow 3; solo orquestan funciones de `src/novamercado/`.
- `docker/`: Dockerfiles. `docker-compose.yml` en la raíz (proyecto `novamercado`).
- `tests/`: pruebas con pytest (corren en cada PR con GitHub Actions).
- `scripts/`: utilidades (perfil de datos, simulador de operación).
- `docs/`: perfil de datos y documentación de apoyo. `evidencia/`: capturas y respuestas de ejemplo.
- `datos/publicados/`: archivos del GES (no versionados).

## Forma de trabajo
- Una rama y un PR por fase; commits cortos en Conventional Commits en español, sin
  `Co-Authored-By`.
- Toda decisión nueva va a `DECISIONES.md` (numerada, con alternativas y justificación con números)
  en el mismo PR que la implementa.
- La entrega es el tag `entrega-lab2`; no moverlo ni borrarlo una vez creado.
