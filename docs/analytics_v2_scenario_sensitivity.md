# Analytics v2 - Motor de Sensibilidad Heuristica

## Objetivo

Resolver, para cada activo normalizado y para cada `scenario_key` del catalogo MVP:

- multiplicador de shock
- canal de transmision

## Regla de diseno

El motor no calcula impacto final del portafolio.
Solo resuelve sensibilidad heuristica por activo.

## Reutilizacion de baseline legacy

Se reutiliza como baseline conceptual la logica ya presente en `StressTestService`:

- shock por equity
- shock por pais Argentina
- shock por tasas USA
- shock por USD

## Cobertura MVP actual

- `spy_down_10`
- `spy_down_20`
- `tech_shock`
- `argentina_stress`
- `ars_devaluation`
- `em_stress`
- `usa_rates_up_200bps`

## Limitaciones

- heuristico y no calibrado
- no incorpora correlaciones
- no modela efectos de segundo orden
- no distingue aun entre magnitudes finas por subindustria

## Siguiente paso

`3.3` debe usar este motor para calcular:

- impacto por activo
- impacto total
- agregaciones por sector y pais
