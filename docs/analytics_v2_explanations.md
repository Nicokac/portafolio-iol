# Analytics v2 - Interpretaciones automáticas

## Objetivo

Agregar explicaciones determinísticas para resultados analíticos ya calculados, sin modificar modelos ni recalcular métricas.

## Servicio

`AnalyticsExplanationService` transforma resultados existentes en texto interpretable para:

- `Risk Contribution`
- `Scenario Analysis`
- `Factor Exposure`

## Integración

Las interpretaciones se agregan en `get_analytics_v2_dashboard_summary()` y se renderizan server-side en `Estrategia`.

Campos expuestos:

- `risk_contribution.interpretation`
- `scenario_analysis.interpretation`
- `factor_exposure.interpretation`

## Restricciones

- no usa LLMs
- no agrega endpoints
- no modifica cálculos de los modelos
- no introduce dependencias externas

## Limitaciones

- las explicaciones son heurísticas y resumidas
- no reemplazan un drill-down detallado
- por ahora no cubren `Stress Fragility` ni `Expected Return`
