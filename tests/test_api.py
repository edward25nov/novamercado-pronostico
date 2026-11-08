"""Contrato de la API (Anexo) contra Postgres real y un modelo pequeño entrenado en la prueba.
No necesitan MLflow ni Airflow: el modelo se pone directamente en el estado del servicio."""

import json
import os
import threading
import uuid
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import psycopg
import pytest
from fastapi.testclient import TestClient

from novamercado import config
from novamercado.datos import carga, lectura
from novamercado.modelo import entrenamiento
from novamercado.servicio import app as modulo_app
from novamercado.servicio import repositorio
from novamercado.servicio.estado import Cargador, Estado, ModeloVigente
from tests.conftest import DATOS_PRUEBA

URL = os.environ.get("NOVAMERCADO_TEST_DB_URL")
pytestmark = pytest.mark.skipif(not URL, reason="NOVAMERCADO_TEST_DB_URL no definida")
ULTIMO_DIA = pd.Timestamp("2025-06-30")


def _ventas_sinteticas() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    filas = []
    for tienda, desde, base in [(1, "2025-01-01", 300), (2, "2025-03-15", 60)]:
        for familia, factor in [("abarrotes", 1.0), ("lacteos", 0.4)]:
            fechas = pd.date_range(desde, ULTIMO_DIA)
            promo = rng.integers(0, 4, len(fechas))
            media = base * factor * (1 + 0.3 * (fechas.dayofweek >= 5)) * (1 + 0.05 * promo)
            filas.append(
                pd.DataFrame(
                    {
                        "tienda_id": tienda,
                        "familia_id": familia,
                        "fecha": fechas,
                        "ventas": rng.poisson(media),
                        "en_promocion": promo,
                    }
                )
            )
    return pd.concat(filas, ignore_index=True)


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    esquema = f"prueba_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {esquema}")
    u = urlparse(URL)
    anterior = dict(os.environ)
    os.environ.update(
        {
            "PRODUCTO_DB_USUARIO": u.username,
            "PRODUCTO_DB_CLAVE": u.password or "",
            "PRODUCTO_DB_HOST": u.hostname,
            "PRODUCTO_DB_PUERTO": str(u.port or 5432),
            "PRODUCTO_DB_NOMBRE": u.path.lstrip("/"),
            "PRODUCTO_DB_OPCIONES": f"-c search_path={esquema}",
            "NOVAMERCADO_CACHE": str(tmp_path_factory.mktemp("cache")),
            "NOVAMERCADO_SIN_MONITOR": "1",
        }
    )
    cfg = config.leer()
    with psycopg.connect(cfg.db_url, autocommit=True) as con:
        carga.aplicar_esquema(con)
        carga.cargar_publicados(con, DATOS_PRUEBA)
        con.execute("DELETE FROM ventas")
        v = _ventas_sinteticas()
        with con.cursor().copy(
            "COPY ventas (tienda_id, familia_id, fecha, ventas, en_promocion, origen) FROM STDIN"
        ) as cp:
            for r in v.itertuples(index=False):
                cp.write_row(
                    (r.tienda_id, r.familia_id, r.fecha.date(), int(r.ventas), int(r.en_promocion), "historico")
                )
        res = entrenamiento.entrenar(lectura.ventas(con), lectura.catalogos(con), n_ventanas=1)
    estado = Estado(cfg)
    estado.modelo = ModeloVigente(res.pronosticador, "novamercado-ventas", "champion", "7", "mlflow")
    estado.salud = {"db": None, "mlflow": None, "airflow": None}
    estado.refrescar_catalogo()
    modulo_app.app.state.estado = estado
    with TestClient(modulo_app.app) as cliente:
        yield cliente, estado, cfg, res.pronosticador
    os.environ.clear()
    os.environ.update(anterior)
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f"DROP SCHEMA {esquema} CASCADE")


def _sql(cfg, consulta, params=None):
    with psycopg.connect(cfg.db_url, autocommit=True) as con:
        return con.execute(consulta, params).fetchall()


