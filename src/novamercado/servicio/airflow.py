"""Cliente mínimo de la API REST v2 de Airflow 3 para /admin/reentrenar (D19)."""

import threading
import time
from urllib.parse import quote

import httpx

from novamercado.config import Config

DAG_ID = "reentrenamiento"
ESTADOS = {"queued": "en_curso", "running": "en_curso", "success": "exitoso", "failed": "fallido"}


class ErrorAirflow(Exception):
    """Airflow no responde o no puede iniciar la ejecución (la API responde 503)."""


class ClienteAirflow:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._token: str | None = None
        self._vence = 0.0
        self._candado = threading.Lock()

    def _encabezados(self) -> dict:
        with self._candado:
            if self._token is None or time.monotonic() > self._vence:
                try:
                    r = httpx.post(f"{self.cfg.airflow_url}/auth/token", timeout=self.cfg.timeout_dependencias_s,
                                   json={"username": self.cfg.airflow_usuario, "password": self.cfg.airflow_clave})
                except httpx.HTTPError as e:
                    raise ErrorAirflow(f"Airflow no disponible ({type(e).__name__})") from e
                if r.status_code not in (200, 201):
                    raise ErrorAirflow(f"Airflow rechazó las credenciales ({r.status_code})")
                self._token = r.json()["access_token"]
                self._vence = time.monotonic() + 600  # renovar antes de que venza
            return {"Authorization": f"Bearer {self._token}"}

    def _pedir(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        try:
            r = httpx.request(metodo, f"{self.cfg.airflow_url}/api/v2{ruta}", headers=self._encabezados(),
                              timeout=max(self.cfg.timeout_dependencias_s, 5), **kw)
        except httpx.HTTPError as e:
            raise ErrorAirflow(f"Airflow no disponible ({type(e).__name__})") from e
        if r.status_code == 401:  # token vencido: uno nuevo y se reintenta una vez
            self._token = None
            r = httpx.request(metodo, f"{self.cfg.airflow_url}/api/v2{ruta}", headers=self._encabezados(),
                              timeout=max(self.cfg.timeout_dependencias_s, 5), **kw)
        return r

    def en_curso(self) -> str | None:
        """id de una ejecución en cola o corriendo, o None."""
        r = self._pedir("GET", f"/dags/{DAG_ID}/dagRuns", params={"state": ["queued", "running"], "limit": 5})
        if r.status_code == 404:
            raise ErrorAirflow("el DAG de reentrenamiento todavía no está cargado en Airflow")
        if r.status_code != 200:
            raise ErrorAirflow(f"Airflow respondió {r.status_code} al listar ejecuciones")
        corridas = r.json().get("dag_runs", [])
        return corridas[0]["dag_run_id"] if corridas else None

    def disparar(self, run_id: str) -> str:
        """Inicia una ejecución con un id propio, corto y seguro en una URL."""
        cuerpo = {"dag_run_id": run_id, "logical_date": None, "conf": {}}
        r = self._pedir("POST", f"/dags/{DAG_ID}/dagRuns", json=cuerpo)
        if r.status_code == 404:
            raise ErrorAirflow("el DAG de reentrenamiento todavía no está cargado en Airflow")
        if r.status_code not in (200, 201):
            raise ErrorAirflow(f"Airflow no pudo iniciar el reentrenamiento ({r.status_code}: {r.text[:200]})")
        return r.json()["dag_run_id"]

    def estado(self, run_id: str) -> str | None:
        """en_curso | exitoso | fallido, o None si Airflow no conoce el id."""
        r = self._pedir("GET", f"/dags/{DAG_ID}/dagRuns/{quote(run_id, safe='')}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise ErrorAirflow(f"Airflow respondió {r.status_code}")
        return ESTADOS.get(r.json().get("state"), "en_curso")
