## Objetivo

Explicar por qué el modelo `covariance_aware` tiene pocas observaciones útiles aunque exista historia reciente en snapshots.

## Base auditada

La auditoría usa exactamente la misma base que el modelo avanzado:

- universo invertido actual desde `RiskContributionService`
- historia de `ActivoPortafolioSnapshot`
- consolidación diaria idéntica a `CovarianceService`

No usa `PortfolioSnapshot` como fuente principal porque la covarianza no se calcula sobre esa tabla.

## Qué responde

Para cada fecha del lookback devuelve:

- `assets_present`
- `expected_assets`
- `coverage_pct`
- `complete_after_ffill`
- `usable`
- `missing_symbols_count`

Además devuelve:

- `available_price_dates_count`
- `usable_observations_count`
- `missing_calendar_dates`

## Distinción clave

Una fecha puede:

- tener datos parciales
- quedar completa después de `ffill`
- pero seguir sin ser usable para retornos

Esto pasa cuando una serie recién aparece ese día: el precio existe, pero no hay precio previo válido para calcular retorno.

## Utilidad

La auditoría permite responder con precisión:

- si faltan días completos
- si faltan activos dentro de los días presentes
- si la pérdida de observaciones viene por cobertura parcial o por falta de precio previo usable

## Limitaciones

- usa el universo actual, no universos históricos cambiantes
- audita la base para covarianza, no para todas las métricas temporales del sistema
- no persiste resultados; es un diagnóstico puntual
