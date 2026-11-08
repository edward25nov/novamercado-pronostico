# Decisiones técnicas y de producto

Cada decisión tiene su contexto, las alternativas consideradas y la justificación. Los números
salen de `docs/perfil_datos.md` (generado con `scripts/perfilar_datos.py`) o de mediciones que se
citan en cada decisión.

**Estado:** *vigente* = implementada y verificada; *propuesta* = acordada, se implementa en la fase
indicada y se actualiza con números medidos en ese mismo PR.

## Índice

- **Producto e infraestructura**
  - D1. Un solo `docker-compose.yml` con nombre de proyecto fijo — *vigente*
  - D2. Los archivos publicados van en `datos/publicados/`, fuera de Git y en solo lectura — *vigente*
  - D3. Versiones fijas y las mismas dependencias en la API, el inicializador y Airflow — *vigente*
  - D4. Puerto de MLflow en el anfitrión configurable, 5000 por defecto — *vigente*
  - D5. Un inicializador idempotente prepara el producto desde cero — *vigente*
  - D18. La API solo depende de la base de datos para arrancar — *vigente*
  - D19. La API habla con Airflow por su API REST v2 con el usuario de `.env` — *vigente (F1), se usa en F6*
- **Persistencia**
  - D6. Una sola tabla de ventas para el histórico y las observaciones — *vigente (esquema F2; endpoint en F5)*
  - D20. Qué se registra de la operación — *vigente (esquema F2)*
  - D21. Pruebas de base de datos contra un Postgres real, cada una en un esquema propio — *vigente*
- **Calidad de los datos de entrada**
  - D7. Política por principios: reparar, advertir o rechazar — *vigente*
  - D8. Taxonomía de problemas y su política — *vigente*
  - D9. Familias faltantes: se pronostican con advertencia y la última promoción conocida — *vigente*
  - D10. Familia repetida con valores distintos: se elige el valor según el costo de la familia — *vigente*
  - D11. Números con separadores: tres dígitos son miles, uno o dos son decimales — *vigente*
  - D12. Fechas: nunca el reloj del sistema; rango válido según los datos — *vigente*
- **Modelo**
  - D13. Información que usa el modelo al predecir — *vigente*
  - D14. Cantidad sugerida: newsvendor por familia, calibrada por costo — *vigente*
  - D15. Criterio de reemplazo del modelo vigente — *propuesta (F6)*
  - D22. Validación temporal común y escalera de modelos — *vigente*
  - D23. Guardas numéricas del modelo — *vigente*
  - D24. Qué se registra en MLflow y cómo se empaqueta el modelo — *vigente*
- **Operación**
  - D16. Reentrenamiento pedido con otro en curso: 202 con el id del que está en curso — *propuesta (F6)*
  - D17. Recarga del modelo en caliente, caché local y monitor de salud — *vigente*
  - D25. La API lee el cuerpo crudo y nunca responde 500 por datos de entrada — *vigente*

## Producto e infraestructura

### D1. Un solo `docker-compose.yml` con nombre de proyecto fijo
- **Decisión:** todo el producto (API, Postgres del producto, MLflow, Airflow y su Postgres) se
  declara en `docker-compose.yml` en la raíz, con `name: novamercado`. El servicio de MLflow se
  llama `mlflow`.
- **Alternativas:** un compose para MLflow y la API y otro para Airflow, como en la sesión 5.
- **Justificación:** el enunciado pide levantar todo con un solo `docker compose up`. El nombre
  fijo evita que los volúmenes y redes choquen con otros proyectos en la misma máquina (en el Lab 1
  el volumen de Postgres de Airflow chocó con el de la clase 4 por compartir el nombre de proyecto).
- **Servicios:** `db` y `airflow-db` (dos Postgres 16.15 separados, como pide el enunciado),
  `mlflow` (backend SQLite y artefactos en el volumen `mlflow-datos`), `api`, y Airflow 3.3.2 con
  LocalExecutor: `airflow-init` (migra la base y crea el usuario), `airflow-apiserver`,
  `airflow-scheduler` y `airflow-dag-processor`. No hay `triggerer`: ninguna tarea es diferible, y
  es un contenedor menos que levantar.
- **Volúmenes con nombre** para todo lo que debe sobrevivir (`producto-db`, `mlflow-datos`,
  `api-cache`, `airflow-db`, `airflow-logs`). Los logs de Airflow van en un volumen y no en una
  carpeta del repositorio para no depender del UID del anfitrión en Linux; por eso Airflow corre
  con el UID fijo de la imagen oficial (`50000:0`) y no es configurable: cambiarlo dejaría el volumen
  de logs sin permisos de escritura. Los DAGs, `src/` y `datos/publicados/` se montan en solo
  lectura (solo necesitan permiso de lectura, que es el normal de un clon).
- **URL de la base:** `config.py` la arma desde `PRODUCTO_DB_*` codificando usuario y clave, así una
  clave con `@`, `:` o `/` no rompe la conexión (hay prueba).
- **MLflow sobre SQLite (riesgo conocido):** SQLite admite un solo escritor; si el inicializador y
  un DAG registraran a la vez podría aparecer "database is locked". Se mitiga porque el inicializador
  solo entrena cuando no existe `@champion` y el DAG tiene `max_active_runs=1`. Alternativa
  registrada: una base `mlflow` en el Postgres del producto (exige agregar `psycopg2` a la imagen de
  MLflow). Se vuelve a medir en F6 con escrituras concurrentes.
- **Credenciales** solo en `.env`; el compose usa `${VAR:?definir en .env}`, así que sin `.env`
  falla de inmediato con un mensaje que dice qué falta, en vez de arrancar con claves vacías.
- **Medido (F1, Mac M-series, imágenes ya construidas):** desde cero, todos los servicios quedan
  sanos en unos 35 s; tras `down` + `up` en 23 s, conservando una tabla de prueba en `db` y un
  experimento en MLflow. Una tarea disparada por la API REST de Airflow corre y ve el paquete,
  los datos montados y las mismas versiones de scikit-learn (1.9.1) y MLflow (3.17.2).

