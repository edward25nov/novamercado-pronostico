"""Política de calidad (D7–D12): catálogo E01–E10 y casos que no están en el catálogo."""

import json
from datetime import date

import pytest

from novamercado.calidad import Rechazo, estado, limpiar_observacion, limpiar_prediccion
from tests.catalogo_prueba import FAMILIAS, catalogo, observacion, prediccion

CAT = catalogo()


def _pred(cuerpo, **kw):
    sol, obs = limpiar_prediccion(cuerpo, CAT, **kw)
    return sol, obs, estado(obs), {f.familia_id: f.en_promocion for f in sol.familias}


def _acciones(obs):
    return [(o.campo, o.accion) for o in obs]


# --- Solicitud válida

def test_valida_queda_ok_sin_observaciones():
    sol, obs, est, promos = _pred(prediccion())
    assert est == "ok" and obs == []
    assert sol.tienda_id == 5 and sol.fecha == date(2025, 11, 17) and len(promos) == 12


def test_acepta_bytes_y_texto():
    for cuerpo in (json.dumps(prediccion()).encode(), json.dumps(prediccion())):
        assert _pred(cuerpo)[2] == "ok"


# --- Catálogo de errores E01–E07 (predicción)

@pytest.mark.parametrize("valor", ["T05", "5", "05", "tienda 5", "Tienda-5", 5.0, "NovaMercado Quetzaltenango"])
def test_E01_tienda_con_otro_formato_se_repara(valor):
    sol, obs, est, _ = _pred(prediccion(tienda_id=valor))
    assert sol.tienda_id == 5 and est == "corregido"
    assert _acciones(obs) == [("tienda_id", "reparar")]


def test_E02_familia_escrita_de_otra_forma_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"][2]["familia_id"] = "LÁCTEOS"
    cuerpo["familias"][5]["familia_id"] = "Frutas y Verduras"
    cuerpo["familias"][0]["familia_id"] = "abarrotes "
    sol, obs, est, promos = _pred(cuerpo)
    assert est == "corregido" and set(promos) == set(FAMILIAS)
    assert ("familias[2].familia_id", "reparar") in _acciones(obs)
    assert any("'LÁCTEOS' se interpretó como 'lacteos'" == o.detalle for o in obs)


def test_E03_promocion_como_texto_o_decimal_entero_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"][1]["en_promocion"] = 8.0
    cuerpo["familias"][9]["en_promocion"] = "9"
    _, obs, est, promos = _pred(cuerpo)
    assert est == "corregido" and promos["bebidas"] == 8 and promos["snacks"] == 9


@pytest.mark.parametrize("valor", ["2025-11-17T00:00:00", "17/11/2025", "2025/11/17", "20251117",
                                   "17 de noviembre de 2025", "Nov 17, 2025", "2025-11-17T08:30:00-06:00",
                                   "11/17/2025"])
def test_E04_fecha_en_otro_formato_sin_ambiguedad_se_repara(valor):
    sol, obs, est, _ = _pred(prediccion(fecha=valor))
    assert sol.fecha == date(2025, 11, 17) and est == "corregido", obs


def test_E05_familias_faltantes_se_completan_con_advertencia():
    cuerpo = prediccion()
    cuerpo["familias"] = [f for f in cuerpo["familias"] if f["familia_id"] not in ("bebe", "mascotas")]
    previas = {(5, "bebe"): 3}
    _, obs, est, promos = _pred(cuerpo, promo_previa=lambda t, f: previas.get((t, f)))
    assert est == "advertencia" and set(promos) == set(FAMILIAS)
    assert promos["bebe"] == 3 and promos["mascotas"] == 0  # última promoción conocida, o 0 (D9)
    assert sum(o.regla == "faltan_familias" for o in obs) == 2


def test_E06_familia_repetida_con_valores_distintos_usa_el_lado_barato():
    cuerpo = prediccion()
    cuerpo["familias"].append({"familia_id": "abarrotes", "en_promocion": 3})   # τ alto: el mayor
    cuerpo["familias"].append({"familia_id": "panaderia", "en_promocion": 4})   # τ bajo: el menor
    _, obs, est, promos = _pred(cuerpo)
    assert est == "advertencia" and promos["abarrotes"] == 3 and promos["panaderia"] == 0
    assert len(promos) == 12


