"""Limpieza de las solicitudes: aplica la política de D7/D8 y devuelve la forma canónica.

Entrada: el cuerpo tal como llegó (bytes, texto o un objeto ya decodificado).
Salida: la solicitud canónica (validada con Pydantic) y sus observaciones de calidad, o `Rechazo`.

Las reglas son por clase de problema, no por ejemplo: un campo de identidad (tienda, fecha) que no
se puede establecer rechaza la solicitud; un campo de un ítem (familia, promoción, ventas) que no se
puede interpretar se imputa o se excluye con advertencia (D7).
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from novamercado.calidad import normalizar as N
from novamercado.calidad.catalogo import Catalogo, _parecido
from novamercado.calidad.esquemas import (
    FamiliaCanonica,
    ObservacionCanonica,
    PrediccionCanonica,
    VentaCanonica,
)
from novamercado.calidad.resultado import Observacion, Rechazo, Registro

MAX_ITEMS = 500
# Una venta mayor a este múltiplo del máximo histórico de su familia se guarda, pero se advierte.
FACTOR_ATIPICO = 3

# Nombres alternativos de los campos, en forma normalizada (normalizar.clave).
ALIAS = {
    "tienda_id": {"tienda", "id_tienda", "tiendaid", "store", "store_id", "storeid", "codigo_tienda",
                  "cod_tienda", "sucursal", "sucursal_id", "id_sucursal", "local"},
    "fecha": {"date", "dia", "fecha_pronostico", "fecha_prediccion", "fecha_venta", "fecha_ventas",
              "fecha_solicitud", "fecha_observacion", "day"},
    "familias": {"familia", "lista_familias", "productos", "items", "lineas", "detalle", "pronosticos"},
    "familia_id": {"familia", "id_familia", "familiaid", "family", "family_id", "categoria", "nombre_familia",
                   "linea", "producto"},
    "en_promocion": {"promocion", "promo", "promos", "promociones", "productos_en_promocion",
                     "en_promo", "enpromocion", "promotion", "on_promotion", "onpromotion"},
    "ventas": {"venta", "unidades", "unidades_vendidas", "cantidad", "vendido", "vendidas", "real",
               "ventas_reales", "sales", "valor", "observaciones", "detalle", "items", "lineas"},
}
RAIZ_PREDICCION = ("tienda_id", "fecha", "familias")
ITEM_PREDICCION = ("familia_id", "en_promocion")
RAIZ_OBSERVACION = ("tienda_id", "fecha", "ventas")
ITEM_OBSERVACION = ("familia_id", "ventas")

class Objeto(dict):
    """dict que recuerda las claves repetidas del JSON (json.loads se queda con la última)."""

    repetidas: list

    def __init__(self, pares=()):
        super().__init__()
        self.repetidas = []
        for k, v in pares:
            if k in self:
                self.repetidas.append((k, v))
            else:
                self[k] = v


def leer_cuerpo(cuerpo, reg: Registro):
    """bytes/texto -> objeto JSON. Rechaza lo que no es JSON (no hay forma única de repararlo)."""
    if isinstance(cuerpo, (bytes, bytearray)):
        try:
            texto = bytes(cuerpo).decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = bytes(cuerpo).decode("latin-1")
            reg.reparar("cuerpo", "el cuerpo no venía en UTF-8; se leyó como Latin-1", "codificacion")
        cuerpo = texto
    if isinstance(cuerpo, str):
        if not cuerpo.strip():
            raise Rechazo("el cuerpo de la solicitud está vacío", "cuerpo", "cuerpo_invalido")
        try:
            return json.loads(cuerpo, object_pairs_hook=Objeto)
        except (json.JSONDecodeError, RecursionError) as e:
            raise Rechazo(f"el cuerpo no es JSON válido ({e.__class__.__name__}: {str(e)[:80]})",
                          "cuerpo", "cuerpo_invalido") from e
    return cuerpo


def _raiz(obj, reg: Registro) -> dict:
    if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
        reg.reparar("cuerpo", "el cuerpo era una lista con una sola solicitud; se usó esa solicitud", "forma")
        return obj[0]
    if not isinstance(obj, dict):
        raise Rechazo("el cuerpo debe ser un objeto JSON con tienda_id, fecha y la lista de familias",
                      "cuerpo", "cuerpo_invalido")
    return obj


def _canonico(nombre: str, permitidos: tuple[str, ...]) -> tuple[str | None, bool]:
    """(campo canónico, aproximado) para un nombre de campo recibido."""
    c = N.clave(nombre)
    for canon in permitidos:
        if c == canon or c in ALIAS[canon] or c.replace("_", "") == canon.replace("_", ""):
            return canon, False
    opciones = {a: canon for canon in permitidos for a in (ALIAS[canon] | {canon})}
    parecido = _parecido(c, opciones)
    return parecido, parecido is not None


Candidatos = list[tuple[object, str]]  # (valor, ruta del campo recibido)


def _mapear(obj: dict, permitidos: tuple[str, ...], prefijo: str, reg: Registro) -> dict[str, Candidatos]:
    """Campos recibidos -> {canónico: [(valor, ruta), ...]}. Varios candidatos = el mismo dato vino en
    campos sinónimos (o repetido); se resuelven después comparando los valores ya interpretados."""
    pares = list(obj.items()) + list(getattr(obj, "repetidas", []))
    out: dict[str, Candidatos] = {}
    for nombre, valor in pares:
        ruta = f"{prefijo}{nombre}"
        canon, aproximado = _canonico(nombre, permitidos) if isinstance(nombre, str) else (None, False)
        if canon is None:
            reg.advertir(ruta, f"se ignoró el campo desconocido '{nombre}'", "campo_desconocido")
            continue
        if aproximado:
            reg.advertir(ruta, f"el campo '{nombre}' se interpretó como '{canon}'", "campo_renombrado")
        elif nombre != canon:
            reg.reparar(ruta, f"el campo '{nombre}' se interpretó como '{canon}'", "campo_renombrado")
        out.setdefault(canon, []).append((valor, ruta))
    return out


_INVALIDO = object()


def _resolver(candidatos: Candidatos, interpretar, reg: Registro, canon: str, identidad: bool,
              clave_igualdad=lambda v: v):
    """Interpreta cada candidato por separado y compara los valores interpretados (D8).

    Un solo candidato: su interpretación. Varios que coinciden: se repara. Varios distintos (o alguno
    que no se puede interpretar): se rechaza si es de identidad; si es de un ítem se advierte y se
    devuelve None (como si no hubiera venido).
    """
    if len(candidatos) == 1:
        return interpretar(*candidatos[0], reg)
    resultados = []
    for valor, ruta in candidatos:
        sub = Registro()
        try:
            r = interpretar(valor, ruta, sub)
        except Rechazo:
            r = _INVALIDO
        resultados.append((r, valor, ruta, sub))
    claves = [None if r is _INVALIDO or r is None else clave_igualdad(r) for r, *_ in resultados]
    if None not in claves and all(c == claves[0] for c in claves):
        primero = resultados[0]
        reg.observaciones.extend(primero[3].observaciones)
        for *_, ruta, _ in resultados[1:]:
            reg.reparar(ruta, f"'{ruta}' repetía {canon} con el mismo valor que '{primero[2]}'", "campo_repetido")
        return primero[0]
    detalle = ", ".join(f"'{ruta}': {valor!r}" for _, valor, ruta, _ in resultados)
    if identidad:
        raise Rechazo(f"campos con {canon} distintos ({detalle})", resultados[0][2], "campo_en_conflicto")
    reg.advertir(resultados[-1][2], f"campos con {canon} distintos ({detalle}); no se usó ninguno",
                 "campo_en_conflicto")
    return None


# --- identidad: tienda y fecha

PREFIJOS_TIENDA = {"", "t", "tienda", "store", "st", "suc", "sucursal", "id", "no", "num", "numero", "n", "nm",
                   "local", "tda"}


def _tienda_valor(valor, ruta: str, cat: Catalogo, reg: Registro) -> int:
    if isinstance(valor, str):
        texto, _ = N.limpiar_texto(valor)
        candidato = None
        if texto.isdigit():
            candidato = int(texto)
        else:
            por_nombre, aprox = cat.tienda_por_nombre(texto)
            c = N.clave(texto)
            ciudad = cat.tiendas_en_ciudad(texto)
            if por_nombre is not None and not aprox:
                candidato = por_nombre
            elif (m := re.fullmatch(r"([a-z_]*?)_?0*(\d+)", c)) and m.group(1).strip("_") in PREFIJOS_TIENDA:
                candidato = int(m.group(2))
            elif len(ciudad) == 1:
                reg.advertir(ruta, f"'{valor}' se interpretó como la tienda {ciudad[0]}, la única en esa ciudad",
                             "tienda_aproximada")
                return ciudad[0]
            elif len(ciudad) > 1:
                raise Rechazo(f"'{valor}' es ambiguo: hay {len(ciudad)} tiendas en esa ciudad "
                              f"({', '.join(map(str, ciudad))})", ruta, "tienda_ambigua")
            elif por_nombre is not None:
                reg.advertir(ruta, f"'{valor}' se interpretó como la tienda {por_nombre} "
                             f"({cat.tiendas[por_nombre].nombre}) por parecido", "tienda_aproximada")
                return por_nombre
        if candidato is None:
            raise Rechazo(f"no se reconoce la tienda {valor!r}", ruta, "tienda_desconocida")
        nota = f"'{valor}' se interpretó como la tienda {candidato}"
    else:
        candidato, nota, motivo = N.entero(valor)
        if candidato is None:
            raise Rechazo(f"tienda_id inválido: {motivo}", ruta, "tienda_desconocida")
    if candidato not in cat.tiendas:
        raise Rechazo(f"la tienda {candidato} no existe en el catálogo (tiendas "
                      f"{min(cat.tiendas)} a {max(cat.tiendas)})", ruta, "tienda_desconocida")
    if nota:
        reg.reparar(ruta, nota, "tienda_formato")
    return candidato


def _tienda(cands: Candidatos | None, cat: Catalogo, reg: Registro) -> int:
    if not cands:
        raise Rechazo("falta 'tienda_id'", "tienda_id", "falta_identidad")
    return _resolver(cands, lambda v, r, g: _tienda_valor(v, r, cat, g), reg, "tienda_id", identidad=True)


def _fecha_valor(valor, ruta: str, desde, hasta_calendario, hasta, reg: Registro):
    f, nota, supuesto, motivo = N.fecha(valor)
    if f is None:
        raise Rechazo(f"fecha inválida: {motivo}", ruta, "fecha_invalida")
    if not desde <= f <= hasta:
        raise Rechazo(f"la fecha {f.isoformat()} está fuera del periodo que el servicio puede atender "
                      f"({desde.isoformat()} a {hasta.isoformat()})", ruta, "fecha_fuera_de_rango")
    if supuesto:
        reg.advertir(ruta, supuesto, "fecha_ambigua")
    elif nota:
        reg.reparar(ruta, nota, "fecha_formato")
    if hasta_calendario is not None and f > hasta_calendario:
        reg.advertir(ruta, f"{f.isoformat()} es posterior al calendario de feriados "
                     f"({hasta_calendario.isoformat()}); se asumió un día sin feriados ni fechas especiales",
                     "fecha_sin_calendario")
    return f


def _fecha(cands: Candidatos | None, desde, hasta_calendario, hasta, reg: Registro):
    if not cands:
        raise Rechazo("falta 'fecha' (AAAA-MM-DD)", "fecha", "falta_identidad")
    return _resolver(cands, lambda v, r, g: _fecha_valor(v, r, desde, hasta_calendario, hasta, g), reg,
                     "fecha", identidad=True)


# --- ítems

def _items(cands: Candidatos | None, nombre_item: str, reg: Registro) -> list[tuple[str, object]]:
    """Lista de (ruta, ítem). Acepta la lista del contrato, un objeto {familia: valor} o una lista de
    nombres de familia. Si la lista vino en dos campos sinónimos, se usan los elementos de ambos (las
    familias repetidas se resuelven después)."""
    items = []
    for valor, nombre in cands or []:
        if valor is None:
            continue
        if isinstance(valor, dict):
            reg.reparar(nombre, f"'{nombre}' venía como objeto {{familia: valor}}; se leyó como lista", "forma")
            items += [(f"{nombre}.{k}", {"familia_id": k, nombre_item: v}) for k, v in valor.items()]
        elif isinstance(valor, list):
            items += [(f"{nombre}[{i}]", it) for i, it in enumerate(valor)]
        else:
            reg.advertir(nombre, f"'{nombre}' no es una lista; se ignoró", "forma")
    if len(items) > MAX_ITEMS:
        raise Rechazo(f"la solicitud trae {len(items)} elementos (máximo {MAX_ITEMS})", "familias", "forma")
    return items


def _familia_valor(valor, ruta: str, cat: Catalogo, reg: Registro) -> str | None:
    if not isinstance(valor, str):
        reg.advertir(ruta, f"familia {valor!r} no es un texto; se ignoró", "familia_desconocida")
        return None
    texto = N.limpiar_texto(valor)[0]
    fid = cat.familia_exacta(texto)
    if fid is not None:
        if valor != fid:
            reg.reparar(ruta, f"'{valor}' se interpretó como '{fid}'", "familia_formato")
        return fid
    fid = cat.familia_parecida(texto)
    if fid is not None:
        reg.advertir(ruta, f"'{valor}' no es una familia del catálogo; se interpretó como '{fid}' por parecido",
                     "familia_aproximada")
        return fid
    reg.advertir(ruta, f"la familia '{valor}' no existe en el catálogo; se ignoró", "familia_desconocida")
    return None


def _familia(item, ruta: str, cat: Catalogo, reg: Registro, permitidos) -> tuple[str | None, dict]:
    """Devuelve (familia_id o None si se excluye, candidatos de los campos del ítem)."""
    if isinstance(item, str):
        item = {"familia_id": item}
        reg.reparar(ruta, "el elemento era solo el nombre de la familia", "forma")
    if not isinstance(item, dict):
        reg.advertir(ruta, f"elemento {item!r} no es un objeto; se ignoró", "item_invalido")
        return None, {}
    campos = _mapear(item, permitidos, f"{ruta}.", reg)
    if not campos.get("familia_id"):
        reg.advertir(ruta, "elemento sin familia_id; se ignoró", "familia_desconocida")
        return None, campos
    fid = _resolver(campos["familia_id"], lambda v, r, g: _familia_valor(v, r, cat, g), reg, "familia_id",
                    identidad=False)
    return fid, campos


@dataclass
class _Promo:
    valor: int | None
    ruta: str
    motivo: str | None = None


def _promo_valor(valor, ruta: str, fid: str, cat: Catalogo, reg: Registro) -> _Promo:
    n, nota, motivo = N.entero(valor)
    if n is None:
        return _Promo(None, ruta, motivo)
    if n < 0:
        return _Promo(None, ruta, f"{n} es negativo")
    tope = cat.promo_max.get(fid)
    if tope is not None and n > tope:
        # Se conserva el valor: el modelo lo trata como el máximo visto, pero el dato real queda
        # registrado para el reentrenamiento (revisión del PR #5).
        reg.advertir(ruta, f"{n} supera el máximo histórico de la familia ({tope}); el modelo lo trata como "
                     f"{tope}", "promocion_atipica")
    elif nota:
        reg.reparar(ruta, nota, "numero_formato")
    return _Promo(n, ruta)


def _promocion(campos, ruta_item: str, fid: str, cat: Catalogo, reg: Registro) -> _Promo:
    cands = campos.get("en_promocion")
    if not cands:
        return _Promo(None, f"{ruta_item}.en_promocion", "no viene")
    p = _resolver(cands, lambda v, r, g: _promo_valor(v, r, fid, cat, g), reg, "en_promocion", identidad=False,
                  clave_igualdad=lambda x: x.valor)
    if p is None:
        return _Promo(None, cands[-1][1], "venía en campos con valores distintos")
    return p


def _limites(cat: Catalogo, tienda: int, desde):
    """(desde, último día con calendario, último día aceptable) para una tienda (D12)."""
    return max(desde, cat.tiendas[tienda].fecha_apertura), cat.fecha_max_calendario, cat.fecha_max_aceptada


def limpiar_prediccion(cuerpo, cat: Catalogo,
                       promo_previa: Callable[[int, str, object], int | None] = lambda t, f, d: None
                       ) -> tuple[PrediccionCanonica, list[Observacion]]:
    """Política para POST /v1/prediccion. `promo_previa(tienda, familia, fecha)` = última promoción
    conocida hasta esa fecha (D9), o None."""
    reg = Registro()
    obj = _raiz(leer_cuerpo(cuerpo, reg), reg)
    campos = _mapear(obj, RAIZ_PREDICCION, "", reg)
    tienda = _tienda(campos.get("tienda_id"), cat, reg)
    f = _fecha(campos.get("fecha"), *_limites(cat, tienda, cat.fecha_min_prediccion), reg)
    if "familias" not in campos:
        reg.advertir("familias", "no vino la lista de familias; se pronosticaron todas", "faltan_familias")

    def imputar(fid: str) -> tuple[int, str]:
        previa = promo_previa(tienda, fid, f)
        if previa is None:
            return 0, "se usó 0 porque no hay promociones conocidas de esa familia"
        return int(previa), f"se usó {previa}, la última promoción conocida de la tienda"

    vistos: dict[str, list[_Promo]] = {}
    for ruta, item in _items(campos.get("familias"), "en_promocion", reg):
        fid, cs = _familia(item, ruta, cat, reg, ITEM_PREDICCION)
        if fid is not None:
            vistos.setdefault(fid, []).append(_promocion(cs, ruta, fid, cat, reg))

    familias = []
    for fid, promos in vistos.items():
        validas = sorted({p.valor for p in promos if p.valor is not None})
        if len(promos) > 1:
            if len(validas) > 1:
                elegido = max(validas) if cat.tau.get(fid, 0.5) >= 0.5 else min(validas)
                lado = "faltar" if cat.tau.get(fid, 0.5) >= 0.5 else "sobrar"
                reg.advertir(promos[-1].ruta, f"'{fid}' venía repetida con en_promocion {validas}; se usó "
                             f"{elegido} (en esta familia cuesta más {lado})", "familia_repetida")
                familias.append(FamiliaCanonica(familia_id=fid, en_promocion=elegido))
                continue
            reg.reparar(promos[-1].ruta, f"'{fid}' venía repetida con el mismo valor; se usó una vez",
                        "familia_repetida")
        if validas:
            familias.append(FamiliaCanonica(familia_id=fid, en_promocion=validas[0]))
        else:
            valor, como = imputar(fid)
            p = promos[0]
            reg.advertir(p.ruta, f"en_promocion de '{fid}' inválido ({p.motivo}); {como}", "promocion_imputada")
            familias.append(FamiliaCanonica(familia_id=fid, en_promocion=valor))
    for fid in cat.familias:
        if fid not in vistos:
            valor, como = imputar(fid)
            reg.advertir("familias", f"faltaba la familia '{fid}'; se pronosticó y para en_promocion {como}",
                         "faltan_familias")
            familias.append(FamiliaCanonica(familia_id=fid, en_promocion=valor))
    return PrediccionCanonica(tienda_id=tienda, fecha=f, familias=familias), reg.observaciones


def _ventas_valor(valor, ruta: str, fid: str, cat: Catalogo, reg: Registro) -> int | None:
    n, nota, motivo = N.entero(valor)
    if n is None:
        reg.advertir(ruta, f"ventas de '{fid}' inválidas ({motivo}); no se guardó", "ventas_invalidas")
        return None
    if n < 0:
        reg.advertir(ruta, f"ventas de '{fid}' negativas ({n}, p. ej. devoluciones); no se guardó",
                     "ventas_negativas")
        return None
    if nota:
        reg.reparar(ruta, nota, "numero_formato")
    tope = cat.ventas_max.get(fid)
    if tope and n > FACTOR_ATIPICO * tope:
        reg.advertir(ruta, f"{n} es más de {FACTOR_ATIPICO} veces el máximo histórico de '{fid}' ({tope}); "
                     "se guardó tal cual", "ventas_atipicas")
    return n


def limpiar_observacion(cuerpo, cat: Catalogo) -> tuple[ObservacionCanonica, list[Observacion]]:
    """Política para POST /v1/observaciones. Nunca guarda un valor que no sea una venta entera no
    negativa inequívoca (no inventa datos)."""
    reg = Registro()
    obj = _raiz(leer_cuerpo(cuerpo, reg), reg)
    campos = _mapear(obj, RAIZ_OBSERVACION, "", reg)
    tienda = _tienda(campos.get("tienda_id"), cat, reg)
    desde, _, hasta = _limites(cat, tienda, cat.fecha_min_datos)
    f = _fecha(campos.get("fecha"), desde, None, hasta, reg)
    vistos: dict[str, list[tuple[int | None, str]]] = {}
    for ruta, item in _items(campos.get("ventas"), "ventas", reg):
        fid, cs = _familia(item, ruta, cat, reg, ITEM_OBSERVACION)
        if fid is None:
            continue
        cands = cs.get("ventas")
        if not cands:
            reg.advertir(f"{ruta}.ventas", f"'{fid}' sin ventas; no se guardó", "ventas_invalidas")
            vistos.setdefault(fid, []).append((None, ruta))
            continue
        n = _resolver(cands, lambda v, r, g, fid=fid: _ventas_valor(v, r, fid, cat, g), reg, "ventas",
                      identidad=False)
        vistos.setdefault(fid, []).append((n, cands[-1][1]))

    ventas = []
    for fid, valores in vistos.items():
        distintos = sorted({n for n, _ in valores if n is not None})
        if len(valores) > 1 and len(distintos) > 1:
            reg.advertir(valores[-1][1], f"'{fid}' venía repetida con ventas distintas {distintos}; no se guardó",
                         "familia_repetida")
            continue
        if len(valores) > 1 and distintos:
            reg.reparar(valores[-1][1], f"'{fid}' venía repetida con el mismo valor; se guardó una vez",
                        "familia_repetida")
        if distintos:
            ventas.append(VentaCanonica(familia_id=fid, ventas=distintos[0]))
    if not ventas:
        detalle = "; ".join(o.detalle for o in reg.observaciones if o.accion == "advertir") or "no vino ninguna"
        raise Rechazo(f"no hay ninguna venta válida para guardar ({detalle})", "ventas", "sin_datos_validos")
    return ObservacionCanonica(tienda_id=tienda, fecha=f, ventas=ventas), reg.observaciones