def _pred(tienda=1, fecha="2025-07-01", **extra):
    cuerpo = {
        "tienda_id": tienda,
        "fecha": fecha,
        "familias": [{"familia_id": "abarrotes", "en_promocion": 2}, {"familia_id": "lacteos", "en_promocion": 0}],
    }
    cuerpo.update(extra)
    return cuerpo


# --- POST /v1/prediccion


def test_prediccion_valida_cumple_el_contrato(entorno):
    cliente, *_ = entorno
    r = cliente.post("/v1/prediccion", json=_pred())
    assert r.status_code == 200, r.text
    d = r.json()
    assert {"tienda_id", "fecha", "version_modelo", "predicciones", "calidad"} <= set(d)
    assert d["tienda_id"] == 1 and d["fecha"] == "2025-07-01"
    assert d["version_modelo"] == "7" and isinstance(d["version_modelo"], str)
    assert d["calidad"] == {"estado": "ok", "observaciones": []}
    assert [p["familia_id"] for p in d["predicciones"]] == ["abarrotes", "lacteos"]
    for p in d["predicciones"]:
        assert set(p) == {"familia_id", "venta_esperada", "cantidad_sugerida"}
        assert isinstance(p["cantidad_sugerida"], int) and p["cantidad_sugerida"] >= 0
        assert isinstance(p["venta_esperada"], float) and p["venta_esperada"] > 0


def test_prediccion_corregida_informa_que_hizo(entorno):
    cliente, *_ = entorno
    cuerpo = _pred(tienda="T01", fecha="2025/07/01")
    cuerpo["familias"][1]["familia_id"] = "LÁCTEOS"
    d = cliente.post("/v1/prediccion", content=json.dumps(cuerpo, ensure_ascii=False).encode()).json()
    assert d["calidad"]["estado"] == "corregido"
    campos = {o["campo"]: o for o in d["calidad"]["observaciones"]}
    assert campos["familias[1].familia_id"] == {
        "campo": "familias[1].familia_id",
        "accion": "reparar",
        "detalle": "'LÁCTEOS' se interpretó como 'lacteos'",
    }
    assert set(campos) == {"tienda_id", "fecha", "familias[1].familia_id"}


def test_prediccion_rechazada_responde_422_con_detail_y_se_registra(entorno):
    cliente, _, cfg, _ = entorno
    r = cliente.post("/v1/prediccion", json=_pred(tienda=99))
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and "99" in r.json()["detail"]
    fila = _sql(cfg, "SELECT codigo_http, detalle, cuerpo_crudo FROM solicitudes ORDER BY id DESC LIMIT 1")[0]
    assert fila[0] == 422 and "99" in fila[1] and '"tienda_id":99' in fila[2].replace(" ", "")


def test_cuerpo_que_no_es_json_es_422(entorno):
    cliente, *_ = entorno
    r = cliente.post("/v1/prediccion", content=b"esto no es json", headers={"content-type": "text/plain"})
    assert r.status_code == 422 and "JSON" in r.json()["detail"]


def test_prediccion_queda_registrada_con_su_version(entorno):
    cliente, _, cfg, _ = entorno
    cliente.post("/v1/prediccion", json=_pred(tienda="T01", fecha="2025-07-01"))
    sid, estado = _sql(
        cfg, "SELECT id, estado_calidad FROM solicitudes WHERE codigo_http = 200 ORDER BY id DESC LIMIT 1"
    )[0]
    assert estado == "corregido"
    preds = _sql(
        cfg,
        "SELECT familia_id, en_promocion, version_modelo FROM predicciones WHERE solicitud_id = %s ORDER BY familia_id",
        (sid,),
    )
    assert preds == [("abarrotes", 2, "7"), ("lacteos", 0, "7")]
    assert _sql(cfg, "SELECT accion FROM correcciones WHERE solicitud_id = %s", (sid,)) == [("reparar",)]


