# novamercado-pronostico

Servicio de pronóstico diario de ventas por familia de producto para las tiendas de NovaMercado
(Laboratorio 2, Product Development). Integra FastAPI, PostgreSQL, MLflow y Apache Airflow, y se
levanta con un solo comando.

> Estado: F7 (simulación de la operación); falta la evidencia final y el tag de entrega.

## Requisitos
- Docker Desktop (o Docker Engine) con Compose v2, con al menos 4 GB de memoria para Docker.
- Puertos libres en el anfitrión: 8000 (API), 5000 (MLflow) y 8080 (Airflow). Los dos últimos se
  cambian en `.env` (en macOS el 5000 lo ocupa AirPlay: usar `MLFLOW_PUERTO_HOST=5001`).
- Para desarrollo local: Python 3.13.

## Levantar el producto desde cero
1. Colocar los archivos publicados en `datos/publicados/` (ver abajo).
2. Crear el archivo de configuración: `cp .env.example .env`.
3. Levantar todo: `docker compose up -d` (la primera vez construye las imágenes).
4. Ver el estado: `docker compose ps` y `curl localhost:8000/health`.

| Servicio | Dirección en el anfitrión | Dentro de la red de Docker |
|---|---|---|
| API | http://localhost:8000 (documentación en `/docs`) | `api:8000` |
| MLflow | http://localhost:5000 | `mlflow:5000` |
| Airflow | http://localhost:8080 (usuario y clave de `.env`) | `airflow-apiserver:8080` |
| Postgres del producto | no se publica | `db:5432` |

Al arrancar, el servicio `inicializador` aplica el esquema de la base y carga los archivos
publicados; termina solo (`docker compose ps -a` lo muestra como `Exited (0)`). En los arranques
siguientes detecta que los archivos no cambiaron y no repite la carga
(`docker compose logs inicializador`).

El producto está listo cuando `curl localhost:8000/health` responde `{"estado": "ok", ...}`
(medido: unos 50 s desde cero con las imágenes construidas; unos 15 s al volver a levantarlo).

## Uso de la API
Documentación interactiva en http://localhost:8000/docs. Contrato completo en el Anexo del enunciado.

```
curl -s localhost:8000/health
curl -s localhost:8000/modelo
curl -s -X POST localhost:8000/v1/prediccion -H 'content-type: application/json' \
     -d @datos/publicados/ejemplos/prediccion_valida.json
curl -s -X POST localhost:8000/v1/observaciones -H 'content-type: application/json' \
     -d @datos/publicados/ejemplos/observacion_valida.json
.venv/bin/python scripts/enviar_ejemplos.py   # todos los ejemplos -> evidencia/respuestas_api.md

# Reentrenamiento (DAG "reentrenamiento" en Airflow): devuelve 202 con el id de la ejecución
curl -s -X POST localhost:8000/admin/reentrenar
curl -s localhost:8000/admin/reentrenar/<id>   # en_curso | exitoso | fallido, con promovido, version y motivo
```

El reentrenamiento compara al retador con el vigente solo en los días posteriores al corte del vigente:
tras una promoción hacen falta **al menos 7 días nuevos de observaciones** antes de que otro
reentrenamiento pueda promover (DECISIONES.md, D15).

## Simulación de la operación
Con el producto levantado desde cero, `scripts/simular_operacion.py` reproduce la evaluación (56 días
posteriores al histórico, solicitudes con problemas, reentrenamientos, cambio de demanda, caída de
MLflow y reinicio del producto) y escribe `evidencia/simulacion.md`:

```
.venv/bin/python scripts/simular_operacion.py --desde 2026-03-01 --dias 56   # ~6 minutos
```

Los eventos (detener MLflow, `down` + `up`) actúan sobre el proyecto de Compose `novamercado`. Para
simular contra otro stack, pasar `--url` y también `--proyecto` (y `--compose-file` si corresponde).

Detener sin perder datos: `docker compose down` (los volúmenes se conservan). Borrar todo, incluidos
los datos del producto, MLflow y Airflow: `docker compose down -v`.

## Dónde colocar los archivos publicados
Descomprimir el archivo publicado en el GES y colocar su contenido **tal cual** en
`datos/publicados/`:

```
datos/publicados/
├── tiendas.csv
├── familias.csv
├── historico_ventas.csv
├── feriados.csv
├── costos.csv
├── catalogo_errores.md
└── ejemplos/
```

Esa carpeta no se versiona en Git y los contenedores la leen en modo solo lectura.

## Desarrollo local
```
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
# Postgres desechable para las pruebas de base de datos (sin él, esas pruebas se omiten)
docker run -d --name novamercado-pruebas-db -p 55432:5432 -e POSTGRES_PASSWORD=pruebas postgres:16.15
export NOVAMERCADO_TEST_DB_URL=postgresql://postgres:pruebas@localhost:55432/postgres
.venv/bin/pytest -q
.venv/bin/python scripts/perfilar_datos.py   # regenera docs/perfil_datos.md
```

## Documentación
- `DECISIONES.md`: decisiones técnicas y de producto, con alternativas y justificación.
- `docs/perfil_datos.md`: perfil de los datos publicados.
- `CLAUDE.md`: contexto para el agente de programación.