### D2. Los archivos publicados van en `datos/publicados/`, fuera de Git y en solo lectura
- **Decisión:** el contenido del archivo del GES (`tiendas.csv`, `familias.csv`,
  `historico_ventas.csv`, `feriados.csv`, `costos.csv`, `catalogo_errores.md`, `ejemplos/`) se
  coloca tal cual en `datos/publicados/`. `.gitignore` excluye todo excepto `.gitkeep`. Los
  contenedores lo montan en solo lectura.
- **Alternativas:** ruta configurable por variable de entorno; copiar los datos dentro de la imagen.
- **Justificación:** el enunciado prohíbe datos en el repositorio y en las imágenes. Una carpeta fija
  dentro del clon hace que las instrucciones del README sean una sola línea y que el evaluador no
  tenga que configurar nada. El montaje de solo lectura garantiza que el producto nunca altere la
  fuente.

### D3. Versiones fijas y las mismas dependencias en la API, el inicializador y Airflow
- **Decisión:** `requirements.txt` fija todas las versiones y se instala igual en las tres imágenes,
  sobre Python 3.13 (el de `apache/airflow:3.3.2`). Las imágenes base también llevan versión fija.
- **Alternativas:** dependencias distintas por imagen; rangos de versiones.
- **Justificación:** el modelo se serializa en un contenedor (inicializador o Airflow) y se carga en
  otro (API); con otra versión de scikit-learn puede no cargar o predecir distinto (sesión 5).
- **Detalle:** `apache/airflow:3.3.2` ya trae pandas 3.0.5, numpy 2.5.3, scikit-learn 1.9.1,
  fastapi 0.136.3, pydantic 2.13.5, uvicorn 0.52.4, httpx 0.28.1 y psycopg 3.3.5 (revisado con
  `pip list` dentro de la imagen). `requirements.txt` usa exactamente esas versiones, de modo que
  instalarlo en la imagen de Airflow solo agrega lo que falta (MLflow, skops) sin cambiar nada de
  Airflow. Las imágenes base son `python:3.13.15-slim` (la misma versión menor de Python que Airflow),
  `postgres:16.15`, `ghcr.io/mlflow/mlflow:v3.17.2` y `apache/airflow:3.3.2`.

### D4. Puerto de MLflow en el anfitrión configurable, 5000 por defecto
- **Decisión:** `MLFLOW_PUERTO_HOST` en `.env` (5000 en `.env.example`). Dentro de la red de Docker
  siempre es `http://mlflow:5000`.
- **Alternativas:** fijar 5000; fijar 5001.
- **Justificación:** 5000 es lo que espera el curso, pero en macOS lo ocupa el Receptor AirPlay; en
  la máquina de desarrollo se usa 5001. Ningún servicio del producto depende del puerto del
  anfitrión, solo las personas que abren la interfaz.

### D5. Un inicializador idempotente prepara el producto desde cero
- **Decisión:** un servicio `inicializador` de una sola ejecución aplica el esquema, carga los
  archivos publicados si su huella no está registrada y, si no existe `@champion`, entrena y registra
  la primera versión con la misma función que usa el DAG. Al volver a levantar el producto no repite
  nada.
- **Alternativas:** que el primer modelo lo entrene una corrida del DAG disparada al arrancar; que lo
  entrene la API.
- **Justificación:** no depende de que Airflow esté listo (es el servicio que más tarda en arrancar,
  y el producto debe estar en `ok` en menos de 10 minutos). La API se mantiene liviana y solo sirve.
- **Carga (F2):** cada archivo se valida antes de cargar el primero (si falta uno o cambian sus
  columnas, no se carga nada y el inicializador termina con error explicando qué falta). Cada archivo
  se carga con `COPY` a una tabla temporal y un `INSERT … ON CONFLICT DO UPDATE … WHERE IS DISTINCT
  FROM`, en una transacción junto con su huella SHA-256 en `cargas`. Misma huella = no se lee. Un
  archivo modificado actualiza solo las filas que cambian y nunca duplica; un cambio en el histórico
  no pisa una venta que ya llegó como observación. Un `pg_advisory_lock` impide que dos
  inicializadores carguen a la vez.
- **Medido (F2, datos publicados):** desde cero el inicializador carga 10 tiendas, 12 familias,
  12 costos, 61 feriados y 83 052 ventas en 0,5 s (la suma de ventas en la base, 17 565 431, es igual
  a la del CSV) y termina 13 s después del `up`. En el segundo arranque responde "sin cambios" para los
  cinco archivos en 0,0 s. Con dos inicializadores lanzados a la vez sobre una base vacía, uno cargó
  las 83 052 filas y el otro esperó el candado y encontró "sin cambios"; quedaron 83 052 filas.
- **Contenido inválido:** si un archivo trae valores que la base rechaza (p. ej. una venta
  negativa), el inicializador registra una sola línea, `historico_ventas.csv: contenido inválido
  (<motivo de Postgres>)`, y termina con código 1. La transacción de ese archivo se revierte; los
  archivos anteriores quedan cargados y, como la huella del fallido no se registró, se reintenta en el
  próximo arranque. Verificado con una venta `-5` en la primera fila del histórico publicado:
  quedaron los cuatro catálogos y 0 ventas.
- **Filas que desaparecen de un archivo republicado no se borran:** el upsert solo inserta o
  actualiza. *Alternativa:* borrar lo que ya no está en el archivo. *Justificación:* las ventas son
  hechos; que una fila falte en una nueva publicación es más probable que sea un archivo incompleto
  que una venta que no ocurrió, y borrarla cambiaría en silencio los datos de entrenamiento y las
  variables de predicción. Las filas actualizadas marcan `actualizado_en`.
- **Primer modelo (F3):** tras la carga, garantiza que exista `@champion`. **MLflow es la fuente de
  verdad**; la marca en `estado_producto` solo evita depender de él cuando no responde:
  - champion existe → nada que hacer;
  - no hay champion pero sí una versión con `origen=inicializador` (el proceso murió entre registrar y
    promover) → se promueve esa versión, sin reentrenar ni dejar versiones huérfanas;
  - no hay ninguna versión (primer arranque, o se perdió el volumen de MLflow aunque la base siga) →
    se entrena la escalera, se registra y se promueve;
  - MLflow no responde → con marca, termina bien (hubo modelo y la API usa su caché, D17) tras 4
    intentos; sin marca, espera hasta 3 minutos y si no, falla.
