## Objetivo

Medir con datos reales cuántas veces el modelo avanzado `covariance_aware` se activa y cuántas veces cae a fallback.

## Reutilización aplicada

Se reutilizó el canal existente de observabilidad en memoria:

- `apps/core/services/observability.py`
- endpoint staff `metrics/internal-observability/`

No se creó:

- tabla nueva
- endpoint nuevo
- persistencia adicional

## Implementación

Cada ejecución de `CovarianceAwareRiskContributionService.calculate()` registra un estado en cache:

- métrica: `analytics_v2.risk_contribution.model_variant`
- estado:
  - `covariance_aware`
  - `mvp_proxy`

Extra asociado:

- `observations`
- `coverage_pct`
- `reason` cuando hubo fallback

## Consumo

El endpoint staff de observabilidad interna ahora devuelve:

- `metrics`
- `states`

Dentro de `states` queda disponible el resumen de activación del modelo avanzado.

## Utilidad operativa

Permite responder con evidencia:

- si el modelo avanzado se está activando en producción real
- con qué frecuencia cae al MVP
- cuál es la causa dominante de fallback

## Limitaciones

- observabilidad en cache, no persistente
- ventana corta, dependiente del TTL
- no expone serie temporal completa, solo resumen rolling