def test_familia_repetida_con_el_mismo_valor_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"].append({"familia_id": "abarrotes", "en_promocion": 0})
    assert _pred(cuerpo)[2] == "corregido"


@pytest.mark.parametrize("nombre", ["tienda", "tiendaId", "id_tienda", "Tienda_ID", "store_id"])
def test_E07_campo_renombrado_se_repara(nombre):
    cuerpo = prediccion()
    cuerpo[nombre] = cuerpo.pop("tienda_id")
    sol, obs, est, _ = _pred(cuerpo)
    assert sol.tienda_id == 5 and est == "corregido" and obs[0].campo == nombre


# --- Catálogo E08–E10 (observaciones)

def test_E08_ventas_negativas_no_se_guardan():
    cuerpo = observacion()
    cuerpo["ventas"][5]["ventas"] = -4
    sol, obs = limpiar_observacion(cuerpo, CAT)
    assert estado(obs) == "advertencia" and len(sol.ventas) == 11
    assert "frutas_verduras" not in {v.familia_id for v in sol.ventas}
    assert obs[0].campo == "ventas[5].ventas" and obs[0].regla == "ventas_negativas"


def test_E09_envio_repetido_es_valido_sin_observaciones():
    # la idempotencia la garantiza la base (D6); la limpieza responde igual las dos veces
    a = limpiar_observacion(observacion(), CAT)
    b = limpiar_observacion(observacion(), CAT)
    assert a == b and a[1] == []


@pytest.mark.parametrize("texto,valor", [("1,292", 1292), ("50,0", 50), ("812,0", 812), ("1.234", 1234),
                                         ("1.234,00", 1234), ("1 292", 1292), ("2,000,000", 2000000)])
def test_E10_numero_con_separadores_se_repara(texto, valor):
    cuerpo = observacion()
    cuerpo["ventas"][0]["ventas"] = texto
    sol, obs = limpiar_observacion(cuerpo, CAT)
    assert sol.ventas[0].ventas == valor
    assert [o.accion for o in obs if o.regla == "numero_formato"] == ["reparar"]


@pytest.mark.parametrize("texto", ["812,5", "1.234,56", 12.5, "doce", None, True, [3]])
def test_ventas_no_enteras_o_invalidas_no_se_guardan(texto):
    cuerpo = observacion()
    cuerpo["ventas"][0]["ventas"] = texto
    sol, obs = limpiar_observacion(cuerpo, CAT)
    assert "abarrotes" not in {v.familia_id for v in sol.ventas} and estado(obs) == "advertencia"


# --- Fuera del catálogo: identidad

@pytest.mark.parametrize("valor", [99, 0, "T99", -5, 5.5, True, None, [5], {"id": 5}, "Guatemala", "xyz"])
def test_tienda_inexistente_o_ambigua_se_rechaza(valor):
    with pytest.raises(Rechazo):
        limpiar_prediccion(prediccion(tienda_id=valor), CAT)


def test_tienda_unica_en_su_ciudad_se_acepta_con_advertencia():
    sol, obs, est, _ = _pred(prediccion(tienda_id="Cobán"))
    assert sol.tienda_id == 8 and est == "advertencia"


def test_nombre_de_tienda_con_numero_no_se_confunde_con_el_id():
    # "Zona 10" es la tienda 1, no la 10
    assert _pred(prediccion(tienda_id="NovaMercado Zona 10"))[0].tienda_id == 1


def test_falta_tienda_o_fecha_se_rechaza():
    for campo in ("tienda_id", "fecha"):
        cuerpo = prediccion()
        del cuerpo[campo]
        with pytest.raises(Rechazo, match=f"falta '{campo}'"):
            limpiar_prediccion(cuerpo, CAT)


@pytest.mark.parametrize("valor", ["2025-02-30", "2025-13-01", "mañana", "", 20251117, "17/11", "2024-03-15",
                                   "2027-03-01", "2099-01-01"])
def test_fecha_imposible_o_fuera_de_rango_se_rechaza(valor):
    with pytest.raises(Rechazo):
        limpiar_prediccion(prediccion(fecha=valor), CAT)


def test_fecha_anterior_a_la_apertura_de_la_tienda_se_rechaza():
    with pytest.raises(Rechazo, match="fuera del periodo"):
        limpiar_prediccion(prediccion(tienda_id=10, fecha="2025-03-01"), CAT)