def test_misma_fecha_dos_veces_se_registra_dos_veces(entorno):
    cliente, _, cfg, _ = entorno
    antes = _sql(cfg, "SELECT count(*) FROM predicciones WHERE tienda_id = 2 AND fecha = '2025-07-01'")[0][0]
    a = cliente.post("/v1/prediccion", json=_pred(tienda=2)).json()
    b = cliente.post("/v1/prediccion", json=_pred(tienda=2)).json()
    assert a["predicciones"] == b["predicciones"]  # mismo modelo y mismos datos: misma respuesta
    assert (
        _sql(cfg, "SELECT count(*) FROM predicciones WHERE tienda_id = 2 AND fecha = '2025-07-01'")[0][0] == antes + 4
    )


def test_familia_faltante_usa_la_ultima_promocion_registrada(entorno):
    cliente, *_ = entorno
    cuerpo = _pred(tienda=2, fecha="2025-07-01")
    cuerpo["familias"][1]["en_promocion"] = 3
    cliente.post("/v1/prediccion", json=cuerpo)
    d = cliente.post(
        "/v1/prediccion", json=_pred(tienda=2, familias=[{"familia_id": "abarrotes", "en_promocion": 0}])
    ).json()
    assert d["calidad"]["estado"] == "advertencia"
    assert any("se usó 3, la última promoción conocida" in o["detalle"] for o in d["calidad"]["observaciones"])


def test_faltan_ventas_recientes_se_advierte(entorno):
    cliente, *_ = entorno
    d = cliente.post("/v1/prediccion", json=_pred(fecha="2025-07-06")).json()
    assert d["calidad"]["estado"] == "advertencia"
    obs = [o for o in d["calidad"]["observaciones"] if o["campo"] == "fecha"]
    assert obs and "2025-06-30" in obs[0]["detalle"]


def test_excepcion_inesperada_en_la_limpieza_es_422_no_500(entorno, monkeypatch):
    cliente, *_ = entorno

    def falla(*a, **k):
        raise ValueError("regla rota")

    monkeypatch.setattr(modulo_app.calidad, "limpiar_prediccion", falla)
    r = cliente.post("/v1/prediccion", json=_pred())
    assert r.status_code == 422 and "no se pudo interpretar" in r.json()["detail"]


def test_cambio_de_modelo_se_refleja_sin_reiniciar(entorno):
    cliente, estado, _, p = entorno
    original = estado.modelo
    estado.modelo = ModeloVigente(p, "novamercado-ventas", "champion", "8", "mlflow")
    try:
        assert cliente.post("/v1/prediccion", json=_pred()).json()["version_modelo"] == "8"
        assert cliente.get("/modelo").json()["version"] == "8"
    finally:
        estado.modelo = original


def test_sin_modelo_prediccion_y_health_responden_503(entorno):
    cliente, estado, *_ = entorno
    original = estado.modelo
    estado.modelo = None
    try:
        assert cliente.post("/v1/prediccion", json=_pred()).status_code == 503
        r = cliente.get("/health")
        assert r.status_code == 503 and r.json()["estado"] == "sin_modelo"
        assert cliente.get("/modelo").status_code == 503
        # las observaciones no necesitan el modelo
        assert (
            cliente.post(
                "/v1/observaciones",
                json={"tienda_id": 2, "fecha": "2025-07-20", "ventas": [{"familia_id": "abarrotes", "ventas": 1}]},
            ).status_code
            == 200
        )
    finally:
        estado.modelo = original


# --- POST /v1/observaciones


def _obs(fecha="2025-07-01", abarrotes=310, lacteos=120, tienda=1):
    return {
        "tienda_id": tienda,
        "fecha": fecha,
        "ventas": [{"familia_id": "abarrotes", "ventas": abarrotes}, {"familia_id": "lacteos", "ventas": lacteos}],
    }


