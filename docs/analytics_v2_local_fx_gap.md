## Objetivo

Extender la lectura local de Analytics v2 con una señal cambiaria simple, reutilizando la infraestructura actual de `MacroSeriesSnapshot`.

## Inputs

- posiciones normalizadas actuales
- `usdars_oficial`
- `usdars_mep` opcional
- referencias ya usadas por el modulo local:
  - `BADLAR`
  - `IPC`

## Outputs

`LocalMacroSignalsService.calculate()` agrega:

- `usdars_mep`
- `fx_gap_pct`
- `fx_gap_change_30d`
- `fx_gap_change_pct_30d`

`LocalMacroSignalsService.build_recommendation_signals()` puede agregar:

- `local_fx_gap_high`
- `local_fx_gap_deteriorating`

## Algoritmo MVP

- si existen `usdars_oficial` y `usdars_mep`, calcula:
  - `fx_gap_pct = (mep / oficial - 1) * 100`
- si existen referencias comparables con al menos 30 dias:
  - `fx_gap_change_30d`
  - `fx_gap_change_pct_30d`
- si la exposicion argentina es material y la brecha es alta:
  - genera una señal de sensibilidad cambiaria local
- si la brecha viene ampliandose con fuerza:
  - genera una señal simple de deterioro reciente

## Limitaciones

- no agrega un sync nuevo para `usdars_mep`
- no usa CCL, riesgo pais ni spreads soberanos
- si `usdars_mep` no existe en `MacroSeriesSnapshot`, el modulo sigue funcionando y deja `fx_gap_pct = None`
- el deterioro usa una comparacion simple contra la ultima referencia disponible a 30 dias
