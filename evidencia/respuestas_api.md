# Respuestas de la API ante solicitudes válidas y defectuosas

Generado con `python scripts/enviar_ejemplos.py` contra el producto levantado con Docker.

## Estado

```json
{
  "estado": "ok",
  "dependencias": {
    "db": "ok",
    "mlflow": "ok",
    "airflow": "ok"
  },
  "version_modelo": "5",
  "origen_modelo": "mlflow"
}
{
  "nombre": "novamercado-ventas",
  "alias": "champion",
  "version": "5",
  "origen": "mlflow",
  "fecha_corte": "2026-04-24"
}
```

## E01_tienda_texto

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": "T05", "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "tienda_id",
        "accion": "reparar",
        "detalle": "'T05' se interpretó como la tienda 5"
      }
    ]
  }
}
```

## E02_familia_otra_forma

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "Frutas y Verduras", "en_promocion": 0}, {"familia_id": "LÁCTEOS", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "familias[5].familia_id",
        "accion": "reparar",
        "detalle": "'Frutas y Verduras' se interpretó como 'frutas_verduras'"
      },
      {
        "campo": "familias[6].familia_id",
        "accion": "reparar",
        "detalle": "'LÁCTEOS' se interpretó como 'lacteos'"
      }
    ]
  }
}
```

## E03_promocion_texto

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8.0}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": "9"}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "familias[2].en_promocion",
        "accion": "reparar",
        "detalle": "8.0 se interpretó como 8"
      },
      {
        "campo": "familias[11].en_promocion",
        "accion": "reparar",
        "detalle": "'9' se interpretó como 9"
      }
    ]
  }
}
```

## E04_fecha_formato

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "17/11/2025", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "fecha",
        "accion": "reparar",
        "detalle": "'17/11/2025' se interpretó como 2025-11-17"
      }
    ]
  }
}
```

## E05_faltan_familias

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'bebe'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'mascotas'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      }
    ]
  }
}
```

## E06_familia_repetida

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}, {"familia_id": "abarrotes", "en_promocion": 3}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1136.3,
      "cantidad_sugerida": 1387
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[12].en_promocion",
        "accion": "advertir",
        "detalle": "'abarrotes' venía repetida con en_promocion [0, 3]; se usó 3 (en esta familia cuesta más faltar)"
      }
    ]
  }
}
```

## E07_campo_renombrado

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}], "tienda": 5}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "tienda",
        "accion": "reparar",
        "detalle": "el campo 'tienda' se interpretó como 'tienda_id'"
      }
    ]
  }
}
```

## E08_ventas_negativas

`POST /v1/observaciones` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "ventas": [{"familia_id": "abarrotes", "ventas": 994}, {"familia_id": "bebe", "ventas": 50}, {"familia_id": "bebidas", "ventas": 1292}, {"familia_id": "carnes", "ventas": 182}, {"familia_id": "cuidado_personal", "ventas": 118}, {"familia_id": "frutas_verduras", "ventas": -4}, {"familia_id": "lacteos", "ventas": 358}, {"familia_id": "licores", "ventas": 85}, {"familia_id": "limpieza", "ventas": 202}, {"familia_id": "mascotas", "ventas": 63}, {"familia_id": "panaderia", "ventas": 213}, {"familia_id": "snacks", "ventas": 386}]}
```
</details>

```json
{
  "registros_guardados": 0,
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "ventas[5].ventas",
        "accion": "advertir",
        "detalle": "ventas de 'frutas_verduras' negativas (-4, p. ej. devoluciones); no se guardó"
      }
    ]
  }
}
```

## E09_envio_repetido