@pytest.mark.parametrize("valor,esperada", [("03/04/2026", date(2026, 4, 3)), ("17/11/25", date(2025, 11, 17))])
def test_fecha_ambigua_se_interpreta_con_advertencia(valor, esperada):
    sol, obs, est, _ = _pred(prediccion(fecha=valor))
    assert sol.fecha == esperada and est == "advertencia" and obs[0].regla == "fecha_ambigua"


def test_tienda_en_dos_campos_con_valores_distintos_se_rechaza():
    with pytest.raises(Rechazo, match="distintos"):
        limpiar_prediccion(prediccion(tienda=4), CAT)
    with pytest.raises(Rechazo, match="distintos"):
        limpiar_prediccion(prediccion(tienda="NovaMercado Cobán"), CAT)  # 5 contra 8


# Campos sinónimos: se comparan los valores ya interpretados (revisión del PR #5)
@pytest.mark.parametrize("extra", [{"tienda": 5}, {"tienda": "5"}, {"tienda": "T05"}])
def test_tienda_en_dos_campos_con_el_mismo_valor_se_repara(extra):
    sol, obs, est, _ = _pred(prediccion(**extra))
    assert sol.tienda_id == 5 and est == "corregido"


def test_fecha_en_dos_campos_con_el_mismo_valor_se_repara():
    sol, obs, est, _ = _pred(prediccion(date="2025-11-17T00:00:00"))
    assert str(sol.fecha) == "2025-11-17" and est == "corregido"


def test_fecha_en_dos_campos_distintos_se_rechaza():
    with pytest.raises(Rechazo, match="distintos"):
        limpiar_prediccion(prediccion(date="2025-11-18"), CAT)


def test_familia_en_dos_campos_equivalentes_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"][2] = {"familia_id": "lacteos", "familia": "LÁCTEOS", "en_promocion": 4}
    _, obs, est, promos = _pred(cuerpo)
    assert promos["lacteos"] == 4 and est == "corregido"


def test_familia_en_dos_campos_distintos_se_excluye():
    cuerpo = prediccion()
    cuerpo["familias"][2] = {"familia_id": "lacteos", "familia": "carnes", "en_promocion": 4}
    _, obs, est, promos = _pred(cuerpo)
    assert est == "advertencia" and any(o.regla == "campo_en_conflicto" for o in obs)
    assert promos["lacteos"] == 0  # no se usó el ítem: lacteos quedó como faltante


def test_promocion_en_dos_campos_equivalentes_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"][1] = {"familia_id": "bebidas", "en_promocion": 8, "promo": "8"}
    assert _pred(cuerpo)[3]["bebidas"] == 8


def test_fecha_despues_del_calendario_se_atiende_con_advertencia():
    sol, obs, est, _ = _pred(prediccion(fecha="2027-01-05"))
    assert str(sol.fecha) == "2027-01-05" and est == "advertencia"
    assert [o.regla for o in obs] == ["fecha_sin_calendario"]


@pytest.mark.parametrize("cuerpo", [b"", b"no es json", b"{'tienda_id': 5}", b"[]", b"[1,2]", b"42", b"null",
                                    "{\"tienda_id\": 5,"])
def test_cuerpo_invalido_se_rechaza(cuerpo):
    with pytest.raises(Rechazo):
        limpiar_prediccion(cuerpo, CAT)


def test_lista_con_una_solicitud_se_repara():
    assert _pred([prediccion()])[2] == "corregido"


def test_cuerpo_latin1_se_repara():
    cuerpo = prediccion()
    cuerpo["familias"][2]["familia_id"] = "Lácteos"
    sol, obs, est, promos = _pred(json.dumps(cuerpo, ensure_ascii=False).encode("latin-1"))
    assert "lacteos" in promos and est == "corregido"


# --- Fuera del catálogo: ítems

@pytest.mark.parametrize("texto", ["LÃ¡cteos", "lácteos​", "Lacteos", "LACTEOS", "lacteos ", "Lácteos"])
def test_familia_con_codificacion_espacios_o_mayusculas_se_repara(texto):
    cuerpo = prediccion()
    cuerpo["familias"][2]["familia_id"] = texto
    _, obs, est, promos = _pred(cuerpo)
    assert est == "corregido" and "lacteos" in promos


