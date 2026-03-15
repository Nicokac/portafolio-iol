# Priorizacion de recomendaciones combinadas

## Objetivo

Reducir ruido en `Planeacion` cuando conviven recomendaciones legacy y señales de Analytics v2.

## Regla MVP

La priorizacion combinada:

1. ordena por prioridad (`alta`, `media`, `baja`)
2. prefiere recomendaciones `analytics_v2` cuando pisan el mismo problema tactico
3. conserva recomendaciones distintas aunque tengan prioridad similar

## Topics deduplicados en el MVP

- liquidez excesiva
- concentracion Argentina
- concentracion patrimonial / de riesgo en pocos activos

## Limites deliberados

- no hace deduplicacion semantica amplia
- no fusiona descripciones
- no reescribe acciones sugeridas
- no pondera todavia por `confidence`
