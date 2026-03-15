# Analytics v2 - Risk Contribution MVP

## Objetivo

Implementar la primera salida ejecutable de `risk contribution` por activo, manteniendo el algoritmo definido en `docs/analytics_v2_risk_contribution_design.md`.

## Inputs

- posiciones actuales desde `ActivoPortafolioSnapshot`
- metadata por simbolo desde `ParametroActivo`
- historico por simbolo desde snapshots del portafolio

## Output del modulo 2.2

- `items`
- `top_contributors`
- `metadata`

En esta etapa:

- `by_sector`
- `by_country`
- `by_asset_type`

quedan presentes en el contrato, pero vacios, porque la agregacion se completa en `2.3`.

## Reglas MVP implementadas

- base economica: `portafolio invertido`
- exclusion de:
  - caucion
  - FCI de cash management
- `volatility_proxy` con prioridad:
  1. historico propio del activo
  2. fallback por tipo de activo
- liquidez operativa no entra en el universo elegible

## Limitaciones

- no usa covarianza
- no usa betas
- no usa agregacion completa por sector/pais/tipo
- los fallbacks por asset class son heuristicas controladas

## Extension inmediata prevista

`2.3` debe completar:

- agregacion por sector
- agregacion por pais
- agregacion por tipo de activo
