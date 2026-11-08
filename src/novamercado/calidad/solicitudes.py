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

_CONFLICTO = object()  # dos campos que significan lo mismo con valores distintos


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


def _mapear(obj: dict, permitidos: tuple[str, ...], prefijo: str, reg: Registro,
            identidad: frozenset = frozenset()) -> dict[str, tuple[object, str]]:
    """Campos recibidos -> {canónico: (valor, nombre recibido)}, con observaciones."""
    pares = list(obj.items()) + list(getattr(obj, "repetidas", []))
    out: dict[str, tuple[object, str]] = {}
    for nombre, valor in pares:
        ruta = f"{prefijo}{nombre}"
        if not isinstance(nombre, str):
            reg.advertir(ruta, f"se ignoró el campo {nombre!r}", "campo_desconocido")
            continue
        canon, aproximado = _canonico(nombre, permitidos)
        if canon is None:
            reg.advertir(ruta, f"se ignoró el campo desconocido '{nombre}'", "campo_desconocido")
            continue
        if canon in out:
            previo, nombre_previo = out[canon]
            if previo is _CONFLICTO or previo != valor:
                if canon in identidad:
                    raise Rechazo(f"'{nombre_previo}' y '{nombre}' indican {canon} distintos "
                                  f"({previo!r} y {valor!r})", ruta, "campo_en_conflicto")
                reg.advertir(ruta, f"'{nombre_previo}' y '{nombre}' indican {canon} distintos; "
                             "no se usó ninguno", "campo_en_conflicto")
                out[canon] = (_CONFLICTO, nombre_previo)
            else:
                reg.reparar(ruta, f"'{canon}' venía repetido con el mismo valor", "campo_repetido")
            continue
        if aproximado:
            reg.advertir(ruta, f"el campo '{nombre}' se interpretó como '{canon}'", "campo_renombrado")
        elif nombre != canon:
            reg.reparar(ruta, f"el campo '{nombre}' se interpretó como '{canon}'", "campo_renombrado")
        out[canon] = (valor, nombre)
    return out


# --- identidad: tienda y fecha

PREFIJOS_TIENDA = {"", "t", "tienda", "store", "st", "suc", "sucursal", "id", "no", "num", "numero", "n", "nm",
                   "local", "tda"}


def _tienda(entrada, cat: Catalogo, reg: Registro) -> int:
    if entrada is None:
        raise Rechazo("falta 'tienda_id'", "tienda_id", "falta_identidad")
    valor, nombre = entrada
    ruta = nombre
    if valor is _CONFLICTO:
        raise Rechazo("tienda en conflicto", ruta, "campo_en_conflicto")
    if isinstance(valor, str):
        texto, _ = N.limpiar_texto(valor)
        candidato, nota = None, None
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


def _fecha(entrada, desde, hasta, reg: Registro):
    if entrada is None:
        raise Rechazo("falta 'fecha' (AAAA-MM-DD)", "fecha", "falta_identidad")
    valor, ruta = entrada
    if valor is _CONFLICTO:
        raise Rechazo("fecha en conflicto", ruta, "campo_en_conflicto")
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
    return f


# --- ítems

def _items(entrada, nombre_item: str, reg: Registro) -> list[tuple[str, object]]:
    """Lista de (ruta, ítem). Acepta la lista del contrato, un objeto {familia: valor} o una lista de
    nombres de familia."""
    if entrada is None:
        return []
    valor, nombre = entrada
    if valor is _CONFLICTO or valor is None:
        return []
    if isinstance(valor, dict):
        reg.reparar(nombre, f"'{nombre}' venía como objeto {{familia: valor}}; se leyó como lista", "forma")
        return [(f"{nombre}.{k}", {"familia_id": k, nombre_item: v}) for k, v in valor.items()]
    if not isinstance(valor, list):
        reg.advertir(nombre, f"'{nombre}' no es una lista; se ignoró", "forma")
        return []
    if len(valor) > MAX_ITEMS:
        raise Rechazo(f"'{nombre}' trae {len(valor)} elementos (máximo {MAX_ITEMS})", nombre, "forma")
    return [(f"{nombre}[{i}]", it) for i, it in enumerate(valor)]


def _familia(item, ruta: str, cat: Catalogo, reg: Registro, permitidos) -> tuple[str | None, dict]:
    """Devuelve (familia_id o None si se excluye, campos del ítem)."""
    if isinstance(item, str):
        item = {"familia_id": item}
        reg.reparar(ruta, "el elemento era solo el nombre de la familia", "forma")
    if not isinstance(item, dict):
        reg.advertir(ruta, f"elemento {item!r} no es un objeto; se ignoró", "item_invalido")
        return None, {}
    campos = _mapear(item, permitidos, f"{ruta}.", reg)
    if "familia_id" not in campos or campos["familia_id"][0] in (None, _CONFLICTO):
        reg.advertir(ruta, "elemento sin familia_id; se ignoró", "familia_desconocida")
        return None, campos
    valor, nombre = campos["familia_id"]
    r = f"{ruta}.{nombre}"
    if not isinstance(valor, str):
        reg.advertir(r, f"familia {valor!r} no es un texto; se ignoró", "familia_desconocida")
        return None, campos
    fid = cat.familia_exacta(N.limpiar_texto(valor)[0])
    if fid is not None:
        if valor != fid:
            reg.reparar(r, f"'{valor}' se interpretó como '{fid}'", "familia_formato")
        return fid, campos
    fid = cat.familia_parecida(N.limpiar_texto(valor)[0])
    if fid is not None:
        reg.advertir(r, f"'{valor}' no es una familia del catálogo; se interpretó como '{fid}' por parecido",
                     "familia_aproximada")
        return fid, campos
    reg.advertir(r, f"la familia '{valor}' no existe en el catálogo; se ignoró", "familia_desconocida")
    return None, campos


