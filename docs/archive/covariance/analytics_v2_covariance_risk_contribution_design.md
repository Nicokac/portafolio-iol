# Analytics v2 - Diseno de Covariance-Aware Risk Contribution

## Objetivo del modulo

Agregar una segunda version de `risk contribution` que mejore el modelo MVP actual:

- MVP actual:
  - `risk_score_i = weight_i * volatility_proxy_i`
- modulo avanzado propuesto:
  - usar una matriz de covarianza cuando la historia lo permita
  - seguir devolviendo una explicacion serializable y auditable
  - no romper el contrato ni reemplazar el MVP como fallback

La pregunta que debe responder el modulo es:

> que posiciones explican el riesgo total del portafolio cuando se consideran tambien co-movimientos entre activos

## Reutilizacion existente

### Servicios ya disponibles

- `apps/core/services/portfolio/covariance_service.py`
- `apps/core/services/portfolio/risk_parity_service.py`
- `apps/core/services/portfolio/optimizer_markowitz.py`
- `apps/core/services/analytics_v2/risk_contribution_service.py`

### Tests ya disponibles

- `apps/core/tests/test_portfolio_quant_services.py`
- `apps/core/tests/test_hardening_fallbacks.py`
- `apps/core/tests/test_analytics_v2_risk_contribution_service.py`

## Hallazgo clave previo

`CovarianceService` hoy pivotea por `fecha_extraccion` completa.

Eso implica un riesgo metodologico real:

- puede contar snapshots intradia como observaciones distintas
- puede sobreestimar cantidad de historia util
- puede producir covarianza aparente con una base temporal falsa

Por lo tanto, el modulo avanzado no debe consumir `CovarianceService` tal como esta sin una decision explicita sobre frecuencia.

## Decision de diseño

El modulo avanzado debe trabajar sobre:

- una serie diaria normalizada
- una observacion por activo por fecha
- ultima observacion valida del dia

No debe trabajar sobre:

- timestamps intradia crudos
- series con frecuencia mixta sin normalizacion

## Universo del calculo

Se mantiene la misma base economica del MVP:

- `portafolio invertido`

Se mantiene exclusion de:

- caucion
- cash management
- liquidez operativa pura

Razon:

- el objetivo sigue siendo explicar riesgo economico de inversion, no peso patrimonial bruto

## Formula avanzada acotada

### Version propuesta

Sea:

- `w` = vector de pesos del portafolio invertido
- `Sigma` = matriz de covarianza anualizada sobre retornos diarios por activo

Entonces:

```text
portfolio_vol = sqrt(w' * Sigma * w)
```

Y la contribucion marginal aproximada por activo:

```text
mrc_i = (Sigma * w)_i / portfolio_vol
```

Contribucion total por activo:

```text
trc_i = w_i * mrc_i
```

Normalizacion para dashboard:

```text
contribution_pct_i = trc_i / sum(trc) * 100
```

## Propiedades esperadas

- la suma de `contribution_pct_i` debe ser aproximadamente `100%`
- activos correlacionados pueden explicar mas riesgo conjunto que en el MVP
- la lectura deja de depender solo de `weight * volatility`

## Requisitos minimos de historia

Para habilitar el modelo covariance-aware:

1. al menos `20` observaciones diarias utiles del portafolio compartidas entre activos relevantes
2. al menos `3` activos elegibles con historia diaria suficiente
3. matriz de covarianza no vacia y numericamente usable

Razon:

- con menos historia, el ruido de estimacion domina
- el modelo avanzado deja de ser mas confiable que el MVP

## Regla de fallback

Si no se cumplen las condiciones anteriores:

- no se intenta forzar contribucion por covarianza
- se devuelve el resultado del `RiskContributionService` MVP actual
- metadata debe indicar:
  - `model_variant = mvp_proxy`
  - `warning = insufficient_covariance_history`

Si se cumplen:

- metadata debe indicar:
  - `model_variant = covariance_aware`

## Output esperado

No conviene inventar un contrato nuevo.

La version avanzada debe extender el contrato actual de `RiskContributionResult` con metadata adicional, por ejemplo:

- `model_variant`
- `covariance_observations`
- `portfolio_volatility_proxy`
- `used_covariance_matrix`

El detalle por activo debe seguir exponiendo:

- `symbol`
- `weight_pct`
- `contribution_pct`
- `sector`
- `country`
- `asset_type`

Y puede agregar:

- `marginal_risk_contribution`
- `total_risk_contribution`

## Calidad de datos y confidence

### `high`

- historia diaria suficiente
- covarianza usable
- pocos activos relevantes con fallback

### `medium`

- covarianza usable pero con cobertura parcial
- algunos activos importantes quedan fuera o degradados

### `low`

- historia insuficiente
- matriz degenerada
- fallback al MVP

## Integracion con el MVP actual

El modulo avanzado no debe reemplazar silenciosamente al actual.

Secuencia correcta:

1. implementar servicio separado
2. comparar outputs contra MVP
3. exponer en metadata que variante se esta usando
4. decidir despues si dashboard consume una u otra

## Riesgos del modulo

1. falsa precision con historia corta
2. distorsion por series intradia no agregadas a diario
3. perdida de comparabilidad con el MVP si no se expone `model_variant`
4. covarianza inestable con activos iliquidos o series muy cortas

## Criterios de aceptacion para implementacion

1. usa frecuencia diaria normalizada
2. no usa covarianza si la historia no alcanza
3. fallback controlado al MVP actual
4. suma de contribuciones aproximadamente `100%`
5. tests para:
   - portafolio vacio
   - historia insuficiente
   - matriz degenerada
   - activos correlacionados
   - coexistencia con fallback MVP

## Fuera de alcance

Este modulo no habilita todavia:

- betas por benchmark
- factor model estadistico
- Monte Carlo
- optimizacion de frontera
- matrices shrinkage o robust estimators
