## Objetivo

Evaluar si la variante avanzada `covariance_aware` de `risk contribution` debe reemplazar al modelo MVP en producto o activarse solo bajo condiciones controladas.

## Consumos actuales revisados

- `apps/dashboard/selectors.py`
  - `get_analytics_v2_dashboard_summary()` consume hoy `RiskContributionService`
- `templates/dashboard/estrategia.html`
  - muestra el top activo y sector de riesgo en la sección `Analytics v2`
- `apps/core/services/recommendation_engine.py`
  - usa señales del `RiskContributionService` MVP

## Reutilización aplicada

- se mantiene `RiskContributionService` como baseline estable
- se usa `CovarianceAwareRiskContributionService` solo como capa avanzada evaluable
- no se cambia el contrato legacy del motor de recomendaciones

## Hallazgo sobre datos reales

Verificación manual sobre la base actual al 2026-03-15:

- `model_variant = mvp_proxy`
- `covariance_observations = 5`
- `coverage_pct = 100.0`
- warning principal:
  - `insufficient_covariance_history`

Conclusión:

- hoy no hay base histórica suficiente para reemplazar el resultado visible del MVP con covarianza
- sí conviene exponer en dashboard el estado metodológico de la activación

## Decisión de integración

Integración aprobada para producto:

- activación selectiva automática en dashboard solo cuando:
  - `model_variant = covariance_aware`
- fallback visible y explícito al MVP cuando no se cumplan condiciones

Integración no aprobada todavía:

- usar la variante avanzada para señales del motor de recomendaciones
- reemplazar silenciosamente el resultado MVP sin informar metodología activa

## Condiciones mínimas visibles para producto

La variante avanzada solo debe activarse cuando se cumplan simultáneamente:

- al menos `20` observaciones diarias útiles
- al menos `3` activos cubiertos
- al menos `80%` de cobertura del portafolio invertido
- matriz de covarianza usable
- volatilidad de portafolio positiva

## Comportamiento de UI decidido

En `Estrategia`, el bloque `Risk Contribution` ahora debe:

- mostrar `Covarianza activa` cuando la variante avanzada esté realmente operativa
- mostrar `Proxy MVP` cuando la covarianza no esté activa
- acompañar el estado con:
  - observaciones diarias
  - cobertura patrimonial

## Limitaciones

- las señales de recomendaciones siguen atadas al MVP
- no se expone todavía comparación lado a lado MVP vs covarianza
- no se integró el modelo avanzado en `Análisis` ni en APIs dedicadas

## Extensión futura sugerida

Si la historia diaria mejora, el siguiente paso razonable es:

- comparar ambos modelos en dashboard con tooltip metodológico
- evaluar si algunas señales de concentración deben migrar a la variante avanzada
