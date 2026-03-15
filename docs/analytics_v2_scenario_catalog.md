# Analytics v2 - Catalogo de Escenarios MVP

## Objetivo

Definir una fuente unica y cerrada de escenarios para `scenario analysis` en el MVP.

## Catalogo actual

- `spy_down_10`
- `spy_down_20`
- `tech_shock`
- `argentina_stress`
- `ars_devaluation`
- `em_stress`
- `usa_rates_up_200bps`

## Criterios de diseno

- nombres estables y serializables
- labels legibles para UI futura
- descripcion breve y auditable
- categoria explicita
- trazabilidad opcional hacia escenarios legacy cuando exista equivalencia razonable

## Reutilizacion con stress legacy

Cuando existe un escenario analiticamente cercano en `StressTestService`, el catalogo conserva:

- `legacy_mapping_key`

Eso permite:

- no duplicar naming sin necesidad
- reutilizar shocks legacy en futuras adaptaciones
- mantener trazabilidad metodologica

## Limitaciones

Este catalogo no define aun:

- magnitudes exactas de shock por activo
- canales de transmision detallados
- heuristicas de impacto

Eso corresponde a `3.2` y `3.3`.
