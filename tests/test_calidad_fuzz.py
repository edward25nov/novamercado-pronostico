"""Fuzzing: con cualquier cuerpo, la limpieza devuelve una solicitud canónica válida o un Rechazo,
nunca otra excepción (que sería un 500). También con mutaciones de una solicitud válida."""

import json
import os

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from novamercado.calidad import Rechazo, estado, limpiar_observacion, limpiar_prediccion
from novamercado.calidad.esquemas import ObservacionCanonica, PrediccionCanonica
from tests.catalogo_prueba import FAMILIAS, catalogo, observacion, prediccion

CAT = catalogo()
# FUZZ_EJEMPLOS=5000 para una corrida larga (en la CI, 400 por prueba)
AJUSTES = settings(max_examples=int(os.environ.get("FUZZ_EJEMPLOS", "400")), deadline=None,
                   suppress_health_check=[HealthCheck.too_slow])

escalar = st.one_of(st.none(), st.booleans(), st.integers(-10**6, 10**6), st.floats(allow_nan=True),
                    st.text(max_size=20), st.sampled_from(["T05", "5", "17/11/2025", "LÁCTEOS", "1,234", "-4",
                                                           "2025-11-17", "abarrotes", "nan", "∞"]))
json_cualquiera = st.recursive(escalar, lambda hijos: st.one_of(
    st.lists(hijos, max_size=5), st.dictionaries(st.text(max_size=12), hijos, max_size=5)), max_leaves=25)
claves = st.sampled_from(["tienda_id", "tienda", "fecha", "familias", "ventas", "familia_id", "en_promocion",
                          "x", "Fecha", "TIENDA_ID", "promo"])


def _verificar(funcion, cuerpo, canonica):
    try:
        sol, obs = funcion(cuerpo, CAT)
    except Rechazo as r:
        assert isinstance(r.detalle, str) and r.detalle
        return
    assert isinstance(sol, canonica)
    assert estado(obs) in ("ok", "corregido", "advertencia")
    assert all(o.accion in ("reparar", "advertir") for o in obs)


@AJUSTES
@given(json_cualquiera)
def test_prediccion_con_json_arbitrario(cuerpo):
    _verificar(limpiar_prediccion, cuerpo, PrediccionCanonica)


@AJUSTES
@given(json_cualquiera)
def test_observacion_con_json_arbitrario(cuerpo):
    _verificar(limpiar_observacion, cuerpo, ObservacionCanonica)


@AJUSTES
@given(st.binary(max_size=200))
def test_bytes_arbitrarios(cuerpo):
    _verificar(limpiar_prediccion, cuerpo, PrediccionCanonica)


@AJUSTES
@given(st.data())
def test_mutaciones_de_una_solicitud_valida(data):
    cuerpo = prediccion()
    for _ in range(data.draw(st.integers(1, 4))):
        accion = data.draw(st.sampled_from(["raiz", "item", "borrar", "renombrar"]))
        if accion == "raiz":
            cuerpo[data.draw(claves)] = data.draw(json_cualquiera)
        elif accion == "item" and cuerpo.get("familias") and isinstance(cuerpo["familias"], list):
            i = data.draw(st.integers(0, len(cuerpo["familias"]) - 1))
            if isinstance(cuerpo["familias"][i], dict):
                cuerpo["familias"][i][data.draw(claves)] = data.draw(json_cualquiera)
        elif accion == "borrar" and cuerpo:
            cuerpo.pop(data.draw(st.sampled_from(sorted(cuerpo))), None)
        elif accion == "renombrar" and "tienda_id" in cuerpo:
            cuerpo[data.draw(claves)] = cuerpo.pop("tienda_id")
    _verificar(limpiar_prediccion, cuerpo, PrediccionCanonica)
    _verificar(limpiar_prediccion, json.dumps(cuerpo, default=str).encode(), PrediccionCanonica)


@AJUSTES
@given(st.data())
def test_mutaciones_de_una_observacion_valida(data):
    cuerpo = observacion()
    i = data.draw(st.integers(0, len(FAMILIAS) - 1))
    cuerpo["ventas"][i]["ventas"] = data.draw(json_cualquiera)
    cuerpo["ventas"][i]["familia_id"] = data.draw(st.one_of(st.sampled_from(list(FAMILIAS)), json_cualquiera))
    _verificar(limpiar_observacion, cuerpo, ObservacionCanonica)
