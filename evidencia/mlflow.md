# Evidencia de MLflow

Exportado con `python scripts/exportar_evidencia.py` desde http://localhost:5001.

## Experimento `novamercado-ventas`

| tanda (run padre) | origen | fecha de corte | filas | observaciones | atípicas excluidas | promos imputadas | costo validación (producción) |
|---|---|---|---|---|---|---|---|
| tanda-2026-02-28 (`7a3fadfa`) | inicializador | 2026-02-28 | 83052 | 0 | 0 | 0 | 369,741 |
| tanda-2026-03-13 (`fab2ffa3`) | reentrenamiento | 2026-03-13 | 84456 | 1404 | 0 | 192 | 372,086 |
| tanda-2026-03-27 (`1ee25f39`) | reentrenamiento | 2026-03-27 | 86136 | 3084 | 0 | 288 | 374,666 |
| tanda-2026-04-10 (`84adc466`) | reentrenamiento | 2026-04-10 | 87816 | 4764 | 0 | 384 | 385,657 |
| tanda-2026-04-24 (`696b70a7`) | reentrenamiento | 2026-04-24 | 89496 | 6444 | 0 | 480 | 389,254 |
| tanda-2026-04-24 (`7efe43a5`) | reentrenamiento | 2026-04-24 | 89496 | 6444 | 0 | 480 | 389,254 |

### Escalera de la última tanda (tanda-2026-04-24)

| modelo | WAPE | sesgo | costo | producción |
|---|---|---|---|---|
| baseline | 0.2646 | +0.0081 | 518,260 | False |
| gbm_directo | 0.1981 | -0.0552 | 398,998 | False |
| gbm_relativo_absoluta | 0.1937 | -0.0367 | 394,959 | False |
| gbm_relativo_sin_escala | 0.1922 | -0.0138 | 389,254 | True |

## Model Registry: `novamercado-ventas`

Aliases: {'anterior': '4', 'champion': '5'}

| versión | origen | decisión | fue champion | fecha de corte | costo validación | motivo |
|---|---|---|---|---|---|---|
| 1 | inicializador | — | true | 2026-02-28 | 369740.7 | — |
| 2 | reentrenamiento | promovido | true | 2026-03-13 | 372085.8 | Costo en validación 40 807 vs 40 755 del vigente (v1; +0.1%; 13 días posteriores a su corte: 2026-03-01..2026-03-13) |
| 3 | reentrenamiento | promovido | true | 2026-03-27 | 374666.4 | Costo en validación 50 310 vs 50 324 del vigente (v2; -0.0%; 14 días posteriores a su corte: 2026-03-14..2026-03-27) |
| 4 | reentrenamiento | promovido | true | 2026-04-10 | 385656.8 | Costo en validación 63 706 vs 63 731 del vigente (v3; -0.0%; 14 días posteriores a su corte: 2026-03-28..2026-04-10) |
| 5 | reentrenamiento | promovido | true | 2026-04-24 | 389254.3 | Costo en validación 61 990 vs 62 173 del vigente (v4; -0.3%; 14 días posteriores a su corte: 2026-04-11..2026-04-24) |
| 6 | reentrenamiento | rechazado | — | 2026-04-24 | 389254.3 | solo hay 0 días de ventas posteriores al corte del vigente (v5); se necesitan 7 para compararlos fuera de muestra: se conserva el vigente |
