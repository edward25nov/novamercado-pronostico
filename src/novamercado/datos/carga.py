"""Esquema de la base y carga idempotente de los archivos publicados.

Cada archivo se carga en una transacción junto con su huella (SHA-256) en la tabla `cargas`.
Si la huella ya está registrada, el archivo no se vuelve a leer: el segundo arranque del producto
no repite trabajo (D5). Si un archivo cambia, sus filas se actualizan (upsert), nunca se duplican.
"""

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

ESQUEMA = Path(__file__).with_name("esquema.sql")
# Llave para pg_advisory_lock: dos inicializadores a la vez no cargan en paralelo.
CANDADO_CARGA = 2026_11_15


class ErrorDatosPublicados(Exception):
    """Un archivo publicado falta o no tiene las columnas esperadas."""


@dataclass(frozen=True)
class Archivo:
    nombre: str
    tabla: str
    columnas: tuple[str, ...]
    llave: tuple[str, ...]
    fijas: tuple[tuple[str, str], ...] = ()  # columnas que no vienen en el archivo: (columna, valor)
    # Condición extra para actualizar una fila existente (None = siempre)
    actualizar_si: str | None = None


# En orden de llaves foráneas.
ARCHIVOS = (
    Archivo("tiendas.csv", "tiendas",
            ("tienda_id", "nombre", "ciudad", "departamento", "tipo", "fecha_apertura"), ("tienda_id",)),
    Archivo("familias.csv", "familias", ("familia_id", "nombre"), ("familia_id",)),
    Archivo("costos.csv", "costos", ("familia_id", "costo_faltante", "costo_sobrante"), ("familia_id",)),
    Archivo("feriados.csv", "feriados", ("fecha", "nombre", "tipo", "ambito"), ("fecha", "nombre", "ambito")),
    # Un cambio en el histórico no pisa una venta que ya llegó como observación.
    Archivo("historico_ventas.csv", "ventas",
            ("fecha", "tienda_id", "familia_id", "ventas", "en_promocion"),
            ("tienda_id", "fecha", "familia_id"),
            fijas=(("origen", "historico"),), actualizar_si="ventas.origen = 'historico'"),
)


def huella(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_encabezado(ruta: Path) -> list[str]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return [c.strip() for c in next(csv.reader(f), [])]


def validar_archivo(carpeta: Path, archivo: Archivo) -> list[str]:
    """Devuelve el encabezado del archivo si tiene exactamente las columnas esperadas."""
    ruta = carpeta / archivo.nombre
    if not ruta.is_file():
        raise ErrorDatosPublicados(f"falta {ruta} (ver README: carpeta datos/publicados/)")
    encabezado = leer_encabezado(ruta)
    if sorted(encabezado) != sorted(archivo.columnas):
        raise ErrorDatosPublicados(
            f"{archivo.nombre}: columnas {encabezado}, se esperaban {list(archivo.columnas)}")
    return encabezado


def aplicar_esquema(con: psycopg.Connection) -> None:
    con.execute(ESQUEMA.read_text(encoding="utf-8"))


def _cargar_archivo(con: psycopg.Connection, carpeta: Path, archivo: Archivo, encabezado: list[str]) -> int:
    tmp = sql.Identifier(f"tmp_{archivo.tabla}")
    tabla = sql.Identifier(archivo.tabla)
    cols = sql.SQL(", ").join(map(sql.Identifier, encabezado))
    # Tabla temporal con los tipos de la tabla destino y sin restricciones.
    con.execute(sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA")
                .format(tmp, cols, tabla))
    with con.cursor().copy(sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)")
                           .format(tmp, cols)) as copia, (carpeta / archivo.nombre).open("rb") as f:
        while bloque := f.read(1 << 20):
            copia.write(bloque)

    destino = list(encabezado) + [c for c, _ in archivo.fijas]
    origen = [sql.Identifier(c) for c in encabezado] + [sql.Literal(v) for _, v in archivo.fijas]
    no_llave = [c for c in destino if c not in archivo.llave]
    actualizar = sql.SQL(", ").join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c)) for c in no_llave)
    # Solo se reescriben las filas que cambian: así `filas` cuenta cambios reales.
    distinto = sql.SQL("({}) IS DISTINCT FROM ({})").format(
        sql.SQL(", ").join(sql.SQL("{}.{}").format(tabla, sql.Identifier(c)) for c in no_llave),
        sql.SQL(", ").join(sql.SQL("EXCLUDED.{}").format(sql.Identifier(c)) for c in no_llave))
    condicion = distinto if archivo.actualizar_si is None else sql.SQL("{} AND {}").format(
        distinto, sql.SQL(archivo.actualizar_si))
    cur = con.execute(sql.SQL(
        "INSERT INTO {tabla} ({destino}) SELECT {origen} FROM {tmp} "
        "ON CONFLICT ({llave}) DO UPDATE SET {actualizar} WHERE {condicion}").format(
            tabla=tabla, destino=sql.SQL(", ").join(map(sql.Identifier, destino)),
            origen=sql.SQL(", ").join(origen), tmp=tmp,
            llave=sql.SQL(", ").join(map(sql.Identifier, archivo.llave)),
            actualizar=actualizar, condicion=condicion))
    return cur.rowcount


def cargar_publicados(con: psycopg.Connection, carpeta: Path) -> dict[str, str]:
    """Carga los archivos publicados que no estén registrados con la misma huella.

    Valida todos los archivos antes de cargar el primero. Devuelve un resumen por archivo.
    """
    encabezados = {a.nombre: validar_archivo(carpeta, a) for a in ARCHIVOS}
    resumen = {}
    for archivo in ARCHIVOS:
        h = huella(carpeta / archivo.nombre)
        fila = con.execute("SELECT huella FROM cargas WHERE archivo = %s", (archivo.nombre,)).fetchone()
        if fila and fila[0] == h:
            resumen[archivo.nombre] = "sin cambios"
            continue
        with con.transaction():
            filas = _cargar_archivo(con, carpeta, archivo, encabezados[archivo.nombre])
            con.execute(
                "INSERT INTO cargas (archivo, huella, filas) VALUES (%s, %s, %s) "
                "ON CONFLICT (archivo) DO UPDATE SET huella = EXCLUDED.huella, filas = EXCLUDED.filas, "
                "cargado_en = now()", (archivo.nombre, h, filas))
        resumen[archivo.nombre] = f"{filas} filas nuevas o modificadas"
    return resumen


def preparar_base(url: str, carpeta: Path) -> dict[str, str]:
    """Aplica el esquema y carga los archivos publicados, con un candado contra ejecuciones simultáneas."""
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("SELECT pg_advisory_lock(%s)", (CANDADO_CARGA,))
        try:
            aplicar_esquema(con)
            return cargar_publicados(con, carpeta)
        finally:
            con.execute("SELECT pg_advisory_unlock(%s)", (CANDADO_CARGA,))
