# Covariance-aware risk contribution MVP acotado

## Objetivo

Agregar una variante avanzada de `risk contribution` que use covarianza solo cuando la historia diaria y la cobertura del portafolio sean suficientes.

## Regla principal

- si la historia y la cobertura alcanzan: `model_variant = covariance_aware`
- si no alcanzan: fallback explicito a `RiskContributionService` MVP con `model_variant = mvp_proxy`

## Condiciones minimas actuales

- al menos 20 observaciones de retornos diarios
- al menos 3 activos cubiertos
- cobertura patrimonial suficiente del universo invertido
- volatilidad de portafolio positiva y matriz usable

## Salida adicional

El servicio expone, ademas del contrato base:

- `model_variant`
- `covariance_observations`
- `portfolio_volatility_proxy`
- `coverage_pct`
- `covered_symbols`
- `excluded_symbols`

## Limites deliberados

- no mezcla covarianza con activos uncovered dentro del mismo score
- si la cobertura no alcanza, cae al MVP
- no reemplaza todavia al servicio actual consumido por producto
