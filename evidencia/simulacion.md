# Simulación de la operación

Generado con `python scripts/simular_operacion.py` (periodo 2026-03-01..2026-04-25, 5.6 min).

- Respuestas: {'pred 200': 507, 'pred 422': 40, 'obs 200': 537}; **5xx: 0**; errores de contrato en respuestas 200: **0**.
- Costo de las cantidades sugeridas: **206,651** contra 402,341 de sugerir lo vendido el mismo día de la semana anterior (-48.6%).
- Cambio de demanda desde 2026-03-29: {'bebidas': 1.35, 'snacks': 1.35, 'carnes': 0.75, 'abarrotes': 1.15}.

## Por semana

| semana | costo | costo ingenuo | vs ingenuo | WAPE | versiones |
|---|---|---|---|---|---|
| 2026-02-23/2026-03-01 | 1,790 | 4,020 | -55.5% | 0.161 | 1 |
| 2026-03-02/2026-03-08 | 20,482 | 40,406 | -49.3% | 0.171 | 1 |
| 2026-03-09/2026-03-15 | 21,038 | 43,575 | -51.7% | 0.185 | 1 |
| 2026-03-16/2026-03-22 | 24,257 | 43,418 | -44.1% | 0.195 | 1,2 |
| 2026-03-23/2026-03-29 | 22,115 | 40,800 | -45.8% | 0.193 | 2 |
| 2026-03-30/2026-04-05 | 35,484 | 71,084 | -50.1% | 0.236 | 2,3 |
| 2026-04-06/2026-04-12 | 24,926 | 45,438 | -45.1% | 0.194 | 3 |
| 2026-04-13/2026-04-19 | 37,428 | 63,294 | -40.9% | 0.256 | 3 |
| 2026-04-20/2026-04-26 | 19,129 | 50,307 | -62.0% | 0.182 | 3 |

## Reentrenamientos

- 2026-03-14: exitoso en 55 s — promovido: True, versión 2. Costo en validación 40 807 vs 40 755 del vigente (v1; +0.1%; 13 días posteriores a su corte: 2026-03-01..2026-03-13)
- 2026-03-28: exitoso en 45 s — promovido: True, versión 3. Costo en validación 50 310 vs 50 324 del vigente (v2; -0.0%; 14 días posteriores a su corte: 2026-03-14..2026-03-27)
- 2026-04-11: exitoso en 50 s — promovido: True, versión 4. Costo en validación 63 706 vs 63 731 del vigente (v3; -0.0%; 14 días posteriores a su corte: 2026-03-28..2026-04-10)
- 2026-04-25: exitoso en 50 s — promovido: True, versión 5. Costo en validación 61 990 vs 62 173 del vigente (v4; -0.3%; 14 días posteriores a su corte: 2026-04-11..2026-04-24)

## Eventos

- {'dia': '2026-03-21', 'evento': 'MLflow detenido', 'segundos_hasta_degradado': 4.0261594999997214}
- {'dia': '2026-03-24', 'evento': 'MLflow de vuelta', 'segundos_hasta_ok': 5.029436040999826}
- {'dia': '2026-04-05', 'evento': 'down + up (volúmenes conservados)', 'segundos_hasta_ok': 25}

## Solicitudes por tipo de problema (código o estado de calidad)

| tipo | resultado |
|---|---|
| campo_extra | {'advertencia': 18} |
| campo_renombrado | {'corregido': 11} |
| cuerpo_roto | {'422': 11} |
| faltan_familias | {'advertencia': 19} |
| familia_desconocida | {'advertencia': 9} |
| familia_forma | {'corregido': 14} |
| familia_repetida | {'advertencia': 13} |
| fecha_formato | {'corregido': 13, 'advertencia': 2} |
| fecha_imposible | {'422': 12} |
| promo_invalida | {'advertencia': 15} |
| promo_texto | {'corregido': 16} |
| tienda_inexistente | {'422': 17} |
| tienda_texto | {'corregido': 18} |
| valida | {'ok': 358, 'advertencia': 1} |