@dataclass
class _Promo:
    valor: int | None
    ruta: str
    motivo: str | None = None


def _promocion(campos, ruta_item: str, fid: str, cat: Catalogo, reg: Registro) -> _Promo:
    if "en_promocion" not in campos:
        return _Promo(None, f"{ruta_item}.en_promocion", "no viene")
    valor, nombre = campos["en_promocion"]
    ruta = f"{ruta_item}.{nombre}"
    if valor is _CONFLICTO:
        return _Promo(None, ruta, "venía en conflicto")
    n, nota, motivo = N.entero(valor)
    if n is None:
        return _Promo(None, ruta, motivo)
    if n < 0:
        return _Promo(None, ruta, f"{n} es negativo")
    tope = cat.promo_max.get(fid)
    if tope is not None and n > tope:
        reg.advertir(ruta, f"{n} supera el máximo histórico de la familia ({tope}); se usó {tope}",
                     "promocion_atipica")
        return _Promo(tope, ruta)
    if nota:
        reg.reparar(ruta, nota, "numero_formato")
    return _Promo(n, ruta)


def limpiar_prediccion(cuerpo, cat: Catalogo,
                       promo_previa: Callable[[int, str], int | None] = lambda t, f: None
                       ) -> tuple[PrediccionCanonica, list[Observacion]]:
    """Política para POST /v1/prediccion. `promo_previa(tienda, familia)` = última promoción
    registrada (D9), o None."""
    reg = Registro()
    obj = _raiz(leer_cuerpo(cuerpo, reg), reg)
    campos = _mapear(obj, RAIZ_PREDICCION, "", reg, identidad=frozenset({"tienda_id", "fecha"}))
    tienda = _tienda(campos.get("tienda_id"), cat, reg)
    f = _fecha(campos.get("fecha"), max(cat.fecha_min_prediccion, cat.tiendas[tienda].fecha_apertura),
               cat.fecha_max_calendario, reg)
    if "familias" not in campos:
        reg.advertir("familias", "no vino la lista de familias; se pronosticaron todas", "faltan_familias")

    def imputar(fid: str) -> tuple[int, str]:
        previa = promo_previa(tienda, fid)
        if previa is None:
            return 0, "se usó 0 (no hay promociones registradas de esa familia)"
        return int(previa), f"se usó {previa}, la última promoción registrada"

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
            reg.advertir("familias", f"faltaba la familia '{fid}'; se pronosticó con en_promocion: {como}",
                         "faltan_familias")
            familias.append(FamiliaCanonica(familia_id=fid, en_promocion=valor))
    return PrediccionCanonica(tienda_id=tienda, fecha=f, familias=familias), reg.observaciones


def limpiar_observacion(cuerpo, cat: Catalogo) -> tuple[ObservacionCanonica, list[Observacion]]:
    """Política para POST /v1/observaciones. Nunca guarda un valor que no sea una venta entera no
    negativa inequívoca (no inventa datos)."""
    reg = Registro()
    obj = _raiz(leer_cuerpo(cuerpo, reg), reg)
    campos = _mapear(obj, RAIZ_OBSERVACION, "", reg, identidad=frozenset({"tienda_id", "fecha"}))
    tienda = _tienda(campos.get("tienda_id"), cat, reg)
    f = _fecha(campos.get("fecha"), max(cat.fecha_min_datos, cat.tiendas[tienda].fecha_apertura),
               cat.fecha_max_calendario, reg)
    vistos: dict[str, list[tuple[int | None, str]]] = {}
    for ruta, item in _items(campos.get("ventas"), "ventas", reg):
        fid, cs = _familia(item, ruta, cat, reg, ITEM_OBSERVACION)
        if fid is None:
            continue
        if "ventas" not in cs:
            reg.advertir(f"{ruta}.ventas", f"'{fid}' sin ventas; no se guardó", "ventas_invalidas")
            vistos.setdefault(fid, []).append((None, ruta))
            continue
        valor, nombre = cs["ventas"]
        r = f"{ruta}.{nombre}"
        n, nota, motivo = N.entero(valor) if valor is not _CONFLICTO else (None, None, "venía en conflicto")
        if n is None:
            reg.advertir(r, f"ventas de '{fid}' inválidas ({motivo}); no se guardó", "ventas_invalidas")
            n = None
        elif n < 0:
            reg.advertir(r, f"ventas de '{fid}' negativas ({n}, p. ej. devoluciones); no se guardó",
                         "ventas_negativas")
            n = None
        else:
            if nota:
                reg.reparar(r, nota, "numero_formato")
            tope = cat.ventas_max.get(fid)
            if tope and n > FACTOR_ATIPICO * tope:
                reg.advertir(r, f"{n} es más de {FACTOR_ATIPICO} veces el máximo histórico de '{fid}' ({tope}); "
                             "se guardó tal cual", "ventas_atipicas")
        vistos.setdefault(fid, []).append((n, r))

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
