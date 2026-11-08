"""Funciones puras de normalización: texto, nombres de campos, números y fechas.

Cada función de interpretación devuelve (valor, nota, ambiguo):
- valor None = no se pudo interpretar;
- nota = descripción de la transformación si el valor cambió de forma (para `reparar`);
- ambiguo = True si se eligió entre varias lecturas posibles (para `advertir`).
"""

import math
import re
import unicodedata
from datetime import date

INVISIBLES = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def limpiar_texto(s: str) -> tuple[str, bool]:
    """Quita espacios sobrantes, caracteres invisibles y corrige mojibake (UTF-8 leído como
    Latin-1, p. ej. 'LÃ¡cteos'). Devuelve (texto, cambió)."""
    original = s
    s = s.translate(INVISIBLES).replace(" ", " ")
    if any(c in s for c in "ÃÂ"):
        try:
            s = s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    s = unicodedata.normalize("NFC", " ".join(s.split()))
    return s, s != original


def clave(s: str) -> str:
    """Forma comparable: sin tildes, minúsculas, camelCase separado y cualquier separador como '_'.
    'Frutas y Verduras' -> 'frutas_y_verduras'; 'tiendaId' -> 'tienda_id'; 'LÁCTEOS ' -> 'lacteos'."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def es_bool(v) -> bool:
    return isinstance(v, bool)


# --- Enteros

_NUMERO = re.compile(r"^[+-]?\d+([.,]\d+)*$")


def _leer_numero(s: str) -> list[float]:
    """Lecturas posibles de un número escrito con separadores (D11).

    Un separador seguido de exactamente 3 dígitos es de miles; seguido de 1 o 2 dígitos, decimal.
    Con dos tipos de separador, el último es el decimal ('1.234,50' = 1234.50).
    """
    s = s.replace(" ", "").replace("_", "")
    if not _NUMERO.match(s):
        return []
    signo = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    seps = [c for c in s if c in ".,"]
    if not seps:
        return [signo * float(s)]
    if len(set(seps)) == 2:
        decimal = s[max(s.rfind("."), s.rfind(","))]
        miles = "," if decimal == "." else "."
        entera, _, frac = s.partition(decimal)
        grupos = entera.split(miles)
        if any(len(g) != 3 for g in grupos[1:]) or frac.count(miles) or frac.count(decimal):
            return []
        return [signo * float("".join(grupos) + "." + frac)]
    sep = seps[0]
    grupos = s.split(sep)
    if len(grupos) > 2:  # varios separadores iguales: solo pueden ser de miles
        return [signo * float("".join(grupos))] if all(len(g) == 3 for g in grupos[1:]) else []
    entera, frac = grupos
    if len(frac) == 3:
        return [signo * float(entera + frac)]       # miles
    return [signo * float(entera + "." + frac)]     # decimal


def entero(v) -> tuple[int | None, str | None, str | None]:
    """Interpreta un entero. Devuelve (valor, nota_de_reparación, motivo_si_no_se_pudo).

    5 -> 5; 5.0 / "5" / "5,0" / "1,234" -> se repara; 2.5 / "abc" / True / None -> no se puede.
    """
    if v is None:
        return None, None, "no viene"
    if es_bool(v):
        return None, None, f"{v!r} no es un número"
    if isinstance(v, int):
        return v, None, None
    if isinstance(v, float):
        if not math.isfinite(v):
            return None, None, f"{v!r} no es un número válido"
        if v.is_integer():
            return int(v), f"{v!r} se interpretó como {int(v)}", None
        return None, None, f"{v!r} no es un número entero"
    if isinstance(v, str):
        texto, _ = limpiar_texto(v)
        lecturas = _leer_numero(texto)
        if not lecturas:
            return None, None, f"{v!r} no es un número"
        x = lecturas[0]
        if not x.is_integer():
            return None, None, f"{v!r} no es un número entero"
        return int(x), f"{v!r} se interpretó como {int(x)}", None
    return None, None, f"{type(v).__name__} no es un número"


# --- Fechas

MESES = {
    "ene": 1, "enero": 1, "jan": 1, "january": 1, "feb": 2, "febrero": 2, "february": 2,
    "mar": 3, "marzo": 3, "march": 3, "abr": 4, "abril": 4, "apr": 4, "april": 4,
    "may": 5, "mayo": 5, "jun": 6, "junio": 6, "june": 6, "jul": 7, "julio": 7, "july": 7,
    "ago": 8, "agosto": 8, "aug": 8, "august": 8, "sep": 9, "sept": 9, "septiembre": 9,
    "setiembre": 9, "september": 9, "oct": 10, "octubre": 10, "october": 10,
    "nov": 11, "noviembre": 11, "november": 11, "dic": 12, "diciembre": 12, "dec": 12, "december": 12,
}


def _crear(a: int, m: int, d: int) -> date | None:
    try:
        return date(a, m, d)
    except ValueError:
        return None


def fecha(v) -> tuple[date | None, str | None, str | None, str | None]:
    """Interpreta una fecha sin usar el reloj del sistema.

    Devuelve (fecha, nota_reparación, nota_supuesto, motivo_si_no_se_pudo). `nota_supuesto` no es
    None cuando hubo que elegir entre lecturas (día/mes ambiguo o año de dos dígitos).
    """
    if v is None:
        return None, None, None, "no viene"
    if not isinstance(v, str):
        return None, None, None, f"{v!r} no es una fecha en texto AAAA-MM-DD"
    s, _ = limpiar_texto(v)
    s_original = v

    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s):
        f = _crear(*map(int, m.groups()))
        if f is None:
            return None, None, None, f"{s_original!r} no es una fecha válida"
        return f, (None if s == v else f"{s_original!r} se interpretó como {f.isoformat()}"), None, None

    def reparada(f, como=None):
        return f, f"{s_original!r} se interpretó como {f.isoformat()}" + (f" ({como})" if como else ""), None, None

    # Fecha y hora ISO (con o sin zona): se usa la fecha
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})[T ]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?", s):
        f = _crear(*map(int, m.groups()[:3]))
        return reparada(f) if f else (None, None, None, f"{s_original!r} no es una fecha válida")
    # Año primero: 2025/11/17, 2025.11.17, 2025-1-7, 20251117
    if m := re.fullmatch(r"(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})", s) or re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s):
        f = _crear(*map(int, m.groups()))
        return reparada(f) if f else (None, None, None, f"{s_original!r} no es una fecha válida")
    # Día y mes con números: 17/11/2025, 17-11-25, 03.04.2026
    if m := re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})", s):
        a_txt = m.group(3)
        a = int(a_txt) + (2000 if len(a_txt) == 2 else 0)
        x, y = int(m.group(1)), int(m.group(2))
        dia_mes, mes_dia = _crear(a, y, x), _crear(a, x, y)
        supuestos = []
        if len(a_txt) == 2:
            supuestos.append(f"año {a_txt} como {a}")
        if dia_mes and mes_dia and dia_mes != mes_dia:
            supuestos.append("día/mes (convención de Guatemala); también podía ser mes/día")
            f = dia_mes
        elif dia_mes:
            f = dia_mes
        elif mes_dia:
            f = mes_dia
            if not supuestos:
                return reparada(f, "mes/día: el segundo número no puede ser mes")
        else:
            return None, None, None, f"{s_original!r} no es una fecha válida"
        if supuestos:
            return f, None, f"{s_original!r} se interpretó como {f.isoformat()} ({'; '.join(supuestos)})", None
        return reparada(f)
    # Con nombre de mes: "17 nov 2025", "17 de noviembre de 2025", "Nov 17, 2025"
    palabras = re.findall(r"[a-záéíóúñ]+|\d+", clave(s).replace("_", " ") if s else "")
    nums = [int(p) for p in palabras if p.isdigit()]
    meses = [MESES[p] for p in palabras if p in MESES]
    if len(meses) == 1 and len(nums) == 2:
        anio = next((n for n in nums if n >= 1000), None)
        dia = next((n for n in nums if n < 1000), None)
        f = _crear(anio, meses[0], dia) if anio and dia else None
        if f:
            return reparada(f)
    return None, None, None, f"{s_original!r} no es una fecha reconocible (se espera AAAA-MM-DD)"