`POST /v1/observaciones` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "ventas": [{"familia_id": "abarrotes", "ventas": 994}, {"familia_id": "bebe", "ventas": 50}, {"familia_id": "bebidas", "ventas": 1292}, {"familia_id": "carnes", "ventas": 182}, {"familia_id": "cuidado_personal", "ventas": 118}, {"familia_id": "frutas_verduras", "ventas": 410}, {"familia_id": "lacteos", "ventas": 358}, {"familia_id": "licores", "ventas": 85}, {"familia_id": "limpieza", "ventas": 202}, {"familia_id": "mascotas", "ventas": 63}, {"familia_id": "panaderia", "ventas": 213}, {"familia_id": "snacks", "ventas": 386}]}
```
</details>

```json
{
  "registros_guardados": 0,
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

## E10_numero_formato

`POST /v1/observaciones` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "ventas": [{"familia_id": "abarrotes", "ventas": 994}, {"familia_id": "bebe", "ventas": "50,0"}, {"familia_id": "bebidas", "ventas": "1,292"}, {"familia_id": "carnes", "ventas": 182}, {"familia_id": "cuidado_personal", "ventas": 118}, {"familia_id": "frutas_verduras", "ventas": 410}, {"familia_id": "lacteos", "ventas": 358}, {"familia_id": "licores", "ventas": 85}, {"familia_id": "limpieza", "ventas": 202}, {"familia_id": "mascotas", "ventas": 63}, {"familia_id": "panaderia", "ventas": 213}, {"familia_id": "snacks", "ventas": 386}]}
```
</details>

```json
{
  "registros_guardados": 0,
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "ventas[1].ventas",
        "accion": "reparar",
        "detalle": "'50,0' se interpretó como 50"
      },
      {
        "campo": "ventas[2].ventas",
        "accion": "reparar",
        "detalle": "'1,292' se interpretó como 1292"
      }
    ]
  }
}
```

## observacion_valida

`POST /v1/observaciones` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "ventas": [{"familia_id": "abarrotes", "ventas": 994}, {"familia_id": "bebe", "ventas": 50}, {"familia_id": "bebidas", "ventas": 1292}, {"familia_id": "carnes", "ventas": 182}, {"familia_id": "cuidado_personal", "ventas": 118}, {"familia_id": "frutas_verduras", "ventas": 410}, {"familia_id": "lacteos", "ventas": 358}, {"familia_id": "licores", "ventas": 85}, {"familia_id": "limpieza", "ventas": 202}, {"familia_id": "mascotas", "ventas": 63}, {"familia_id": "panaderia", "ventas": 213}, {"familia_id": "snacks", "ventas": 386}]}
```
</details>

```json
{
  "registros_guardados": 0,
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

## prediccion_valida

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

## X01_tienda_por_ciudad

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": "Quetzaltenango", "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "tienda_id",
        "accion": "advertir",
        "detalle": "'Quetzaltenango' se interpretó como la tienda 5, la única en esa ciudad"
      }
    ]
  }
}
```

## X02_tienda_inexistente

`POST /v1/prediccion` → **422**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 42, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "detail": "la tienda 42 no existe en el catálogo (tiendas 1 a 10)"
}
```

## X03_fecha_ambigua

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "03/11/2025", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-03",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 941.5,
      "cantidad_sugerida": 1149
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 61.0,
      "cantidad_sugerida": 79
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 969.6,
      "cantidad_sugerida": 1251
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 230.3,
      "cantidad_sugerida": 208
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 142.0,
      "cantidad_sugerida": 192
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 354.8,
      "cantidad_sugerida": 320
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 443.9,
      "cantidad_sugerida": 427
    },
    {
      "familia_id": "licores",
      "venta_esperada": 86.1,
      "cantidad_sugerida": 133
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 187.0,
      "cantidad_sugerida": 249
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 42.6,
      "cantidad_sugerida": 55
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 230.7,
      "cantidad_sugerida": 197
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 341.3,
      "cantidad_sugerida": 413
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "fecha",
        "accion": "advertir",
        "detalle": "'03/11/2025' se interpretó como 2025-11-03 (día/mes (convención de Guatemala); también podía ser mes/día)"
      }
    ]
  }
}
```

## X04_fecha_imposible

`POST /v1/prediccion` → **422**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-02-30", "familias": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "detail": "fecha inválida: '2025-02-30' no es una fecha válida"
}
```

## X05_familia_parecida_y_desconocida

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "lacteo", "en_promocion": 1}, {"familia_id": "ferreteria", "en_promocion": 0}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "lacteos",
      "venta_esperada": 479.1,
      "cantidad_sugerida": 460
    },
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[0].familia_id",
        "accion": "advertir",
        "detalle": "'lacteo' no es una familia del catálogo; se interpretó como 'lacteos' por parecido"
      },
      {
        "campo": "familias[1].familia_id",
        "accion": "advertir",
        "detalle": "la familia 'ferreteria' no existe en el catálogo; se ignoró"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'abarrotes'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'bebe'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'bebidas'; se pronosticó y para en_promocion se usó 8, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'carnes'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'cuidado_personal'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'frutas_verduras'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'licores'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'limpieza'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'mascotas'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'panaderia'; se pronosticó y para en_promocion se usó 0, la última promoción conocida de la tienda"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltaba la familia 'snacks'; se pronosticó y para en_promocion se usó 9, la última promoción conocida de la tienda"
      }
    ]
  }
}
```

