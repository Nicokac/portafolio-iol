# Analytics v2 - Covariance-Aware Risk Contribution

## Objetivo

Consolidar en un solo documento la capa avanzada de `risk contribution` basada en covarianza, su criterio de activacion, su integracion con dashboard y recomendaciones, y su estado operativo actual.

## Alcance

La variante avanzada busca mejorar el MVP `weight * volatility_proxy` cuando la historia diaria permite capturar co-movimientos entre activos.

No busca:

- reemplazar silenciosamente el MVP
- abrir Monte Carlo o modelos estadisticos mas complejos
- mezclar activos sin cobertura suficiente dentro de un resultado aparentemente robusto

## Base metodologica

Inputs requeridos:

- pesos del portafolio invertido
- serie diaria normalizada por activo
- matriz de covarianza usable

Formula resumida:

```text
portfolio_vol = sqrt(w' * Sigma * w)
mrc_i = (Sigma * w)_i / portfolio_vol
trc_i = w_i * mrc_i
contribution_pct_i = trc_i / sum(trc) * 100
```

## Condiciones de activacion

La variante `covariance_aware` solo debe activarse si se cumplen simultaneamente:

- al menos `20` observaciones diarias utiles
- al menos `3` activos cubiertos
- cobertura patrimonial suficiente del universo invertido
- matriz de covarianza usable
- volatilidad de portafolio positiva

Si no se cumplen esas condiciones:

- se vuelve al MVP
- `model_variant = mvp_proxy`
- debe quedar warning metodologico explicito

## Salida esperada

Mantiene el contrato base de `RiskContributionService` y agrega metadata como:

- `model_variant`
- `covariance_observations`
- `portfolio_volatility_proxy`
- `coverage_pct`
- `covered_symbols`
- `excluded_symbols`

## Integracion con producto

### Estrategia

- expone si la lectura visible usa `Covarianza activa` o `Proxy MVP`
- acompana el estado con observaciones y cobertura

### RecommendationEngine

- puede elegir dinamicamente entre MVP y variante avanzada
- mantiene el contrato legacy de recomendaciones
- solo agrega trazabilidad metodologica como `modelo_riesgo`

## Estado operativo actual

La infraestructura avanzada existe, pero su activacion real sigue condicionada por la calidad y profundidad de historia diaria disponible.

Decision vigente:

- mantener el MVP como baseline estable
- activar la variante avanzada solo cuando la base real la sostenga
- no recalibrar thresholds de recomendacion hasta tener mas activacion real

## Riesgos metodologicos

- falsa precision con historia corta
- sesgo si la serie no esta normalizada a diario
- baja frecuencia de activacion real con universos pequenos o historia corta
- confusion de producto si no se expone `model_variant`

## Documentacion archivada relacionada

La evolucion de esta familia queda preservada en `docs/archive/covariance/`.
