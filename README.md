# novamercado-pronostico

Servicio de pronóstico diario de ventas por familia de producto para las tiendas de NovaMercado
(Laboratorio 2, Product Development). Integra FastAPI, PostgreSQL, MLflow y Apache Airflow, y se
levanta con un solo comando.

> Estado: en construcción por fases. Las instrucciones de arranque se completan en la fase F1.

## Requisitos
- Docker Desktop (o Docker Engine) con Compose v2.
- Para desarrollo local: Python 3.13.

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
