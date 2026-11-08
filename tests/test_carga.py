import pytest

from novamercado.datos import carga


def _contar(con, tabla):
    return con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


# --- Sin base de datos

def test_falta_un_archivo(datos):
    (datos / "costos.csv").unlink()
    with pytest.raises(carga.ErrorDatosPublicados, match="falta"):
        carga.validar_archivo(datos, carga.ARCHIVOS[2])


def test_columnas_distintas(datos):
    (datos / "familias.csv").write_text("familia,nombre\nabarrotes,Abarrotes\n", encoding="utf-8")
    with pytest.raises(carga.ErrorDatosPublicados, match="columnas"):
        carga.validar_archivo(datos, carga.ARCHIVOS[1])


def test_columnas_en_otro_orden_se_aceptan(datos):
    (datos / "familias.csv").write_text("nombre,familia_id\nAbarrotes,abarrotes\n", encoding="utf-8")
    assert carga.validar_archivo(datos, carga.ARCHIVOS[1]) == ["nombre", "familia_id"]


# --- Con base de datos

def test_primera_carga(con, datos):
    carga.aplicar_esquema(con)
    resumen = carga.cargar_publicados(con, datos)
    assert all("filas" in v for v in resumen.values())
    assert _contar(con, "tiendas") == 2
    assert _contar(con, "feriados") == 2
    assert _contar(con, "ventas") == 6
    assert con.execute("SELECT count(*) FROM ventas WHERE origen = 'historico'").fetchone()[0] == 6
    # Los tipos llegan bien: fecha como date, ventas como entero
    assert con.execute("SELECT ventas FROM ventas WHERE tienda_id = 1 AND fecha = '2025-03-15' "
                       "AND familia_id = 'lacteos'").fetchone()[0] == 250


def test_segunda_carga_no_repite_trabajo(con, datos):
    carga.aplicar_esquema(con)
    carga.cargar_publicados(con, datos)
    carga.aplicar_esquema(con)  # el esquema también es idempotente
    resumen = carga.cargar_publicados(con, datos)
    assert set(resumen.values()) == {"sin cambios"}
    assert _contar(con, "ventas") == 6


def test_archivo_modificado_actualiza_sin_duplicar(con, datos):
    carga.aplicar_esquema(con)
    carga.cargar_publicados(con, datos)
    ruta = datos / "historico_ventas.csv"
    ruta.write_text(ruta.read_text().replace("2025-03-16,1,abarrotes,610,0", "2025-03-16,1,abarrotes,615,0"))
    resumen = carga.cargar_publicados(con, datos)
    assert resumen["historico_ventas.csv"] == "1 filas nuevas o modificadas"
    assert resumen["tiendas.csv"] == "sin cambios"
    assert _contar(con, "ventas") == 6
    assert con.execute("SELECT ventas FROM ventas WHERE tienda_id = 1 AND fecha = '2025-03-16' "
                       "AND familia_id = 'abarrotes'").fetchone()[0] == 615


def test_historico_no_pisa_una_observacion(con, datos):
    carga.aplicar_esquema(con)
    carga.cargar_publicados(con, datos)
    con.execute("UPDATE ventas SET ventas = 700, origen = 'observacion' WHERE tienda_id = 1 "
                "AND fecha = '2025-03-16' AND familia_id = 'abarrotes'")
    ruta = datos / "historico_ventas.csv"
    ruta.write_text(ruta.read_text().replace("2025-03-16,1,abarrotes,610,0", "2025-03-16,1,abarrotes,615,0"))
    carga.cargar_publicados(con, datos)
    assert con.execute("SELECT ventas, origen FROM ventas WHERE tienda_id = 1 AND fecha = '2025-03-16' "
                       "AND familia_id = 'abarrotes'").fetchone() == (700, "observacion")


def test_archivo_invalido_no_carga_nada(con, datos):
    carga.aplicar_esquema(con)
    (datos / "historico_ventas.csv").write_text("fecha,tienda\n", encoding="utf-8")
    with pytest.raises(carga.ErrorDatosPublicados):
        carga.cargar_publicados(con, datos)
    assert _contar(con, "cargas") == 0  # se valida todo antes de cargar el primero
