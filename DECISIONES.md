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
  - D5. Un inicializador idempotente prepara el producto desde cero — *propuesta (F2–F3)*
  - D18. La API solo depende de la base de datos para arrancar — *vigente*
  - D19. La API habla con Airflow por su API REST v2 con el usuario de `.env` — *vigente (F1), se usa en F6*
- **Persistencia**
  - D6. Una sola tabla de ventas para el histórico y las observaciones — *propuesta (F2)*
- **Calidad de los datos de entrada**
  - D7. Política por principios: reparar, advertir o rechazar — *propuesta (F4)*
  - D8. Taxonomía de problemas y su política — *propuesta (F4)*
  - D9. Familias faltantes: se pronostican con advertencia y la última promoción conocida — *propuesta (F4)*
  - D10. Familia repetida con valores distintos: se elige el valor según el costo de la familia — *propuesta (F4)*
  - D11. Números con coma: gana la interpretación que da un entero — *propuesta (F4)*
  - D12. Fechas: nunca el reloj del sistema; rango válido según los datos — *propuesta (F4)*
- **Modelo**
  - D13. Información que usa el modelo al predecir — *propuesta (F3)*
  - D14. Cantidad sugerida: newsvendor por familia, calibrada por costo — *propuesta (F3)*
  - D15. Criterio de reemplazo del modelo vigente — *propuesta (F6)*
- **Operación**
  - D16. Reentrenamiento pedido con otro en curso: 202 con el id del que está en curso — *propuesta (F6)*
  - D17. Recarga del modelo en caliente, caché local y monitor de salud — *propuesta (F5)*

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
  carpeta del repositorio para no depender del UID del anfitrión en Linux. Los DAGs, `src/` y
  `datos/publicados/` se montan en solo lectura.
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

### D18. La API solo depende de la base de datos para arrancar
- **Decisión:** en el compose, `api` espera solo a que `db` esté sana (`depends_on` con
  `service_healthy`); no espera a MLflow ni a Airflow. El healthcheck del contenedor considera viva
  a la API si responde HTTP, aunque `/health` devuelva 503 por no tener modelo.
- **Alternativas:** esperar a que MLflow esté sano, como en la sesión 5.
- **Justificación:** el evaluador interrumpe MLflow y reinicia el producto; si la API dependiera de
  MLflow, un reinicio con MLflow caído la dejaría sin arrancar. La API debe seguir respondiendo
  (con el modelo en caché, D17) y `/health` es el que informa la dependencia caída.

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
Clases generales (la primera columna) y cómo caen en ellas los ejemplos del catálogo:

| Clase | Política | Ejemplos (catálogo y otros) |
|---|---|---|
| Identificador de tienda con otro formato | reparar si apunta a una sola tienda del catálogo | E01 `"T05"`, `"5"`; `5.0`, `"tienda 5"`, nombre exacto de la tienda |
| Tienda inexistente, ambigua o fecha anterior a su apertura | rechazar | `99`, `"Guatemala"` (tres tiendas), tienda 10 antes del 2025-03-15 |
| Familia escrita de otra forma | reparar si la forma normalizada coincide con un id o un nombre | E02 `"LÁCTEOS"`, `"lacteos "`, `"Frutas y Verduras"` |
| Familia parecida pero no idéntica | advertir si hay un único candidato cercano | `"lacteo"`, `"panaderias"` |
| Familia desconocida | advertir y excluirla; rechazar si no queda ninguna | `"ferreteria"` |
| Número como texto o decimal entero | reparar | E03 `"3"`, `2.0` |
| Promoción no entera, negativa, faltante o no numérica | advertir e imputar (D9) | `2.5`, `-1`, `null`, `"sí"` |
| Fecha en otro formato sin ambigüedad | reparar | E04 `"2025-11-17T00:00:00"`, `"17/11/2025"` |
| Fecha ambigua (día y mes ≤ 12) | advertir, se interpreta como día/mes | `"03/04/2026"` |
| Fecha faltante, imposible o fuera del rango | rechazar (D12) | `"2026-02-30"` |
| Faltan familias que la tienda vende | advertir y completarlas (D9) | E05 |
| Familia repetida | reparar si los valores son iguales; advertir y elegir según D10 si difieren | E06 |
| Nombre de campo distinto | reparar si es un alias conocido o su forma normalizada coincide | E07 `"tienda"`; `"tiendaId"`, `"id_tienda"` |
| Campo desconocido | advertir que se ignoró | `"origen": "pos"` |
| Ventas negativas | advertir y no guardar ese valor | E08 `-4` (devoluciones) |
| Envío repetido | sin problema: idempotente, `registros_guardados = 0` (D6) | E09 |
| Número con separador de miles o coma decimal | reparar con la interpretación entera (D11) | E10 `"1,234"`, `"812,0"` |
| Ventas no enteras, faltantes o no numéricas | advertir y no guardar ese valor | `812.5`, `null` |
| Cuerpo que no es JSON o no es un objeto | rechazar | texto plano, lista vacía |

