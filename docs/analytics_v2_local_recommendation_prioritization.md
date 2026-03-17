# Priorizacion local de recomendaciones

## Objetivo

Reducir ruido cuando varias senales locales describen el mismo problema tactico dentro del bloque argentino.

## Regla aplicada

El `RecommendationEngine` sigue usando deduplicacion por topico, pero ahora agrupa tambien:

- `analytics_v2_local_country_risk_high`
- `analytics_v2_local_sovereign_risk_excess`

como refinamientos del mismo topico de concentracion/riesgo argentino.

Y agrupa:

- `analytics_v2_local_inflation_hedge_gap`
- `analytics_v2_local_sovereign_hard_dollar_dependence`

como un mismo topico de mezcla local de renta fija.

## Preferencia interna

Cuando coinciden en prioridad y origen:

- `local_country_risk_high` gana sobre `local_sovereign_risk_excess`
- `local_sovereign_hard_dollar_dependence` gana sobre `local_inflation_hedge_gap`

## Senales que permanecen separadas

No se deduplican con esos topicos:

- `local_sovereign_single_name_concentration`

Porque describe un problema distinto:

- dependencia de un bono puntual

## Limitacion

La deduplicacion sigue siendo heuristica y acotada.
No intenta fusionar descripciones ni combinar evidencias entre senales.
