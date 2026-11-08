"""Salud del servicio (D17, D18) sin base, MLflow ni Airflow: dependencias simuladas."""

import time

from fastapi.testclient import TestClient

from novamercado import config
from novamercado.servicio import app as modulo_app
from novamercado.servicio import dependencias
from novamercado.servicio.estado import Estado, ModeloVigente

OK = {"db": None, "mlflow": None, "airflow": None}


def _estado(modelo=True, salud=OK, catalogo=True) -> Estado:
    e = Estado(config.leer())
    e.modelo = ModeloVigente(object(), "novamercado-ventas", "champion", "3", "mlflow") if modelo else None
    e.salud = dict(salud)
    e.catalogo = object() if catalogo else None
    return e


def test_sin_modelo_es_503_con_motivo():
    e = _estado(modelo=False)
    e.motivo_sin_modelo = "todavía no hay un modelo con el alias champion"
    codigo, cuerpo = e.resumen_salud()
    assert codigo == 503 and cuerpo["estado"] == "sin_modelo" and "champion" in cuerpo["motivo"]


def test_todo_bien_es_ok_sin_motivo():
    codigo, cuerpo = _estado().resumen_salud()
    assert codigo == 200 and cuerpo["estado"] == "ok" and "motivo" not in cuerpo


def test_dependencia_caida_es_degradado():
    codigo, cuerpo = _estado(salud={**OK, "mlflow": "MLflow no disponible (ConnectError)"}).resumen_salud()
    assert codigo == 200 and cuerpo["estado"] == "degradado" and "MLflow" in cuerpo["motivo"]


def test_catalogo_sin_cargar_es_degradado():
    assert _estado(catalogo=False).resumen_salud()[1]["estado"] == "degradado"


def test_health_responde_desde_el_estado_sin_esperar_dependencias(monkeypatch):
    def lenta(cfg):
        time.sleep(5)
        return OK

    monkeypatch.setattr(dependencias, "revisar_todas", lenta)  # el endpoint no debe llamarla
    modulo_app.app.state.estado = _estado()
    try:
        inicio = time.perf_counter()
        r = TestClient(modulo_app.app).get("/health")
        assert r.status_code == 200 and r.json()["estado"] == "ok"
        assert time.perf_counter() - inicio < 1
    finally:
        del modulo_app.app.state.estado


def test_monitor_refleja_la_caida_y_la_vuelta(monkeypatch):
    e = _estado()
    monkeypatch.setattr(e, "refrescar_catalogo", lambda: None)
    monkeypatch.setattr(e.cargador, "actualizar", lambda m: (m, None))
    monkeypatch.setattr(dependencias, "revisar_todas", lambda cfg: {**OK, "mlflow": "MLflow no disponible"})
    e.revisar()
    assert e.resumen_salud()[1]["estado"] == "degradado"
    monkeypatch.setattr(dependencias, "revisar_todas", lambda cfg: OK)
    e.revisar()
    assert e.resumen_salud()[1]["estado"] == "ok"


def test_vivo_no_consulta_dependencias(monkeypatch):
    def explota(cfg):
        raise AssertionError("/vivo no debe revisar dependencias")

    monkeypatch.setattr(dependencias, "revisar_todas", explota)
    assert TestClient(modulo_app.app).get("/vivo").status_code == 200


def test_dependencias_lentas_se_revisan_en_paralelo(monkeypatch):
    """Con las tres dependencias tardando 1 s, la revisión tarda ~1 s (en serie serían 3 s)."""

    def lenta(cfg):
        time.sleep(1.0)
        return "no responde"

    monkeypatch.setattr(dependencias, "REVISIONES", {"db": lenta, "mlflow": lenta, "airflow": lenta})
    inicio = time.perf_counter()
    revision = dependencias.revisar_todas(config.leer())
    assert time.perf_counter() - inicio < 2.0 and all(revision.values())


def test_falla_del_catalogo_no_impide_cargar_el_modelo(monkeypatch):
    """Arranque: la API levanta antes de que el inicializador cargue el histórico (caso real de F5)."""
    e = _estado(modelo=False, catalogo=False)

    def catalogo_falla():
        raise TypeError("Cannot compare NaT with datetime.date object")

    cargado = ModeloVigente(object(), "novamercado-ventas", "champion", "1", "mlflow")
    monkeypatch.setattr(e, "refrescar_catalogo", catalogo_falla)
    monkeypatch.setattr(e.cargador, "actualizar", lambda m: (cargado, None))
    monkeypatch.setattr(dependencias, "revisar_todas", lambda cfg: OK)
    e.revisar()
    assert e.modelo is cargado
