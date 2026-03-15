# Analytics v2 - Stress Signals MVP

## Objetivo

Derivar señales reutilizables para recomendaciones a partir del resultado agregado de
`stress fragility`, sin integrar todavía con frontend ni `RecommendationEngine`.

## Output

`StressFragilityService.build_recommendation_signals()` devuelve una lista serializable de
`RecommendationSignal`.

Señales MVP actuales:

- `stress_fragility_local_crisis`
- `stress_fragility_high`
- `stress_sector_fragility`
- `stress_liquidity_buffer`

## Regla MVP

- fragilidad local: la crisis local severa deja una pérdida material
- fragilidad alta: al menos un stress deja score elevado
- fragilidad sectorial: un sector concentra una parte relevante de la pérdida
- buffer de liquidez: la fragilidad total queda suficientemente contenida

## Limitaciones

- thresholds fijos
- sin priorización final combinada con otros módulos
- sin integración todavía con el motor legacy de recomendaciones
