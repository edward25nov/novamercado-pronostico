# novamercado-pronostico

Servicio de pronóstico diario de ventas por familia de producto para las tiendas de NovaMercado
(Laboratorio 2, Product Development). Integra FastAPI, PostgreSQL, MLflow y Apache Airflow, y se
levanta con un solo comando.

> Estado: en construcción por fases (F1: contenedores listos; el modelo llega en F3).

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
.venv/bin/pytest -q
.venv/bin/python scripts/perfilar_datos.py   # regenera docs/perfil_datos.md
```

## Documentación
- `DECISIONES.md`: decisiones técnicas y de producto, con alternativas y justificación.
- `docs/perfil_datos.md`: perfil de los datos publicados.
- `CLAUDE.md`: contexto para el agente de programación.
