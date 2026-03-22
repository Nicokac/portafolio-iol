## Objetivo

Evaluar si las señales derivadas de `risk contribution` pueden migrar desde el modelo MVP a la variante `covariance_aware` sin romper contrato ni claridad metodológica.

## Señales revisadas

Se revisaron las cuatro señales actuales del módulo:

- `risk_concentration_top_assets`
- `risk_concentration_tech`
- `risk_concentration_argentina`
- `risk_vs_weight_divergence`

## Hallazgo técnico

Las señales no dependen del algoritmo interno del modelo, sino del contrato agregado de salida:

- `items`
- `top_contributors`
- `by_sector`
- `by_country`

Eso significa que cualquier variante de `risk contribution` que mantenga ese contrato puede reutilizar exactamente la misma lógica de señales.

## Decisión aplicada

Se consolidó la lógica de señales en `RiskContributionService` para que pueda operar sobre:

- resultado MVP
- resultado `covariance_aware`
- fallback MVP producido por el servicio avanzado

La variante avanzada ahora expone:

- `build_recommendation_signals()`

Comportamiento:

- si `model_variant = covariance_aware`, las señales se construyen desde el resultado avanzado
- si el servicio avanzado cae a fallback, las señales reutilizan la misma lógica del MVP sobre ese resultado fallback

## Decisión de integración

Migración permitida:

- a nivel de servicio analítico
- sin cambiar contrato de señales
- sin cambiar thresholds del MVP

Migración todavía no aplicada:

- `RecommendationEngine` sigue consumiendo el `RiskContributionService` MVP

Razón:

- con la base real actual, la variante avanzada todavía cae a fallback por historia insuficiente
- no conviene cambiar el origen operativo de recomendaciones hasta que el modelo avanzado se active con datos reales de forma estable

## Implicancia para producto

Cuando la historia diaria permita activar covarianza de verdad, la migración de señales ya no requiere rediseñar el contrato.

El cambio pendiente futuro sería solo de wiring:

- reemplazar la fuente de señales en el engine
- o elegir dinámicamente entre MVP y `covariance_aware`

## Limitaciones

- los thresholds siguen siendo los del MVP
- no se recalibraron severidades para el modelo avanzado
- no se integró todavía priorización especial por `model_variant`

## Próximo paso natural

Si la activación real del modelo avanzado mejora:

- evaluar migración selectiva del `RecommendationEngine`
- comparar si cambian materialmente señales de concentración en activos y divergencia riesgo/peso
