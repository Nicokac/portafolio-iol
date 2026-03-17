# Analytics v2 - Drill-down de Risk Contribution

## Objetivo

Exponer una superficie de lectura detallada del calculo de `Risk Contribution` sin reimplementar el modelo ni mover logica analitica a la vista.

## Reutilizacion aplicada

- `RiskContributionService`
- `CovarianceAwareRiskContributionService`
- `get_analytics_v2_dashboard_summary()` como referencia del criterio de seleccion del modelo activo

## Contrato del selector

`get_risk_contribution_detail()` devuelve:

- `items`
  - `rank`
  - `symbol`
  - `sector`
  - `country`
  - `asset_type`
  - `weight_pct`
  - `volatility_proxy`
  - `risk_score`
  - `contribution_pct`
  - `used_volatility_fallback`
- `top_asset`
- `top_sector`
- `model_variant`
- `covariance_observations`
- `coverage_pct`
- `portfolio_volatility_proxy`
- `confidence`
- `warnings`
- `methodology`
- `limitations`
- `covered_symbols`
- `excluded_symbols`

## UI

Nueva superficie:

- `/estrategia/risk-contribution/`

La hoja muestra:

- metadata del modelo activo
- top activo y cobertura
- tabla completa por activo
- barra visual simple de contribucion

## Limitaciones

- no agrega endpoint API nuevo
- no agrega drill-down por sector o pais
- no cambia el algoritmo del modelo
- no cambia la decision entre `mvp_proxy` y `covariance_aware`
