# Perfil de los datos publicados

Generado con `python scripts/perfilar_datos.py`. No editar a mano.

## Histórico de ventas

- Filas: 83,052; fechas 2024-03-01 a 2026-02-28 (730 días; faltan 0).
- Tiendas: 10; familias: 12; combinaciones tienda×familia: 120.
- Nulos: 0; duplicados (fecha, tienda, familia): 0; ventas negativas: 0; ventas en cero: 139.

### Por tienda

| tienda_id | desde | hasta | filas | venta_media | ciudad | tipo | fecha_apertura |
|---|---|---|---|---|---|---|---|
| 1 | 2024-03-01 | 2026-02-28 | 8760 | 311.6 | Guatemala | hipermercado | 2019-01-01 |
| 2 | 2024-03-01 | 2026-02-28 | 8760 | 191.8 | Mixco | supermercado | 2019-01-01 |
| 3 | 2024-03-01 | 2026-02-28 | 8760 | 340.0 | Villa Nueva | hipermercado | 2019-01-01 |
| 4 | 2024-03-01 | 2026-02-28 | 8760 | 69.1 | Guatemala | express | 2019-01-01 |
| 5 | 2024-03-01 | 2026-02-28 | 8760 | 403.9 | Quetzaltenango | hipermercado | 2019-01-01 |
| 6 | 2024-03-01 | 2026-02-28 | 8760 | 185.7 | Antigua Guatemala | supermercado | 2019-01-01 |
| 7 | 2024-03-01 | 2026-02-28 | 8760 | 215.0 | Escuintla | supermercado | 2019-01-01 |
| 8 | 2024-03-01 | 2026-02-28 | 8760 | 190.7 | Cobán | supermercado | 2019-01-01 |
| 9 | 2024-03-01 | 2026-02-28 | 8760 | 65.4 | Chimaltenango | express | 2019-01-01 |
| 10 | 2025-03-15 | 2026-02-28 | 4212 | 66.7 | Guatemala | express | 2025-03-15 |

### Por familia

| familia_id | venta_media | desv | maximo | promo_max | pct_dias_con_promo |
|---|---|---|---|---|---|
| abarrotes | 581.2 | 406.2 | 3479 | 19 | 60.9 |
| bebe | 39.5 | 28.8 | 187 | 9 | 36.3 |
| bebidas | 444.5 | 304.8 | 2900 | 14 | 57.9 |
| carnes | 149.3 | 122.5 | 989 | 11 | 28.6 |
| cuidado_personal | 137.8 | 87.6 | 586 | 16 | 50.2 |
| frutas_verduras | 237.1 | 151.8 | 888 | 12 | 40.3 |
| lacteos | 256.2 | 159.9 | 1158 | 13 | 47.6 |
| licores | 79.0 | 60.6 | 704 | 10 | 38.3 |
| limpieza | 173.0 | 106.7 | 756 | 18 | 56.5 |
| mascotas | 34.6 | 23.9 | 136 | 9 | 36.3 |
| panaderia | 193.5 | 111.3 | 961 | 7 | 19.6 |
| snacks | 212.1 | 112.1 | 954 | 13 | 48.6 |

## Patrones

- Crecimiento interanual de la venta diaria total (mes contra mismo mes): mediana 10.3 %.

- Índice por día de la semana (1 = promedio): lun 0.88, mar 0.89, mié 0.91, jue 0.93, vie 1.08, sáb 1.23, dom 1.08.
- Índice por día del mes (1 = mediana); los mayores: día 31: 1.36, día 15: 1.17, día 16: 1.11, día 1: 1.06, día 30: 1.05, día 24: 1.04. La quincena (15) y el fin de mes suben aunque `feriados.csv` solo marca 6 fechas de pago (Bono 14 y aguinaldo).

### Efecto de feriados y fechas especiales en el histórico

`indice` = venta del día / media de los 14 días previos (tiendas del ámbito).

