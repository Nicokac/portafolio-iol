## Objetivo

Cerrar la primera iteración de Fase 8 con una validación integrada de:

- modelo avanzado `covariance_aware`
- fallback operativo al MVP
- integración con dashboard
- integración con recomendaciones
- trazabilidad expuesta en producto

## Estado validado

Validación manual sobre base real al 2026-03-15:

- `analytics_v2_summary.risk_contribution.model_variant = mvp_proxy`
- `covariance_observations = 5`
- `coverage_pct = 100.0`

Primera recomendación de riesgo encontrada en el engine:

- `tipo = analytics_v2_risk_vs_weight_divergence`
- `modelo_riesgo = mvp_proxy`

Conclusión operativa:

- la infraestructura avanzada quedó bien integrada
- pero la activación real del modelo de covarianza todavía no ocurre de forma estable con la base histórica actual

## Qué quedó resuelto en Fase 8 inicial

- inputs diarios normalizados para covarianza
- servicio `CovarianceAwareRiskContributionService`
- fallback explícito al MVP
- validación comparativa contra el MVP
- activación selectiva en `Estrategia`
- selección dinámica en `RecommendationEngine`
- trazabilidad `modelo_riesgo` visible en `Planeación`

## Qué no conviene hacer todavía

- reemplazar completamente el MVP en producto
- recalibrar thresholds usando muy poca historia real
- propagar `covariance_aware` a más módulos sin activación real frecuente
- abrir Monte Carlo, betas o modelos de factores estadísticos

## Decisión de cierre

Fase 8 inicial queda cerrada como:

- implementación técnica avanzada válida
- integración controlada
- activación real condicionada por datos

La próxima expansión no debería ser otro módulo técnico inmediato, sino una decisión de roadmap basada en:

- más historia diaria útil
- evidencia de activación real del modelo avanzado
- necesidad de negocio concreta