La implementación vive en `src/novamercado/calidad/` (funciones puras con pruebas) y esta tabla se
actualiza en el mismo PR que cambie una regla.

### D9. Familias faltantes: se pronostican con advertencia y la última promoción conocida
- **Decisión:** si la solicitud omite familias que la tienda vende (E05), se pronostican igual, con
  una observación `advertir` por cada una. Su `en_promocion` es el de la última solicitud registrada
  para esa tienda y familia; si no hay ninguna, 0. La misma imputación aplica a una promoción
  faltante o inválida.
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

### D11. Números con coma: gana la interpretación que da un entero
- **Decisión:** las ventas son unidades enteras. Si un texto con coma o punto admite dos lecturas
  (separador de miles o decimal), se repara con la que produce un entero: `"1,292"` → 1292,
  `"50,0"` → 50. Si ambas o ninguna dan un entero válido, se advierte y no se guarda.
- **Alternativas:** asumir siempre la convención guatemalteca (punto decimal); rechazar el envío.
- **Justificación:** el catálogo (E10) muestra ambas convenciones en el mismo envío, así que no hay
  una convención única; la restricción de que las ventas son enteras resuelve casi todos los casos
  sin supuestos.

### D12. Fechas: nunca el reloj del sistema; rango válido según los datos
- **Decisión:** ninguna regla usa la fecha de hoy. Una solicitud de pronóstico es válida desde el
  primer día con historia suficiente hasta el último día de `feriados.csv` (2026-12-31); fuera de ese
  rango se rechaza. Si faltan observaciones recientes para la fecha pedida, se responde con
  advertencia indicando la última fecha con datos.
- **Alternativas:** aceptar cualquier fecha; advertir más allá de `feriados.csv` asumiendo que no hay
  feriados.
- **Justificación:** el servicio opera sobre fechas simuladas (enunciado). Sin calendario, un
  pronóstico de Navidad o del 31 de diciembre se equivocaría por un factor de 3 a 5
  (`docs/perfil_datos.md`: índice 0.32 en Navidad, 1.69 el 31 de diciembre); el periodo de evaluación
  está cubierto por `feriados.csv`.

## Modelo

### D13. Información que usa el modelo al predecir
- **Propuesta:** para la fecha *d* solo se usan ventas de fechas anteriores a *d*: rezagos y medias
  móviles (1, 7, 14, 28 días) por tienda y familia; el `en_promocion` de la solicitud; tipo y ciudad
  de la tienda; familia; día de la semana y del mes; feriados nacionales y locales (el `ambito`
  coincide con la ciudad de la tienda), fechas comerciales y de pago con su distancia; y la quincena
  (días 15 y último del mes) derivada del calendario.
- **Por qué la quincena aparte:** `feriados.csv` solo marca 6 fechas de pago (Bono 14 y aguinaldo),
  pero las ventas suben el 15 (índice 1.17) y a fin de mes (1.36 el día 31).
- **Por qué un nivel reciente:** las ventas crecen 10.3 % al año (mediana interanual) y el periodo de
  evaluación puede traer cambios de demanda; se comparará en F3 un objetivo relativo al nivel de los
  últimos 28 días contra el objetivo directo.

### D14. Cantidad sugerida: newsvendor por familia, calibrada por costo
- **Propuesta:** `cantidad_sugerida = ceil(venta_esperada × k_f)`, con un factor k_f por familia
  elegido en validación minimizando el costo de `costos.csv`. La justificación teórica es el cuantil
  crítico τ_f (`docs/perfil_datos.md`): de 0.29 en panadería (sugerir por debajo) a 0.95 en licores
  (sugerir por encima). Los factores viajan con la versión del modelo.

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
- **Propuesta:** la API consulta cada 30 s la versión del alias `champion` y, si cambió, carga la
  nueva y la reemplaza de forma atómica (requisito: ≤ 2 minutos). Guarda una copia del modelo en un
  volumen para arrancar aunque MLflow no esté disponible. Un monitor en segundo plano revisa cada
  15 s la base de datos, MLflow, Airflow y el modelo; `/health` responde con ese estado.
