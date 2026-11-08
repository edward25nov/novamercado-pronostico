from fastapi.testclient import TestClient

from novamercado.servicio import app as modulo_app
from novamercado.servicio import dependencias


def _cliente(monkeypatch, revision, modelo):
    monkeypatch.setattr(dependencias, "revisar_todas", lambda cfg: revision)
    modulo_app.app.state.modelo = modelo  # State de Starlette no admite monkeypatch.setattr
    return TestClient(modulo_app.app)


def teardown_function():
    modulo_app.app.state.modelo = None


def test_sin_modelo_responde_503(monkeypatch):
    r = _cliente(monkeypatch, {"db": None, "mlflow": None, "airflow": None}, None).get("/health")
    assert r.status_code == 503
    assert r.json()["estado"] == "sin_modelo"


def test_con_modelo_y_dependencias_ok(monkeypatch):
    r = _cliente(monkeypatch, {"db": None, "mlflow": None, "airflow": None}, object()).get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert "motivo" not in r.json()


def test_dependencia_caida_es_degradado(monkeypatch):
    revision = {"db": None, "mlflow": "MLflow no disponible (ConnectError)", "airflow": None}
    r = _cliente(monkeypatch, revision, object()).get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "degradado"
    assert "MLflow" in r.json()["motivo"]