def test_observaciones_son_idempotentes(entorno):
    cliente, _, cfg, _ = entorno
    r = cliente.post("/v1/observaciones", json=_obs(fecha="2025-07-02"))
    assert r.status_code == 200 and r.json() == {
        "registros_guardados": 2,
        "calidad": {"estado": "ok", "observaciones": []},
    }
    assert cliente.post("/v1/observaciones", json=_obs(fecha="2025-07-02")).json()["registros_guardados"] == 0
    assert _sql(cfg, "SELECT count(*) FROM ventas WHERE fecha = '2025-07-02' AND tienda_id = 1")[0][0] == 2


def test_observacion_corregida_cuenta_como_modificada_y_queda_en_historial(entorno):
    cliente, _, cfg, _ = entorno
    cliente.post("/v1/observaciones", json=_obs(fecha="2025-07-03"))
    d = cliente.post("/v1/observaciones", json=_obs(fecha="2025-07-03", abarrotes=999)).json()
    assert d["registros_guardados"] == 1
    assert _sql(cfg, "SELECT ventas_anterior, ventas_nueva FROM ventas_historial WHERE fecha = '2025-07-03'") == [
        (310, 999)
    ]


def test_observacion_igual_al_historico_no_guarda_nada(entorno):
    cliente, _, cfg, _ = entorno
    ab, la = (
        _sql(cfg, "SELECT ventas FROM ventas WHERE tienda_id = 1 AND fecha = '2025-06-15' AND familia_id = %s", (f,))[
            0
        ][0]
        for f in ("abarrotes", "lacteos")
    )
    assert cliente.post("/v1/observaciones", json=_obs("2025-06-15", ab, la)).json()["registros_guardados"] == 0


def test_observacion_con_problemas_informa_y_no_inventa(entorno):
    cliente, _, cfg, _ = entorno
    cuerpo = _obs(fecha="2025-07-04")
    cuerpo["ventas"][0]["ventas"] = "1,310"
    cuerpo["ventas"][1]["ventas"] = -4
    d = cliente.post("/v1/observaciones", json=cuerpo).json()
    assert d["registros_guardados"] == 1 and d["calidad"]["estado"] == "advertencia"
    assert _sql(cfg, "SELECT familia_id, ventas FROM ventas WHERE fecha = '2025-07-04' AND tienda_id = 1") == [
        ("abarrotes", 1310)
    ]


def test_observacion_mejora_la_siguiente_prediccion(entorno):
    cliente, *_ = entorno
    for f in ("2025-07-05", "2025-07-06", "2025-07-07"):
        cliente.post("/v1/observaciones", json=_obs(fecha=f))
    d = cliente.post("/v1/prediccion", json=_pred(fecha="2025-07-06")).json()
    assert not [o for o in d["calidad"]["observaciones"] if o["campo"] == "fecha"]