- **Medido (F3):** desde cero, el inicializador termina 47 s después del `up` (carga 0,5 s;
  escalera y registro 38 s) con `novamercado-ventas` v1 en `@champion` (costo en validación 369 741,
  WAPE 0.1797, los mismos números que fuera de Docker). Segundo arranque: "modelo inicial ya
  registrado (versión 1)" en 0,0 s. Sigue habiendo una sola versión en el Registry. Casos de falla
  (revisión del PR #4): sin alias y con la v1 registrada, la promueve en 2 s sin reentrenar; con el
  volumen de MLflow borrado y la base intacta, reentrena y promueve en 40 s; con MLflow detenido,
  termina bien en 11 s informando que el modelo ya se había registrado.
- **No bloquea a la API:** la API no depende del inicializador (D18); si este fallara, la API
  arranca igual y responde 503 `sin_modelo` en `/health` (el motivo todavía no dice por qué no hay
  modelo; en F3/F5 el motivo indicará si falló la inicialización o si el primer modelo está en
  entrenamiento).

### D18. La API solo depende de la base de datos para arrancar
- **Decisión:** en el compose, `api` espera solo a que `db` esté sana (`depends_on` con
  `service_healthy`); no espera a MLflow ni a Airflow. El healthcheck del contenedor considera viva
  a la API si responde HTTP, aunque `/health` devuelva 503 por no tener modelo.
- **Alternativas:** esperar a que MLflow esté sano, como en la sesión 5.
- **Justificación:** el evaluador interrumpe MLflow y reinicia el producto; si la API dependiera de
  MLflow, un reinicio con MLflow caído la dejaría sin arrancar. La API debe seguir respondiendo
  (con el modelo en caché, D17) y `/health` es el que informa la dependencia caída.
- **Vida contra salud:** el HEALTHCHECK del contenedor consulta `/vivo`, que no toca dependencias;
  `/health` revisa db, MLflow y Airflow **en paralelo** con timeout de 3 s cada una.
- **Medido (revisión del PR #2):** con las tres dependencias en `docker compose pause`, `/health`
  tardaba 9,05 s con las revisiones en serie y el contenedor quedaba `unhealthy` (el healthcheck
  usaba `/health` con timeout de 4 s). Tras el cambio tarda 3,1 s (tres mediciones: 3,09–3,11 s) y el
  contenedor siguió `healthy` durante 40 s con las dependencias pausadas. Hay una prueba con
  dependencias lentas que exige que las revisiones corran en paralelo. Desde F5 las revisiones las hace
  el monitor en segundo plano (D17) y `/health` responde al instante con el último resultado.

### D19. La API habla con Airflow por su API REST v2 con el usuario de `.env`
- **Decisión:** `airflow-init` crea el usuario administrador de `.env` (gestor de autenticación FAB,
  el mismo de las sesiones 3 y 4). La API obtiene un token con `POST /auth/token` y dispara corridas
  con `POST /api/v2/dags/{dag_id}/dagRuns` y `{"logical_date": null}`; el `dag_run_id` es el `id`
  que devuelve `/admin/reentrenar`. Los DAGs quedan activos al crearse
  (`DAGS_ARE_PAUSED_AT_CREATION=false`).
- **Alternativas:** `airflow dags trigger` por línea de comandos dentro del contenedor (exige montar
  el socket de Docker en la API); un DAG programado que revise una tabla de solicitudes (agrega la
  latencia del intervalo).
- **Justificación:** es la interfaz oficial y no requiere privilegios extra. Verificado en F1: una
  corrida disparada así pasó de `queued` a `success` en segundos, y el DAG nuevo apareció en unos
  20 s (`DAG_PROCESSOR__REFRESH_INTERVAL=30`).

## Persistencia

### D6. Una sola tabla de ventas para el histórico y las observaciones
- **Decisión:** las ventas del histórico y las que llegan por `POST /v1/observaciones` viven en la
  misma tabla, con clave `(tienda_id, fecha, familia_id)` y una columna de origen. Una observación
  solo cuenta en `registros_guardados` si la fila es nueva o cambia su valor; el valor anterior queda
  en un historial.
- **Alternativas:** tablas separadas para histórico y observaciones.
- **Justificación:** los ejemplos usan una fecha del histórico (2025-11-17, tienda 5) y sus 12 valores
  son idénticos al histórico: con tablas separadas, enviar un dato que el producto ya conoce
  contaría como 12 registros nuevos. Con una sola tabla la idempotencia es contra todo lo conocido,
  y el entrenamiento y las variables de predicción leen una única fuente.

### D20. Qué se registra de la operación
- **Decisión:** el esquema (`src/novamercado/datos/esquema.sql`) registra:
  - `solicitudes`: cada solicitud recibida **incluidas las rechazadas**, con el cuerpo tal como llegó
    (texto, aunque no sea JSON válido), su forma normalizada, el código HTTP, el estado de calidad y
    el motivo del rechazo.
  - `correcciones`: cada observación de calidad (`campo`, `accion`, `detalle`) de una solicitud.
  - `predicciones`: cada valor entregado con el `en_promocion` usado y la `version_modelo`.
  - `ventas` y `ventas_historial`: lo conocido (D6) y los valores que una observación corrigió.
  - `reentrenamientos`: estado, resultado y métricas de cada ejecución (id = `dag_run_id`).
  - `cargas`: archivos publicados cargados y su huella.
- **Alternativas:** guardar solo las solicitudes aceptadas; un log en archivos.
- **Justificación:** el enunciado pide registrar solicitudes, predicciones, correcciones y
  observaciones. Guardar el cuerpo crudo de los rechazos permite auditar la política (D7) y
  reproducir un caso nuevo como prueba. `en_promocion` de cada predicción es el dato que el
  reentrenamiento necesita para las fechas sin histórico (las observaciones no lo traen). El reloj
  del sistema solo aparece en columnas de auditoría (`recibido_en`, `cargado_en`), nunca en reglas.
- **Pendiente para F6:** las ventas atípicas se guardan (no se inventa ni se descarta un dato real),
  pero la observación queda con la regla `ventas_atipicas` en `correcciones`; el reentrenamiento
  debe excluirlas o recortarlas para que un error de captura (p. ej. 99 999) no deforme el modelo.
  Además, las observaciones de días sin solicitud de pronóstico quedan con `en_promocion` NULL en
  `lectura.SQL_VENTAS`: el reentrenamiento debe imputarlas con la última promoción conocida (D9) o
  excluirlas.

### D21. Pruebas de base de datos contra un Postgres real, cada una en un esquema propio
- **Decisión:** las pruebas de carga e idempotencia corren contra Postgres 16.15 (en GitHub Actions
  como servicio del job; en local, un contenedor desechable en el puerto 55432). Cada prueba crea un
  esquema `prueba_<id>` y lo borra al terminar. Usan archivos pequeños de `tests/datos_prueba/` con
  el mismo formato que los publicados, porque los publicados no están en el repositorio. Sin
  `NOVAMERCADO_TEST_DB_URL` se omiten (`pytest -rs` lo muestra). Las 12 pruebas con los ejemplos
  publicados (`tests/test_calidad_ejemplos.py`) también se omiten en la CI, porque necesitan
  `datos/publicados/`; corren en local y en la verificación con un clon limpio.
- **Alternativas:** SQLite en memoria; simular la base con objetos falsos.
- **Justificación:** la idempotencia depende de `ON CONFLICT … WHERE IS DISTINCT FROM`, `COPY` y
  candados de Postgres, que SQLite no tiene o hace distinto; probarlos con otra base no prueba nada.
  El enunciado solo excluye depender de MLflow en ejecución.

## Calidad de los datos de entrada

### D7. Política por principios: reparar, advertir o rechazar
- **Decisión:** cada problema se clasifica por lo que implica responder, no por su forma:
  - **reparar:** la transformación es única y determinista y no pierde información (formato,
    mayúsculas, tildes, espacios, tipos, nombres alternativos de campos, codificación, duplicados
    idénticos).
  - **advertir:** se responde, pero con un supuesto o dejando fuera una parte (coincidencia
    aproximada, ambigüedad resuelta por convención, valor faltante o inválido imputado, ítem
    excluido, datos recientes faltantes).
  - **rechazar (422):** no se puede establecer la tienda o la fecha, o no queda nada válido que
    responder.
- Regla general para lo que no está en el catálogo: un campo que no se puede normalizar toma la
  política de su clase. Si es de identidad (tienda, fecha) se rechaza; si es de un ítem (familia,
  promoción, ventas) el ítem se imputa o se excluye con advertencia. Una excepción inesperada en la
  limpieza se responde como rechazo con `detail`, nunca como 500.
- **Alternativas:** reglas caso por caso según el catálogo; rechazar todo lo que no cumple el
  contrato (como en la sesión 5).
- **Justificación:** el enunciado advierte que llegarán problemas que no están en el catálogo; una
  regla por clase cubre casos nuevos de forma consistente. Rechazar todo detendría a las tiendas, y
  reparar todo inventaría datos: la política separa lo que se puede corregir sin supuestos de lo que
  no.

### D8. Taxonomía de problemas y su política
Implementada en `src/novamercado/calidad/` (funciones puras; `regla` es el nombre interno que queda
registrado en `correcciones`). Esta tabla y el código cambian en el mismo PR.

**Identidad (si no se puede establecer, se rechaza)**

| Clase (`regla`) | Política | Ejemplos |
|---|---|---|
| Tienda con otro formato (`tienda_formato`) | reparar si apunta a una sola tienda: número en texto o decimal entero, prefijo + número (`T`, `tienda`, `store`, `suc`, `id`, `#`…), nombre exacto con o sin "NovaMercado" | E01 `"T05"`, `"5"`; `5.0`, `"tienda-5"`, `"NovaMercado Quetzaltenango"`. El nombre se prueba antes que el número: `"NovaMercado Zona 10"` es la tienda 1, no la 10 |
| Tienda aproximada (`tienda_aproximada`) | advertir si es la única tienda de una ciudad o el único nombre parecido | `"Cobán"` → 8 |
| Tienda inexistente o ambigua (`tienda_desconocida`, `tienda_ambigua`) | rechazar | `99`, `5.5`, `true`, `"Guatemala"` (tres tiendas) |
| Fecha con otro formato sin ambigüedad (`fecha_formato`) | reparar | E04 `"2025-11-17T00:00:00"`, `"17/11/2025"`; `"2025/11/17"`, `"20251117"`, `"17 de noviembre de 2025"`, `"Nov 17, 2025"`, `"11/17/2025"` (17 no puede ser mes) |
| Fecha ambigua (`fecha_ambigua`) | advertir: día/mes (convención de Guatemala), o año de dos dígitos como 20AA | `"03/04/2026"` → 3 de abril; `"17/11/25"` |
| Falta tienda o fecha, fecha imposible o fuera de rango (`falta_identidad`, `fecha_invalida`, `fecha_fuera_de_rango`) | rechazar (D12) | `"2025-02-30"`, `"mañana"`, `20251117` (número), tienda 10 antes del 2025-03-15, más de un año después del último dato |
| Fecha posterior al calendario de feriados (`fecha_sin_calendario`) | advertir: se asume un día sin eventos (D12) | `"2027-01-05"` |
| El mismo dato en campos sinónimos (`campo_repetido`, `campo_en_conflicto`) | se interpreta cada uno por separado y se comparan los valores **interpretados**: si coinciden, reparar; si difieren, rechazar si es tienda o fecha, o advertir y no usar ninguno si es de un ítem | `"tienda_id": 5` y `"tienda": "T05"` → reparar; `"tienda": "NovaMercado Cobán"` (8) → rechazar; `"familia_id": "lacteos"` y `"familia": "LÁCTEOS"` → reparar |
| Cuerpo que no es JSON u objeto (`cuerpo_invalido`) | rechazar | vacío, texto plano, comillas simples, `[]`, `42` |

**Ítems de la predicción**

| Clase (`regla`) | Política | Ejemplos |
|---|---|---|
| Familia escrita de otra forma (`familia_formato`) | reparar si la forma normalizada (sin tildes, minúsculas, separadores como `_`, mojibake corregido, invisibles quitados) coincide con un id o un nombre | E02 `"LÁCTEOS"`, `"lacteos "`, `"Frutas y Verduras"`; `"LÃ¡cteos"`, `"Snacks y dulces"` |
| Familia parecida (`familia_aproximada`) | advertir si hay un único candidato con similitud ≥ 0.8 y claramente mejor que el segundo | `"lacteo"`, `"panaderias"` |
| Familia desconocida o elemento inválido (`familia_desconocida`, `item_invalido`) | advertir y excluirla (luego se completa como faltante) | `"ferreteria"`, `42` en la lista |
| Número como texto o decimal entero (`numero_formato`) | reparar | E03 `"3"`, `2.0`, `"3,0"` |
| Promoción no entera, negativa, faltante o no numérica (`promocion_imputada`) | advertir e imputar con la última promoción registrada, o 0 (D9) | `2.5`, `-1`, `null`, `"sí"`, ausente |
| Promoción mayor al máximo histórico de la familia (`promocion_atipica`) | advertir y **conservar el valor**: el modelo lo trata como el máximo, pero el dato real queda registrado para el reentrenamiento | `500`, `"1,000"` |
| Faltan familias (`faltan_familias`) | advertir y pronosticarlas (D9); si no viene la lista, se pronostican todas | E05 |
| Familia repetida (`familia_repetida`) | reparar si el valor es el mismo; advertir y elegir según el costo (D10) si difiere | E06 |

**Ítems de las observaciones**

| Clase (`regla`) | Política | Ejemplos |
|---|---|---|
| Separador de miles o coma decimal (`numero_formato`) | reparar (D11) | E10 `"1,292"`, `"50,0"`; `"1.234,00"`, `"1 292"` |
| Ventas negativas (`ventas_negativas`) | advertir y no guardar ese valor | E08 `-4` (devoluciones) |
| Ventas no enteras, faltantes o no numéricas (`ventas_invalidas`) | advertir y no guardar | `"812,5"`, `12.5`, `null`, `true` |
| Ventas atípicas (`ventas_atipicas`) | guardar y advertir (más de 3 veces el máximo histórico de la familia) | `50000` |
| Familia repetida (`familia_repetida`) | reparar si es el mismo valor; advertir y no guardar si difiere | — |
| Envío repetido | sin observaciones: idempotente, `registros_guardados = 0` (D6) | E09 |
| Ninguna venta válida (`sin_datos_validos`) | rechazar | todas negativas |

**Generales**

| Clase (`regla`) | Política | Ejemplos |
|---|---|---|
| Nombre de campo distinto (`campo_renombrado`) | reparar si es un alias conocido o su forma normalizada coincide; advertir si solo es parecido | E07 `"tienda"`; `"tiendaId"`, `"Tienda_ID"`, `"store_id"`, `"promo"`, `"familia"` |
| Campo desconocido (`campo_desconocido`) | advertir que se ignoró | `"origen": "pos"` |
| Formas alternativas (`forma`, `codificacion`) | reparar: lista con una sola solicitud, `{familia: valor}` en vez de lista, cuerpo en Latin-1 | — |

- **Cambios por la revisión del PR #5:** (1) los campos sinónimos se comparaban por su valor crudo,
  así que `{"tienda_id": 5, "tienda": "5"}` se rechazaba y `{"familia_id": "lacteos", "familia":
  "LÁCTEOS"}` descartaba el ítem; ahora se comparan los valores interpretados. (2) La promoción
  atípica se acotaba al máximo histórico: no cambiaba la predicción (el GBM predice lo mismo para 19 y
  para 500, 27,8537, porque no extrapola) pero sí el `en_promocion` registrado, que el
  reentrenamiento usa para las fechas nuevas; ahora se conserva.
- **Sinónimo ilegible junto a uno válido:** `{"tienda_id": 5, "tienda": "xyz"}` o una fecha válida
  con `"date": "mañana"` se rechazan. Se mantiene a propósito: dos campos de identidad que no
  coinciden (aunque uno sea ilegible) no permiten saber con certeza cuál es el bueno, y equivocarse de
  tienda o de fecha es peor que pedir que se reenvíe (D7).
- **Verificación:** 134 pruebas de calidad: los 10 ejemplos del catálogo y los 2 válidos publicados
  (cuando los archivos están), unos 100 casos fuera del catálogo y fuzzing con hypothesis (JSON y
  bytes arbitrarios y mutaciones de solicitudes válidas: 400 casos por prueba en la CI; una corrida
  de 5 000 por prueba, 25 000 en total, no encontró ninguna excepción fuera de `Rechazo`). La
  salida de la limpieza se valida con modelos estrictos de Pydantic (`calidad/esquemas.py`).
- **Catálogo de prueba:** las pruebas usan un catálogo armado a mano (`tests/catalogo_prueba.py`,
  con los ids de familia y una ciudad con tres tiendas) porque los archivos publicados no están en
  el repositorio; `tests/test_calidad_ejemplos.py` corre además sobre los publicados si existen.

### D9. Familias faltantes: se pronostican con advertencia y la última promoción conocida
- **Decisión:** si la solicitud omite familias que la tienda vende (E05), se pronostican igual, con
  una observación `advertir` por cada una. Su `en_promocion` es la última promoción conocida de esa
  tienda y familia **hasta la fecha pedida**: la de la solicitud más reciente para una fecha anterior
  o igual, o la del histórico si es más reciente; si no hay ninguna, 0. La misma imputación aplica a
  una promoción faltante o inválida. Nunca se usa una solicitud para una fecha posterior (una tienda
  puede pedir fechas en desorden).
- **Alternativas:** responder solo las familias recibidas; asumir siempre 0.
- **Justificación:** el catálogo lo describe como un problema ("faltan familias que la tienda
  vende"), así que la tienda necesita esos pronósticos. La promoción es muy persistente: correlación
  0.83 con la del día anterior y 61 % de los días igual; asumir 0 subestima las ventas (con 0 productos
  en promoción la venta es 0.93 de su nivel, con 10 a 20 es 1.17). El supuesto queda escrito en
  `detalle`.

### D10. Familia repetida con valores distintos: se elige el valor según el costo de la familia
- **Decisión:** si una familia aparece con promociones distintas (E06), se responde con advertencia
  usando el valor mayor cuando τ = c_faltante / (c_faltante + c_sobrante) ≥ 0.5 y el menor cuando
  τ < 0.5.
- **Alternativas:** el primero o el último valor; rechazar la familia o la solicitud.
- **Justificación:** más promoción implica más venta esperada. Ante la duda, conviene equivocarse
  hacia el lado barato: en 8 de las 12 familias faltar cuesta más que sobrar (abarrotes τ = 0.83,
  licores 0.95) y se toma el mayor; en lácteos, carnes, panadería y frutas y verduras (τ entre 0.29 y
  0.45) se toma el menor. Tomar "el primero" o "el último" no tiene ningún respaldo.

### D11. Números con separadores: tres dígitos son miles, uno o dos son decimales
- **Decisión:** un separador (`.` o `,`) seguido de exactamente 3 dígitos es de miles; seguido de 1 o
  2, es decimal. Con los dos tipos de separador, el último es el decimal (`"1.234,50"`). Varios
  separadores iguales solo pueden ser de miles (`"2,000,000"`). Si el resultado no es entero (las
  ventas son unidades), se advierte y no se guarda.
- **Ejemplos:** `"1,292"` → 1292, `"50,0"` → 50, `"812,0"` → 812, `"1.234,00"` → 1234; `"812,5"` y
  `"1.234,56"` no se guardan.
- **Alternativas:** asumir siempre la convención guatemalteca (punto decimal); "gana la lectura que
  da un entero" (la versión propuesta en F0).
- **Justificación:** el catálogo (E10) muestra ambas convenciones en el mismo envío, así que no hay
  una única convención. La regla "la lectura entera" deja ambiguo `"1,000"` (1000 por miles, 1 por
  decimales): la regla de los tres dígitos lo resuelve sin supuestos, porque nadie escribe unidades
  con tres decimales.

### D12. Fechas: nunca el reloj del sistema; rango válido según los datos
- **Decisión:** ninguna regla usa la fecha de hoy. Una solicitud de pronóstico es válida desde 28
  días después del primer día del histórico (2024-03-29, la ventana de nivel) y nunca antes de la
  apertura de la tienda; una observación, desde el primer día del histórico (y la apertura). El
  límite superior es un año después del último dato conocido (o el fin de `feriados.csv` si es
  posterior): más allá, la fecha se considera absurda y se rechaza. Entre el fin de `feriados.csv`
  (2026-12-31) y ese límite se responde con advertencia: "se asumió un día sin feriados ni fechas
  especiales". El último dato conocido se actualiza con cada observación (no queda fijo en el
  histórico). Si faltan las ventas del día anterior de alguna familia, la respuesta advierte cuál es
  la última fecha con dato y el pronóstico se hace con ella (`datos_recientes_faltantes`); una
  familia sin ventas en los 70 días anteriores usa el nivel de respaldo (D23) y también se advierte. Si faltan observaciones
  recientes para la fecha pedida, se responde con advertencia indicando la última fecha con datos
  (lo agrega el servicio en F5, porque necesita la base).
- **Alternativas:** aceptar cualquier fecha; rechazar todo lo posterior a `feriados.csv` (la versión
  de F0; si la evaluación cruzara a 2027, todas las solicitudes responderían 422).
- **Justificación:** el servicio opera sobre fechas simuladas (enunciado). Sin calendario, un
  pronóstico de Navidad o del 31 de diciembre se equivocaría por un factor de 3 a 5
  (`docs/perfil_datos.md`: índice 0.32 en Navidad, 1.69 el 31 de diciembre); el periodo de evaluación
  está cubierto por `feriados.csv`.

## Modelo

### D13. Información que usa el modelo al predecir
- **Decisión:** para la fila (tienda, familia, *d*) el modelo usa (`src/novamercado/modelo/variables.py`):
  - **Ventas pasadas** (solo fechas < *d*, sobre una grilla diaria completa por serie): rezagos de 1, 2,
    7, 14, 21 y 28 días; medias de 7 y 28 días; media del mismo día de la semana en 4 semanas;
    desviación de 28 días; días desde el último dato; promoción del día anterior.
  - **La solicitud:** `en_promocion` del día.
  - **Catálogos:** tienda, familia y tipo de tienda (categóricas).
  - **Calendario** (se conoce de antemano): día de la semana, del mes y del año, mes, días al fin de
    mes, quincena (días 15 y último del mes), marcas por tipo de evento de `feriados.csv` (feriado,
    medio día, comercial, pago; los locales solo para las tiendas cuya ciudad coincide con el
    `ambito`), el evento por nombre (categórica) y la distancia en días al evento más cercano (±7).
- **Modelo de producción:** `HistGradientBoostingRegressor` global (pérdida Poisson, lr 0.05, 600
  árboles, 31 hojas) que predice **ventas / nivel**, donde el nivel es la media de 28 días de la
  serie, y con los rezagos y medias **también divididos entre el nivel** (modelo "sin escala").
- **Alternativas** (`docs/comparacion_modelos.md`, mismas 4 ventanas de 28 días):

  | Modelo | WAPE | Costo | Sesgo con +25 % de demanda sin reentrenar |
  |---|---|---|---|
  | baseline (mismo día, 4 semanas) | 0.267 | 543 415 | −2 a −4 % |
  | GBM directo (ventas en unidades) | 0.180 | 371 454 | −9 a −16 % |
  | GBM relativo con variables absolutas | 0.177 | 367 090 | −6 a −8 % |
  | **GBM relativo sin escala** | 0.180 | 369 741 | **−2 a −2,5 %** |

- **Justificación:** los tres GBM bajan el costo ~32 % frente al baseline. Entre ellos, el relativo
  con variables absolutas es 0,7 % más barato con la demanda estable, pero los árboles no
  extrapolan: si el nivel sube, las variables en unidades salen del rango visto y el pronóstico se
  queda atrás (−6 a −8 %; el directo, −9 a −16 %). El enunciado anuncia cambios de demanda en el
  periodo de evaluación y el reentrenamiento depende de cuándo lo pida el evaluador; el modelo sin
  escala aprende patrones relativos y sigue al nivel en cuanto llegan las observaciones (−2 a −2,5 %
  en el mismo escenario; con +40 %/−30 % en tres familias, ±3–4 % contra ±6–9 %). Se paga 0,7 % en
  estabilidad por robustez. Variantes descartadas: pesos por recencia (vida media 180 días, +0,6 %
  de costo), lr 0.03 con 1 000 árboles (−0,3 %, el doble de tiempo), hojas mínimas de 100 (+0,1 %).
- **Huecos en las observaciones** (medido en la revisión del PR #4, entrenado hasta 2026-01-31 y
  prediciendo febrero): si falta la venta de ayer, el sin escala pasa de WAPE 0.1740 a 0.1766 (sesgo
  −0,5 % → −1,2 %); con tres días faltantes, 0.1872. El directo pasa de 0.1715 a 0.1815. El modelo
  elegido tolera que una tienda no reporte algún día.
- **Por qué la quincena aparte:** `feriados.csv` solo marca 6 fechas de pago (Bono 14 y aguinaldo),
  pero las ventas suben el 15 (índice 1.17) y a fin de mes (1.36 el día 31).

### D14. Cantidad sugerida: newsvendor por familia, calibrada por costo
- **Decisión:** `cantidad_sugerida = ceil(venta_esperada × k_f)`, con un factor por familia k_f
  elegido entre 0.50 y 2.50 (paso 0.01) minimizando el costo de `costos.csv` sobre las predicciones
  fuera de muestra de las 4 ventanas. Los factores viajan dentro del modelo registrado (cambiar de
  champion cambia predicción y factores juntos).
- **Resultado (v1):** licores 1.53, limpieza 1.31, cuidado personal 1.30, bebé 1.30, mascotas 1.23,
  bebidas 1.20, abarrotes 1.18, snacks 1.15, lácteos 0.94, carnes 0.93, frutas y verduras 0.90,
  panadería 0.86: el orden sigue al cuantil crítico τ (0.95 en licores, 0.29 en panadería).
- **Alternativas:** sugerir la venta esperada (k = 1); un factor por familia y tipo de tienda;
  modelos de cuantiles por familia.
- **Justificación:** con k = 1 el costo sería 481 068 contra 369 741 (−23 %). Por familia y tipo de
  tienda mejora solo 0,2 % y triplica los parámetros. Elegir k con las mismas ventanas en que se
  mide introduce un sesgo optimista pequeño: elegido solo con ventanas anteriores y aplicado a la
  siguiente, el costo sube 0,8 % (280 719 contra 278 559), así que la cifra de validación es
  representativa. Un modelo de cuantiles por familia exigiría 12 modelos más por reentrenamiento.

### D22. Validación temporal común y escalera de modelos
- **Decisión:** cuatro ventanas consecutivas de 28 días que terminan en la última fecha con ventas
  (v1: del 2025-11-09 al 2026-02-28, incluye diciembre). Para cada ventana se entrena con las filas
  anteriores a su inicio y se predice cada día con las ventas reales hasta el día anterior, como en
  producción. Los cuatro modelos de la escalera (baseline, GBM directo, GBM relativo absoluto, GBM
  sin escala) usan las mismas filas y quedan como runs anidados de una tanda en MLflow, con
  métricas totales y por ventana, costo por familia y factores. El de producción es fijo (D13); los
  otros son la referencia de cada reentrenamiento.
- **Alternativas:** una sola ventana final; división aleatoria; elegir en cada tanda el de menor
  costo.
- **Justificación:** una sola ventana deja fuera diciembre (el mes con más variación: Navidad 0.32,
  31 de diciembre 1.69); la división aleatoria filtra el futuro. Elegir el de menor costo en cada
  tanda favorecería al relativo absoluto, que gana por 0,7 % en datos estables pero se queda atrás
  ante un cambio de nivel, justo el riesgo que anuncia el enunciado.

### D23. Guardas numéricas del modelo
- **Columnas constantes (F5):** el GBM entrena solo con las columnas que tienen más de un valor y
  recuerda la lista para predecir. scikit-learn 1.9.1 falla al discretizar una columna constante
  (p. ej. si en el periodo de entrenamiento no hay ninguna fecha comercial), cosa que se descubrió al
  probar la API con datos sintéticos. Con los datos publicados todas varían: el costo de la v1 no
  cambió (369 741).
- **Decisión:** el modelo se entrena solo con filas cuya serie tiene nivel de 28 días (al menos 7
  días con dato), el objetivo relativo se acota en 10, la predicción relativa se acota en 1,5 veces
  el percentil 99,9 visto al entrenar y cualquier NaN o infinito se vuelve 0. Si una serie no tiene
  historia, el nivel es la venta media de su familia en las tiendas del mismo tipo en los últimos 28
  días de entrenamiento.
- **Por qué (medido):** en las primeras filas de cada serie (p. ej. la apertura de la tienda 10) el
  nivel era el mínimo de 1 y el objetivo relativo llegaba a 1 476. Con lr 0.1 la liga logarítmica
  de Poisson desbordó y produjo predicciones del orden de 10^188. Con historia, el ratio real tiene
  percentil 99,9 de 2,96 y máximo 4,7 (99 % de las filas); tras la corrección lr 0.1 da un costo
  normal (370 242).

### D24. Qué se registra en MLflow y cómo se empaqueta el modelo
- **Decisión:** experimento `novamercado-ventas`; cada entrenamiento es un run padre `tanda-<fecha de
  corte>` (linaje: filas, rango de fechas, suma y huella de las ventas usadas, filas que vienen de
  observaciones, ventanas, commit, origen) con un run anidado por modelo de la escalera. El de
  producción se registra como versión de `novamercado-ventas` (pyfunc que envuelve un
  `Pronosticador`: modelo, codificación de categorías, factores e información del entrenamiento) con
  tags de costo y WAPE de validación, fecha de corte, factores, run y tanda. El vigente es el alias
  `champion`; al reemplazarlo, el anterior queda como `anterior`.
- **Formato del artefacto:** `Pronosticador.version_formato` (también en `info` y como tag de la
  versión). Si se agregan atributos, `__setstate__` completa los faltantes con valores por defecto
  para que un champion registrado antes siga cargando y prediciendo. Lo mismo en `GBM` (formato 2,
  F5: `columnas` vacío = todas, como entrenaba F3). Verificado con un artefacto entrenado con el
  código de F3 en un worktree: carga y predice con el código nuevo (y hay prueba).
- **Serialización:** `pickle` estándar con las mismas versiones en todas las imágenes (D3); no
  joblib, porque en el Lab 1 `dill` (que importa Airflow) alteraba su pickler.
- **Alternativas:** `mlflow.sklearn` con el estimador solo (la API tendría que reconstruir aparte la
  codificación y los factores, y un cambio de alias podría mezclar versiones); skops (no serializa
  las clases propias sin una lista de tipos de confianza).

### D15. Criterio de reemplazo del modelo vigente
- **Propuesta:** el retador se entrena con datos anteriores a una ventana común de validación (los
  últimos 28 días con observaciones). El vigente se mide en la misma ventana con sus predicciones
  registradas (si cubren al menos el 80 %) o evaluando su artefacto. Se promueve si su costo es al
  menos 1 % menor y pasa las verificaciones de sanidad; el alias `champion` solo se mueve al final y
  un fallo nunca lo toca.

## Operación

### D16. Reentrenamiento pedido con otro en curso: 202 con el id del que está en curso
- **Decisión:** si llega `POST /admin/reentrenar` mientras otra ejecución está en curso, se responde
  202 con el `id` de esa ejecución; no se encola otra. 503 queda para cuando no se puede iniciar
  (Airflow no disponible).
- **Alternativas:** responder 503; encolar una ejecución nueva.
- **Justificación:** el cliente obtiene un `id` válido cuyo resultado incluye los datos que envió;
  encolar duplicaría el trabajo sobre los mismos datos y alargaría el tiempo hasta tener el resultado.

### D17. Recarga del modelo en caliente, caché local y monitor de salud
- **Decisión** (`servicio/estado.py`): un hilo en segundo plano, cada 15 s, revisa en paralelo la
  base, MLflow y Airflow (timeout de 3 s cada una) y refresca el catálogo; y cada 30 s (5 s mientras
  no hay modelo) consulta la versión de `@champion`. Si cambió, descarga esa versión, la guarda en el
  volumen `api-cache` y la reemplaza con una sola asignación (atómica: cada solicitud toma una foto del
  modelo al empezar, así nunca mezcla dos versiones). La caché se indexa por versión y `run_id`
  (`modelos/<versión>-<run_id>/`): si se perdiera el volumen de MLflow y el Registry volviera a
  numerar desde 1, una "v1" nueva no se confunde con la v1 vieja de la caché. Si MLflow no responde, se conserva el modelo
  cargado. Al arrancar, primero se carga la copia de la caché (sin red) y luego se consulta MLflow.
  `/health` solo lee este estado: responde al instante. Cada paso del monitor es independiente: una
  falla al cargar el catálogo no impide cargar el modelo (ver "Medido").
- **Alternativas:** cargar el modelo solo al arrancar y reiniciar la API al promover (sesión 5, no
  cumple "sin reinicio manual"); que el DAG avise a la API (acopla Airflow con la API y falla si la
  API está caída en ese momento); consultar MLflow en cada solicitud (latencia y dependencia).
- **Medido (F5, en Docker):**
  - Promoción de una v2 → la API la usó 5 s después, sin reiniciar (peor caso 30 s; límite 2 min).
  - MLflow detenido → `/health` pasó a `degradado` ("MLflow no disponible") a los 8 s (límite 1 min)
    y las predicciones siguieron respondiendo 200 con la versión cargada.
  - API reiniciada con MLflow detenido → arrancó con el modelo de la caché (`"origen": "cache"`) en
    1 s y predijo normalmente.
  - MLflow de vuelta → `ok` a los 16 s (límite 2 min).
  - Desde cero: `ok` 48 s después del `up`; tras `down` + `up`, 13 s (modelo desde la caché).
  - Error real encontrado: en el primer arranque la API cargaba el catálogo antes de que el
    inicializador terminara el histórico (fecha máxima `NaT`), esa excepción cortaba la revisión y el
    modelo nunca se cargaba. Ahora el catálogo espera a que haya ventas y los pasos están separados
    (hay prueba de ambos).

### D25. La API lee el cuerpo crudo y nunca responde 500 por datos de entrada
- **Decisión:** `/v1/prediccion` y `/v1/observaciones` leen el cuerpo como bytes y lo pasan a la
  limpieza (D7); FastAPI no lo valida antes, porque su 422 automático rechazaría casos reparables
  (`"tienda_id": "T05"`). Un `Rechazo` responde 422 con `detail` (texto); cualquier otra excepción de la
  limpieza también responde 422 ("no se pudo interpretar la solicitud") y queda en el log y en
  `solicitudes`. Si falla la base o no hay modelo, 503 con `detail`. Toda solicitud, aceptada o
  rechazada, se registra con su cuerpo crudo (D20).
- **Respuestas:** se validan con los modelos de Pydantic del contrato (`calidad/esquemas.py`); las
  predicciones vuelven en el orden de la solicitud y luego las familias completadas (D9).
  `GET /modelo` agrega `origen` (mlflow o cache) y `fecha_corte`; `GET /health` agrega
  `dependencias`, `version_modelo` y `origen_modelo` (el contrato permite campos adicionales).
- **Observaciones sin modelo:** `/v1/observaciones` no necesita el modelo: registra ventas aunque
  todavía no haya champion (solo necesita el catálogo).
- **Medido:** 100 solicitudes de 12 familias: mediana 79 ms, p95 265 ms (lee 70 días de ventas de la
  tienda, construye las variables y registra solicitud, correcciones y predicciones en una
  transacción). Las respuestas a los ejemplos publicados y a 8 casos fuera del catálogo están en
  `evidencia/respuestas_api.md` (`scripts/enviar_ejemplos.py`).