## X06_promocion_invalida

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"tienda_id": 5, "fecha": "2025-11-17", "familias": [{"familia_id": "abarrotes", "en_promocion": "muchas"}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}]}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[0].en_promocion",
        "accion": "advertir",
        "detalle": "en_promocion de 'abarrotes' inválido ('muchas' no es un número); se usó 0, la última promoción conocida de la tienda"
      }
    ]
  }
}
```

## X07_campos_sinonimos_y_desconocido

`POST /v1/prediccion` → **200**

<details><summary>Solicitud</summary>

```json
{"store_id": "T05", "date": "2025-11-17T06:00:00", "productos": [{"familia_id": "abarrotes", "en_promocion": 0}, {"familia_id": "bebe", "en_promocion": 0}, {"familia_id": "bebidas", "en_promocion": 8}, {"familia_id": "carnes", "en_promocion": 0}, {"familia_id": "cuidado_personal", "en_promocion": 0}, {"familia_id": "frutas_verduras", "en_promocion": 0}, {"familia_id": "lacteos", "en_promocion": 0}, {"familia_id": "licores", "en_promocion": 0}, {"familia_id": "limpieza", "en_promocion": 0}, {"familia_id": "mascotas", "en_promocion": 0}, {"familia_id": "panaderia", "en_promocion": 0}, {"familia_id": "snacks", "en_promocion": 9}], "origen": "pos-v2"}
```
</details>

```json
{
  "tienda_id": 5,
  "fecha": "2025-11-17",
  "version_modelo": "5",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 964.6,
      "cantidad_sugerida": 1177
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 64.1,
      "cantidad_sugerida": 83
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 978.4,
      "cantidad_sugerida": 1263
    },
    {
      "familia_id": "carnes",
      "venta_esperada": 224.7,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "cuidado_personal",
      "venta_esperada": 172.8,
      "cantidad_sugerida": 234
    },
    {
      "familia_id": "frutas_verduras",
      "venta_esperada": 343.7,
      "cantidad_sugerida": 310
    },
    {
      "familia_id": "lacteos",
      "venta_esperada": 438.8,
      "cantidad_sugerida": 422
    },
    {
      "familia_id": "licores",
      "venta_esperada": 76.7,
      "cantidad_sugerida": 119
    },
    {
      "familia_id": "limpieza",
      "venta_esperada": 192.2,
      "cantidad_sugerida": 256
    },
    {
      "familia_id": "mascotas",
      "venta_esperada": 44.9,
      "cantidad_sugerida": 58
    },
    {
      "familia_id": "panaderia",
      "venta_esperada": 237.8,
      "cantidad_sugerida": 203
    },
    {
      "familia_id": "snacks",
      "venta_esperada": 333.7,
      "cantidad_sugerida": 404
    }
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "store_id",
        "accion": "reparar",
        "detalle": "el campo 'store_id' se interpretó como 'tienda_id'"
      },
      {
        "campo": "date",
        "accion": "reparar",
        "detalle": "el campo 'date' se interpretó como 'fecha'"
      },
      {
        "campo": "productos",
        "accion": "reparar",
        "detalle": "el campo 'productos' se interpretó como 'familias'"
      },
      {
        "campo": "origen",
        "accion": "advertir",
        "detalle": "se ignoró el campo desconocido 'origen'"
      },
      {
        "campo": "store_id",
        "accion": "reparar",
        "detalle": "'T05' se interpretó como la tienda 5"
      },
      {
        "campo": "date",
        "accion": "reparar",
        "detalle": "'2025-11-17T06:00:00' se interpretó como 2025-11-17"
      }
    ]
  }
}
```

## X08_cuerpo_no_json

`POST /v1/prediccion` → **422**

<details><summary>Solicitud</summary>

```json
tienda=5&fecha=hoy
```
</details>

```json
{
  "detail": "el cuerpo no es JSON válido (JSONDecodeError: Expecting value: line 1 column 1 (char 0))"
}
```
