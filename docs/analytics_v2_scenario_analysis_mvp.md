# Analytics v2 - Scenario Analysis MVP

## Objetivo

Calcular el impacto heuristico de un escenario MVP sobre las posiciones actuales del portafolio.

## Base de calculo

- posiciones actuales a valor de mercado
- excluye cash libre de cuenta fuera de `ActivoPortafolioSnapshot`
- incluye posiciones cash-like, pero con sensibilidad nula o muy baja segun el motor heuristico

## Salida

- impacto total
- impacto por activo
- impacto por sector
- impacto por pais
- top contribuidores negativos
- metadata metodologica

## Dependencias

- `ScenarioCatalogService`
- `ScenarioSensitivityService`
- `ParametroActivo`
- `ActivoPortafolioSnapshot`

## Limitaciones

- no modela correlaciones
- no modela efectos de segundo orden
- no incorpora cash libre de resumen de cuenta
- usa heuristicas de transmision, no calibracion estadistica