| fecha | nombre | tipo | ambito | indice |
|---|---|---|---|---|
| 2024-03-28 | Jueves Santo | feriado | nacional | 0.85 |
| 2024-03-29 | Viernes Santo | feriado | nacional | 0.92 |
| 2024-03-30 | Sábado Santo | feriado | nacional | 1.12 |
| 2024-05-01 | Día del Trabajo | feriado | nacional | 0.95 |
| 2024-05-10 | Día de la Madre | comercial | nacional | 1.23 |
| 2024-06-17 | Día del Padre | comercial | nacional | 0.92 |
| 2024-06-30 | Día del Ejército | feriado | nacional | 1.21 |
| 2024-07-15 | Pago del Bono 14 | pago | nacional | 0.98 |
| 2024-07-25 | Santiago Apóstol | feriado | Antigua Guatemala | 0.86 |
| 2024-08-04 | Santo Domingo de Guzmán | feriado | Cobán | 1.09 |
| 2024-08-15 | Virgen de la Asunción | feriado | Guatemala | 1.19 |
| 2024-09-15 | Día de la Independencia | feriado | nacional | 1.14 |
| 2024-10-20 | Día de la Revolución | feriado | nacional | 1.07 |
| 2024-11-01 | Día de Todos los Santos | feriado | nacional | 1.17 |
| 2024-11-29 | Viernes Negro | comercial | nacional | 1.33 |
| 2024-12-15 | Pago del aguinaldo | pago | nacional | 1.3 |
| 2024-12-24 | Nochebuena (medio día) | medio_dia | nacional | 1.47 |
| 2024-12-25 | Navidad | feriado | nacional | 0.33 |
| 2024-12-31 | Fin de año (medio día) | medio_dia | nacional | 1.61 |
| 2025-01-01 | Año Nuevo | feriado | nacional | 0.25 |
| 2025-02-14 | Día del Cariño | comercial | nacional | 1.03 |
| 2025-04-17 | Jueves Santo | feriado | nacional | 0.97 |
| 2025-04-18 | Viernes Santo | feriado | nacional | 0.92 |
| 2025-04-19 | Sábado Santo | feriado | nacional | 1.08 |
| 2025-05-01 | Día del Trabajo | feriado | nacional | 1.08 |
| 2025-05-10 | Día de la Madre | comercial | nacional | 1.21 |
| 2025-06-17 | Día del Padre | comercial | nacional | 0.95 |
| 2025-06-30 | Día del Ejército | feriado | nacional | 1.0 |
| 2025-07-15 | Pago del Bono 14 | pago | nacional | 1.02 |
| 2025-07-25 | Santiago Apóstol | feriado | Antigua Guatemala | 0.97 |
| 2025-08-04 | Santo Domingo de Guzmán | feriado | Cobán | 0.83 |
| 2025-08-15 | Virgen de la Asunción | feriado | Guatemala | 1.22 |
| 2025-09-15 | Día de la Independencia | feriado | nacional | 0.98 |
| 2025-10-20 | Día de la Revolución | feriado | nacional | 0.85 |
| 2025-11-01 | Día de Todos los Santos | feriado | nacional | 1.39 |
| 2025-11-28 | Viernes Negro | comercial | nacional | 1.29 |
| 2025-12-15 | Pago del aguinaldo | pago | nacional | 1.09 |
| 2025-12-24 | Nochebuena (medio día) | medio_dia | nacional | 1.46 |
| 2025-12-25 | Navidad | feriado | nacional | 0.32 |
| 2025-12-31 | Fin de año (medio día) | medio_dia | nacional | 1.69 |
| 2026-01-01 | Año Nuevo | feriado | nacional | 0.28 |
| 2026-02-14 | Día del Cariño | comercial | nacional | 1.25 |

- `feriados.csv` cubre de 2024-03-28 a 2026-12-31; ámbitos locales: ['Antigua Guatemala', 'Cobán', 'Guatemala'], todos presentes en `tiendas.ciudad`: True.

## Promociones

- Correlación de `en_promocion` con la del día anterior: 0.83; igual al día anterior en 61 % de las filas.
- Venta relativa a la media de los 28 días previos, por número de productos en promoción: (-1, 0]: 0.93, (0, 2]: 1.08, (2, 5]: 1.12, (5, 10]: 1.14, (10, 20]: 1.17.

## Costos

`tau_critico` = c_faltante / (c_faltante + c_sobrante): cuantil de la demanda que minimiza el costo esperado (newsvendor). Mayor a 0.5 = conviene sugerir por encima del pronóstico.

| familia_id | costo_faltante | costo_sobrante | tau_critico |
|---|---|---|---|
| abarrotes | 1.0 | 0.2 | 0.833 |
| bebidas | 1.0 | 0.2 | 0.833 |
| lacteos | 1.0 | 1.2 | 0.455 |
| carnes | 1.5 | 2.0 | 0.429 |
| panaderia | 1.0 | 2.5 | 0.286 |
| frutas_verduras | 1.0 | 2.0 | 0.333 |
| limpieza | 1.0 | 0.1 | 0.909 |
| cuidado_personal | 1.0 | 0.1 | 0.909 |
| licores | 2.0 | 0.1 | 0.952 |
| snacks | 1.0 | 0.3 | 0.769 |
| bebe | 1.5 | 0.2 | 0.882 |
| mascotas | 1.0 | 0.2 | 0.833 |

## Catálogos y ejemplos

- Familias: abarrotes, bebidas, lacteos, carnes, panaderia, frutas_verduras, limpieza, cuidado_personal, licores, snacks, bebe, mascotas (nombres con tildes y espacios: Abarrotes, Bebidas, Lácteos, Carnes, Panadería, Frutas y verduras, Limpieza, Cuidado personal, Licores, Snacks y dulces, Bebé, Mascotas).
- Tiendas: 10; tipos {'supermercado': 4, 'hipermercado': 3, 'express': 3}.

- `ejemplos/observacion_valida.json` (5, 2025-11-17): 12 de 12 valores son idénticos al histórico.
- Ejemplos de error: E01_tienda_texto, E02_familia_otra_forma, E03_promocion_texto, E04_fecha_formato, E05_faltan_familias, E06_familia_repetida, E07_campo_renombrado, E08_ventas_negativas, E09_envio_repetido, E10_numero_formato.
