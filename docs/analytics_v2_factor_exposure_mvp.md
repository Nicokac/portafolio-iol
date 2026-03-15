# Analytics v2 - Factor Exposure MVP

## Objetivo

Agregar exposicion por factor sobre las posiciones actuales ya clasificadas por el
clasificador proxy MVP.

## Input

- posiciones actuales normalizadas
- clasificacion individual por activo
- catalogo cerrado de factores MVP

## Output

`FactorExposureService.calculate()` devuelve:

- `factors`
- `dominant_factor`
- `underrepresented_factors`
- `unknown_assets`
- `metadata`

## Regla MVP

- las exposiciones porcentuales se calculan sobre `classified_positions_market_value`
- activos sin proxy razonable quedan en `unknown_assets`
- `unknown_assets` no entra en el denominador de exposicion factorial
- `dominant_factor` es el de mayor `exposure_pct`
- `underrepresented_factors` son los factores bajo el umbral MVP

## Trazabilidad

La metadata deja explicito:

- metodologia
- base economica usada
- limitaciones
- confianza
- warnings de fallback y activos unknown

## Limitaciones

- no es un factor model estadistico
- no clasifica todo el portafolio por fuerza
- depende de la calidad del mapping proxy
- no genera todavia señales para recomendaciones
