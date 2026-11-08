"""Envía los ejemplos publicados (y algunos casos fuera del catálogo) a la API en ejecución y escribe
las respuestas en evidencia/respuestas_api.md.

Uso:
    python scripts/enviar_ejemplos.py [url_api] [carpeta_datos]
    (por defecto http://localhost:8000 y datos/publicados)

Los ejemplos usan fechas del histórico (2025-11-17): el servicio predice con las ventas anteriores a esa
fecha, así que el envío no altera nada (las observaciones de ejemplo son idénticas al histórico).
"""

import json
import sys
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[1]

# Casos que no están en el catálogo (D8), sobre la solicitud válida publicada.
EXTRA = {
    "X01_tienda_por_ciudad": lambda p: {**p, "tienda_id": "Quetzaltenango"},
    "X02_tienda_inexistente": lambda p: {**p, "tienda_id": 42},
    "X03_fecha_ambigua": lambda p: {**p, "fecha": "03/11/2025"},
    "X04_fecha_imposible": lambda p: {**p, "fecha": "2025-02-30"},
    "X05_familia_parecida_y_desconocida": lambda p: {**p, "familias": [
        {"familia_id": "lacteo", "en_promocion": 1}, {"familia_id": "ferreteria", "en_promocion": 0}]},
    "X06_promocion_invalida": lambda p: {**p, "familias": [{**f, "en_promocion": "muchas"} if i == 0 else f
                                                          for i, f in enumerate(p["familias"])]},
    "X07_campos_sinonimos_y_desconocido": lambda p: {"store_id": "T05", "date": "2025-11-17T06:00:00",
                                                     "productos": p["familias"], "origen": "pos-v2"},
    "X08_cuerpo_no_json": None,
}


def enviar(cliente: httpx.Client, ruta: str, cuerpo) -> httpx.Response:
    contenido = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode()
    return cliente.post(ruta, content=contenido, headers={"content-type": "application/json"})


def main(url: str, datos: Path) -> str:
    out = ["# Respuestas de la API ante solicitudes válidas y defectuosas", "",
           "Generado con `python scripts/enviar_ejemplos.py` contra el producto levantado con Docker.", ""]
    with httpx.Client(base_url=url, timeout=30) as c:
        out += ["## Estado", "", "```json", json.dumps(c.get("/health").json(), indent=2, ensure_ascii=False),
                json.dumps(c.get("/modelo").json(), indent=2, ensure_ascii=False), "```", ""]
        ejemplos = sorted((datos / "ejemplos").rglob("*.json"))
        valida = json.loads((datos / "ejemplos" / "prediccion_valida.json").read_text())
        casos = [(p.stem, json.loads(p.read_bytes())) for p in ejemplos]
        casos += [(n, f(valida) if f else b"tienda=5&fecha=hoy") for n, f in EXTRA.items()]
        for nombre, cuerpo in casos:
            ruta = "/v1/observaciones" if isinstance(cuerpo, dict) and "ventas" in cuerpo else "/v1/prediccion"
            r = enviar(c, ruta, cuerpo)
            cuerpo_txt = cuerpo.decode() if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False)
            out += [f"## {nombre}", "", f"`POST {ruta}` → **{r.status_code}**", "",
                    "<details><summary>Solicitud</summary>", "", "```json", cuerpo_txt, "```", "</details>", "",
                    "```json", json.dumps(r.json(), indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(out)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    datos = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "datos" / "publicados"
    destino = RAIZ / "evidencia" / "respuestas_api.md"
    destino.write_text(main(url, datos), encoding="utf-8")
    print(f"escrito {destino}")
