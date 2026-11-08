from urllib.parse import unquote, urlparse

from novamercado import config


def test_url_db_codifica_la_clave(monkeypatch):
    monkeypatch.setenv("PRODUCTO_DB_USUARIO", "nova")
    monkeypatch.setenv("PRODUCTO_DB_CLAVE", "p@ss:w/rd")
    monkeypatch.setenv("PRODUCTO_DB_HOST", "db")
    monkeypatch.setenv("PRODUCTO_DB_NOMBRE", "novamercado")
    url = urlparse(config.url_db())
    assert url.hostname == "db"
    assert url.port == 5432
    assert unquote(url.password) == "p@ss:w/rd"
    assert url.path == "/novamercado"
