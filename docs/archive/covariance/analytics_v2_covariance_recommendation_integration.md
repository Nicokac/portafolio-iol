## Objetivo

Definir si el motor de recomendaciones debe seguir consumiendo `RiskContributionService` o pasar a selección dinámica con `CovarianceAwareRiskContributionService`.

## Punto de integración revisado

El punto correcto de decisión es:

- `RecommendationEngine._analyze_analytics_v2()`

Razón:

- ya centraliza la combinación de señales Analytics v2
- ya aplica priorización y deduplicación
- evita mover lógica analítica a vistas o templates

## Decisión aplicada

Se implementó selección dinámica solo para señales de riesgo:

- si `CovarianceAwareRiskContributionService.calculate()` devuelve `model_variant = covariance_aware`
  - el engine usa señales del modelo avanzado
- si no
  - el engine usa señales del MVP

## Compatibilidad preservada

La integración mantiene:

- el mismo contrato de recomendaciones legacy
- la misma priorización
- la misma deduplicación por topic

Solo se agrega un campo opcional de trazabilidad:

- `modelo_riesgo`

Valores posibles:

- `covariance_aware`
- `mvp_proxy`

## Razón metodológica

No conviene hardcodear el modelo avanzado en recomendaciones mientras:

- la activación real todavía dependa de historia diaria suficiente
- el fallback al MVP siga siendo frecuente en datos reales

La selección dinámica permite:

- usar el modelo avanzado cuando realmente aporta valor
- preservar el comportamiento actual cuando no hay base suficiente

## Limitaciones

- no se recalibraron thresholds para covarianza
- no se pondera la recomendación por `coverage_pct` ni por `covariance_observations`
- el engine no expone todavía en UI por qué eligió un modelo u otro

## Próximo paso natural

Si la activación real del modelo avanzado se vuelve frecuente:

- exponer `modelo_riesgo` en API o planeación
- evaluar si algunas acciones sugeridas deben cambiar bajo `covariance_aware`
