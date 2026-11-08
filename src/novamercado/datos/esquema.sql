-- Esquema de la base del producto (Postgres). Idempotente: se aplica en cada arranque.
-- Ver DECISIONES.md D6 (una sola tabla de ventas) y D20 (registro de la operación).

-- Archivos publicados ya cargados, con su huella: si la huella no cambia, no se vuelve a cargar.
CREATE TABLE IF NOT EXISTS cargas (
    archivo     text PRIMARY KEY,
    huella      text NOT NULL,
    filas       integer NOT NULL,
    cargado_en  timestamptz NOT NULL DEFAULT now()
);

-- Catálogos (de los archivos publicados)
CREATE TABLE IF NOT EXISTS tiendas (
    tienda_id       integer PRIMARY KEY,
    nombre          text NOT NULL,
    ciudad          text NOT NULL,
    departamento    text NOT NULL,
    tipo            text NOT NULL,
    fecha_apertura  date NOT NULL
);

CREATE TABLE IF NOT EXISTS familias (
    familia_id  text PRIMARY KEY,
    nombre      text NOT NULL
);

CREATE TABLE IF NOT EXISTS costos (
    familia_id      text PRIMARY KEY REFERENCES familias,
    costo_faltante  double precision NOT NULL CHECK (costo_faltante >= 0),
    costo_sobrante  double precision NOT NULL CHECK (costo_sobrante >= 0)
);

CREATE TABLE IF NOT EXISTS feriados (
    fecha   date NOT NULL,
    nombre  text NOT NULL,
    tipo    text NOT NULL,
    ambito  text NOT NULL,   -- 'nacional' o el nombre de la ciudad (= tiendas.ciudad)
    PRIMARY KEY (fecha, nombre, ambito)
);

-- Registro de cada solicitud recibida, incluidas las rechazadas.
-- recibido_en usa el reloj solo como auditoría; ninguna regla de negocio lo lee (CLAUDE.md).
CREATE TABLE IF NOT EXISTS solicitudes (
    id                  bigserial PRIMARY KEY,
    endpoint            text NOT NULL,          -- 'prediccion' | 'observaciones'
    recibido_en         timestamptz NOT NULL DEFAULT now(),
    cuerpo_crudo        text NOT NULL,          -- tal como llegó (puede no ser JSON válido)
    cuerpo_normalizado  jsonb,                  -- forma canónica tras la limpieza (null si se rechazó)
    tienda_id           integer,
    fecha               date,
    codigo_http         integer NOT NULL,
    estado_calidad      text CHECK (estado_calidad IN ('ok', 'corregido', 'advertencia')),
    detalle             text                    -- motivo del rechazo
);
CREATE INDEX IF NOT EXISTS solicitudes_tienda_fecha ON solicitudes (tienda_id, fecha);

-- Cada observación de calidad (reparar / advertir) aplicada a una solicitud.
CREATE TABLE IF NOT EXISTS correcciones (
    id            bigserial PRIMARY KEY,
    solicitud_id  bigint NOT NULL REFERENCES solicitudes ON DELETE CASCADE,
    campo         text NOT NULL,
    accion        text NOT NULL CHECK (accion IN ('reparar', 'advertir')),
    detalle       text NOT NULL
);
CREATE INDEX IF NOT EXISTS correcciones_solicitud ON correcciones (solicitud_id);

-- Una sola tabla para el histórico y las observaciones (D6). en_promocion solo se conoce en el
-- histórico; para las observaciones se toma de la solicitud de pronóstico del día (D13).
CREATE TABLE IF NOT EXISTS ventas (
    tienda_id       integer NOT NULL REFERENCES tiendas,
    fecha           date NOT NULL,
    familia_id      text NOT NULL REFERENCES familias,
    ventas          integer NOT NULL CHECK (ventas >= 0),
    en_promocion    integer CHECK (en_promocion >= 0),
    origen          text NOT NULL CHECK (origen IN ('historico', 'observacion')),
    solicitud_id    bigint REFERENCES solicitudes,   -- observación que la creó o la cambió por última vez
    actualizado_en  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tienda_id, fecha, familia_id)
);
CREATE INDEX IF NOT EXISTS ventas_fecha ON ventas (fecha);

-- Valores anteriores de ventas que una observación modificó (corrección de un dato ya conocido).
CREATE TABLE IF NOT EXISTS ventas_historial (
    id              bigserial PRIMARY KEY,
    tienda_id       integer NOT NULL,
    fecha           date NOT NULL,
    familia_id      text NOT NULL,
    ventas_anterior integer NOT NULL,
    ventas_nueva    integer NOT NULL,
    solicitud_id    bigint REFERENCES solicitudes,
    registrado_en   timestamptz NOT NULL DEFAULT now()
);

-- Cada predicción entregada, con la versión del modelo que la produjo.
CREATE TABLE IF NOT EXISTS predicciones (
    id                 bigserial PRIMARY KEY,
    solicitud_id       bigint NOT NULL REFERENCES solicitudes ON DELETE CASCADE,
    tienda_id          integer NOT NULL,
    fecha              date NOT NULL,
    familia_id         text NOT NULL,
    en_promocion       integer NOT NULL,
    venta_esperada     double precision NOT NULL,
    cantidad_sugerida  integer NOT NULL CHECK (cantidad_sugerida >= 0),
    version_modelo     text NOT NULL
);
CREATE INDEX IF NOT EXISTS predicciones_tienda_fecha ON predicciones (tienda_id, fecha, familia_id);

-- Ejecuciones de reentrenamiento (id = dag_run_id de Airflow).
CREATE TABLE IF NOT EXISTS reentrenamientos (
    id             text PRIMARY KEY,
    solicitado_en  timestamptz NOT NULL DEFAULT now(),
    estado         text NOT NULL CHECK (estado IN ('en_curso', 'exitoso', 'fallido')),
    promovido      boolean,
    version        text,
    motivo         text,
    metricas       jsonb,
    terminado_en   timestamptz
);

-- Hitos del producto (p. ej. que el primer modelo ya se registró), para no repetir trabajo al
-- volver a levantar aunque MLflow no responda en ese momento.
CREATE TABLE IF NOT EXISTS estado_producto (
    clave           text PRIMARY KEY,
    valor           text NOT NULL,
    actualizado_en  timestamptz NOT NULL DEFAULT now()
);
