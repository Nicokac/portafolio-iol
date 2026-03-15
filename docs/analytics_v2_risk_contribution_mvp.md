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

quedaban presentes en el contrato, pero vacios.

## Extension aplicada en 2.3

Se completo la agregacion de la salida por:

- sector
- pais
- tipo de activo

Regla usada:

- `contribution_pct` agregado = suma de `contribution_pct` de los items del bucket
- `weight_pct` agregado = suma de `weight_pct` de los items del bucket

Esto mantiene consistencia directa con el detalle por activo.

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

El siguiente paso natural queda en `2.4`:

- senales reutilizables para recomendaciones
