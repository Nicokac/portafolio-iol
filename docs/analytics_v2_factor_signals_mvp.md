# Analytics v2 - Factor Signals MVP

## Objetivo

Derivar señales reutilizables para recomendaciones a partir del resultado agregado de
`factor exposure`, sin integrar todavía con frontend ni `RecommendationEngine`.

## Output

`FactorExposureService.build_recommendation_signals()` devuelve una lista serializable de
`RecommendationSignal`.

Señales MVP actuales:

- `factor_growth_excess`
- `factor_defensive_gap`
- `factor_dividend_gap`
- `factor_concentration_excessive`

## Regla MVP

- exceso de growth: la exposición growth supera el umbral definido
- falta de defensive: la exposición defensive queda por debajo del umbral mínimo
- falta de dividend: la exposición dividend queda por debajo del umbral mínimo
- concentración factorial: un solo factor domina demasiado la exposición clasificada

## Limitaciones

- thresholds fijos y no configurables todavía
- no pondera por convicción ni horizonte de inversión
- no integra todavía con el motor legacy de recomendaciones
