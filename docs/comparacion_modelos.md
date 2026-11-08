# Comparación de modelos

Generado con `python scripts/comparar_modelos.py`. No editar a mano.

Ventanas de validación: 2025-11-09..2025-12-06, 2025-12-07..2026-01-03, 2026-01-04..2026-01-31, 2026-02-01..2026-02-28.

## 1. Escalera (validación temporal)

`costo` usa el factor por familia elegido en validación; `costo_k_1` sugiere exactamente la venta esperada.

| modelo | wape | sesgo | mae | costo | costo_k_1 | pred_max | segundos | vs_baseline |
|---|---|---|---|---|---|---|---|---|
| baseline | 0.2672 | -0.005 | 59.1 | 543415.0 | 717024.0 | 2277.0 | 0.0 | 0.0 |
| gbm_directo | 0.1796 | -0.0266 | 39.7 | 371454.0 | 502971.0 | 2048.0 | 12.0 | -0.316 |
| gbm_relativo_absoluta | 0.1768 | -0.0082 | 39.1 | 367090.0 | 485867.0 | 2388.0 | 13.0 | -0.324 |
| gbm_relativo_sin_escala | 0.1797 | 0.0053 | 39.7 | 369741.0 | 481068.0 | 2647.0 | 13.0 | -0.32 |
| gbm_relativo_sin_escala_vm180 | 0.181 | 0.0053 | 40.0 | 371778.0 | 485561.0 | 2643.0 | 16.0 | -0.316 |
| gbm_sin_escala_lr0.1 | 0.1799 | 0.0053 | 39.8 | 370242.0 | 479955.0 | 2820.0 | 8.0 | -0.319 |
| gbm_sin_escala_lr0.03 | 0.1794 | 0.0046 | 39.7 | 368757.0 | 479915.0 | 2707.0 | 24.0 | -0.321 |
| gbm_sin_escala_msl100 | 0.18 | 0.0067 | 39.8 | 370008.0 | 479995.0 | 2735.0 | 14.0 | -0.319 |

## 2. Cambio de demanda sin reentrenar

Sesgo = venta esperada total / venta real total − 1 por familia, del 2026-01-18 al 2026-02-28.

### bebidas y snacks +40 %, carnes −30 %

| modelo | bebidas | snacks | carnes | abarrotes |
|---|---|---|---|---|
| baseline | -0.05 | -0.049 | 0.091 | -0.002 |
| gbm_directo | -0.158 | -0.112 | 0.068 | -0.049 |
| gbm_relativo_absoluta | -0.089 | -0.073 | 0.061 | -0.024 |
| gbm_relativo_sin_escala | -0.033 | -0.029 | 0.036 | -0.004 |

### todas las familias +25 %

| modelo | bebidas | snacks | carnes | abarrotes |
|---|---|---|---|---|
| baseline | -0.036 | -0.036 | -0.023 | -0.032 |
| gbm_directo | -0.113 | -0.092 | -0.116 | -0.164 |
| gbm_relativo_absoluta | -0.067 | -0.063 | -0.078 | -0.068 |
| gbm_relativo_sin_escala | -0.025 | -0.022 | -0.025 | -0.02 |

## 3. Cantidad sugerida

Modelo de producción: `gbm_relativo_sin_escala`.

- Factores por familia: {'abarrotes': 1.18, 'bebe': 1.3, 'bebidas': 1.2, 'carnes': 0.93, 'cuidado_personal': 1.3, 'frutas_verduras': 0.9, 'lacteos': 0.94, 'licores': 1.53, 'limpieza': 1.31, 'mascotas': 1.23, 'panaderia': 0.86, 'snacks': 1.15}.
- Ventanas 2 a 4 con el factor elegido en las ventanas anteriores (fuera de muestra): 280,719; con el factor elegido usando todas las ventanas: 278,559 (+0.8%).