@pytest.mark.parametrize("texto,fid", [("lacteo", "lacteos"), ("panaderias", "panaderia"), ("mascota", "mascotas")])
def test_familia_parecida_se_acepta_con_advertencia(texto, fid):
    cuerpo = prediccion()
    cuerpo["familias"] = [{"familia_id": texto, "en_promocion": 2}]
    _, obs, est, promos = _pred(cuerpo)
    assert promos[fid] == 2 and est == "advertencia"


def test_familia_desconocida_se_excluye_y_se_completa_el_resto():
    cuerpo = prediccion()
    cuerpo["familias"].append({"familia_id": "ferreteria", "en_promocion": 1})
    _, obs, est, promos = _pred(cuerpo)
    assert "ferreteria" not in promos and len(promos) == 12 and est == "advertencia"


@pytest.mark.parametrize("valor", [2.5, -1, None, "sí", "", [1], {"x": 1}])
def test_promocion_invalida_se_imputa_con_advertencia(valor):
    cuerpo = prediccion()
    cuerpo["familias"][1]["en_promocion"] = valor
    _, obs, est, promos = _pred(cuerpo, promo_previa=lambda t, f: 6)
    assert promos["bebidas"] == 6 and est == "advertencia"


def test_promocion_ausente_se_imputa():
    cuerpo = prediccion()
    del cuerpo["familias"][1]["en_promocion"]
    _, _, est, promos = _pred(cuerpo)
    assert promos["bebidas"] == 0 and est == "advertencia"


def test_promocion_atipica_se_conserva_con_advertencia():
    # Se conserva el valor real: el modelo lo trata como el máximo, pero el reentrenamiento ve el dato
    cuerpo = prediccion()
    cuerpo["familias"][1]["en_promocion"] = "1,000"
    _, obs, est, promos = _pred(cuerpo)
    assert promos["bebidas"] == 1000 and est == "advertencia"
    assert "el modelo lo trata como 19" in obs[0].detalle


def test_familias_como_objeto_o_lista_de_nombres():
    _, _, est, promos = _pred(prediccion(familias={f: 1 for f in FAMILIAS}))
    assert est == "corregido" and set(promos.values()) == {1}
    _, _, est, promos = _pred(prediccion(familias=list(FAMILIAS)))
    assert est == "advertencia" and len(promos) == 12  # sin promoción: imputada


def test_sin_lista_de_familias_se_pronostican_todas_con_advertencia():
    cuerpo = prediccion()
    del cuerpo["familias"]
    _, _, est, promos = _pred(cuerpo)
    assert est == "advertencia" and len(promos) == 12


def test_campo_desconocido_se_ignora_con_advertencia():
    _, obs, est, _ = _pred(prediccion(origen="pos-v2"))
    assert est == "advertencia" and obs[0].campo == "origen"


def test_campos_de_item_renombrados():
    cuerpo = prediccion(familias=[{"familia": f, "promo": 1} for f in FAMILIAS])
    _, obs, est, promos = _pred(cuerpo)
    assert est == "corregido" and set(promos.values()) == {1}


def test_ventas_atipicas_se_guardan_con_advertencia():
    cuerpo = observacion()
    cuerpo["ventas"][0]["ventas"] = 50000
    sol, obs = limpiar_observacion(cuerpo, CAT)
    assert sol.ventas[0].ventas == 50000 and obs[0].regla == "ventas_atipicas"


def test_observacion_repetida_con_valores_distintos_no_se_guarda():
    cuerpo = observacion()
    cuerpo["ventas"].append({"familia_id": "abarrotes", "ventas": 7})
    sol, obs = limpiar_observacion(cuerpo, CAT)
    assert "abarrotes" not in {v.familia_id for v in sol.ventas}


def test_observacion_sin_ninguna_venta_valida_se_rechaza():
    with pytest.raises(Rechazo, match="ninguna venta válida"):
        limpiar_observacion(observacion(ventas=[{"familia_id": "abarrotes", "ventas": -1}]), CAT)


def test_observacion_de_fecha_del_historico_se_acepta():
    sol, obs = limpiar_observacion(observacion(fecha="2024-03-05"), CAT)
    assert sol.fecha == date(2024, 3, 5) and obs == []


def test_observaciones_tienen_la_forma_del_contrato():
    _, obs, _, _ = _pred(prediccion(tienda_id="T05", fecha="17/11/2025"))
    for o in obs:
        assert set(o.contrato()) == {"campo", "accion", "detalle"} and o.accion in ("reparar", "advertir")
