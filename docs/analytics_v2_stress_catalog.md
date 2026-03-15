# Analytics v2 - Catálogo de Stresses Extremos MVP

## Objetivo

Definir el conjunto cerrado de stresses extremos del MVP de `stress testing` ampliado,
reutilizando escenarios ya implementados y manteniendo trazabilidad con `StressTestService`.

## Stresses MVP

- `usa_crash_severe`
- `local_crisis_severe`
- `rates_equity_double_shock`
- `em_deterioration`

## Reutilización aplicada

El catálogo no redefine shocks desde cero. Se apoya en:

- `ScenarioCatalogService`
- `StressTestService`

Cada stress extremo referencia:

- `scenario_keys` de v2 ya existentes
- `legacy_mapping_keys` cuando existe equivalente razonable en v1

## Criterio de diseño

- `usa_crash_severe`: versión extrema del shock de equity USA
- `local_crisis_severe`: combina stress argentino y shock cambiario local
- `rates_equity_double_shock`: combina tasas USA y equity
- `em_deterioration`: stress concentrado en emergentes

## Limitaciones

- este módulo solo define el catálogo
- no calcula todavía pérdida, fragilidad ni agregaciones
- la combinación de escenarios queda para el siguiente módulo