def test_observaciones_simultaneas_no_duplican(entorno):
    _, _, cfg, _ = entorno
    from datetime import date

    from novamercado.calidad.esquemas import ObservacionCanonica

    obs = ObservacionCanonica.model_validate(
        {"tienda_id": 2, "fecha": date(2025, 7, 10), "ventas": [{"familia_id": "abarrotes", "ventas": 50}]}
    )
    totales = []

    def guardar():
        with repositorio.conectar(cfg.db_url) as con:
            sid = repositorio.registrar_solicitud(con, "observaciones", b"{}", 200)
            totales.append(repositorio.guardar_observacion(con, sid, obs))

    hilos = [threading.Thread(target=guardar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(totales) == [0, 0, 0, 0, 0, 1]


# --- GET /modelo y /health


def test_modelo_vigente(entorno):
    cliente, *_ = entorno
    d = cliente.get("/modelo").json()
    assert {k: d[k] for k in ("nombre", "alias", "version")} == {
        "nombre": "novamercado-ventas",
        "alias": "champion",
        "version": "7",
    }
    assert all(isinstance(d[k], str) for k in ("nombre", "alias", "version"))


def test_health_ok_y_degradado(entorno):
    cliente, estado, *_ = entorno
    assert cliente.get("/health").json()["estado"] == "ok"
    estado.salud = {"db": None, "mlflow": "MLflow no disponible (ConnectError)", "airflow": None}
    try:
        r = cliente.get("/health")
        assert r.status_code == 200 and r.json()["estado"] == "degradado" and "MLflow" in r.json()["motivo"]
        # sigue prediciendo con el modelo cargado
        assert cliente.post("/v1/prediccion", json=_pred()).status_code == 200
    finally:
        estado.salud = {"db": None, "mlflow": None, "airflow": None}


# --- Cargador: caché y recarga


def test_cargador_usa_cache_y_recarga_solo_si_cambia_el_modelo(entorno, tmp_path, monkeypatch):
    _, _, cfg, p = entorno
    from dataclasses import replace

    cfg = replace(cfg, cache_dir=tmp_path)
    descargas = []

    def descargar(uri, version, destino):
        descargas.append(version)
        return p

    monkeypatch.setattr(entrenamiento, "descargar", descargar)
    vigente = {"v": ("3", "run-a")}
    monkeypatch.setattr(entrenamiento, "vigente", lambda uri: vigente["v"])
    c = Cargador(cfg)
    m, motivo = c.actualizar(None)
    assert (m.version, m.run_id) == ("3", "run-a") and motivo is None and descargas == ["3"]
    assert c.actualizar(m)[0] is m and descargas == ["3"]  # mismo modelo: no descarga
    vigente["v"] = ("4", "run-b")
    m4, _ = c.actualizar(m)
    assert m4.version == "4" and descargas == ["3", "4"]
    # Otro arranque sin MLflow: la caché tiene el último modelo cargado
    en_cache = Cargador(cfg).desde_cache()
    assert (en_cache.version, en_cache.run_id, en_cache.origen) == ("4", "run-b", "cache")
    # Se perdió el volumen de MLflow: una "v4" nueva con otro run no usa la carpeta vieja
    vigente["v"] = ("4", "run-c")
    m4c, _ = c.actualizar(m4)
    assert m4c.run_id == "run-c" and descargas == ["3", "4", "4"]
    vigente["v"] = None
    assert c.actualizar(m4c)[0] is m4c  # sin champion en MLflow: se conserva el que hay


def test_estado_conserva_el_modelo_si_mlflow_falla(entorno, monkeypatch):
    _, estado, cfg, _ = entorno
    nuevo = Estado(cfg)
    nuevo.modelo = estado.modelo

    def caido(uri):
        raise ConnectionError("MLflow caído")

    monkeypatch.setattr(entrenamiento, "vigente", caido)
    monkeypatch.setattr(
        "novamercado.servicio.dependencias.revisar_todas", lambda c: {"db": None, "mlflow": None, "airflow": None}
    )
    nuevo.revisar()
    assert nuevo.modelo is estado.modelo


def test_catalogo_espera_a_que_haya_ventas(entorno, monkeypatch):
    _, _, cfg, _ = entorno
    nuevo = Estado(cfg)
    monkeypatch.setattr(repositorio, "ultima_fecha_ventas", lambda con: None)  # base aún sin histórico
    nuevo.refrescar_catalogo()
    assert nuevo.catalogo is None
    monkeypatch.undo()
    nuevo.refrescar_catalogo()
    assert nuevo.catalogo is not None and str(nuevo.catalogo.fecha_max_datos) >= "2025-06-30"


def test_promocion_previa_no_mira_fechas_posteriores(entorno):
    _, _, cfg, _ = entorno
    with repositorio.conectar(cfg.db_url) as con:
        sid = repositorio.registrar_solicitud(con, "prediccion", b"{}", 200)
        con.execute("INSERT INTO predicciones (solicitud_id, tienda_id, fecha, familia_id, en_promocion, "
                    "venta_esperada, cantidad_sugerida, version_modelo) VALUES (%s, 1, '2025-09-01', 'lacteos', "
                    "17, 1, 1, '7')", (sid,))
        from datetime import date
        assert repositorio.ultima_promocion(con, 1, "lacteos", date(2025, 7, 15)) != 17
        assert repositorio.ultima_promocion(con, 1, "lacteos", date(2025, 9, 2)) == 17
