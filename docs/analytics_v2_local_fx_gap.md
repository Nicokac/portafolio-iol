## Objetivo

Extender la lectura local de Analytics v2 con una senal cambiaria simple, reutilizando la infraestructura actual de `MacroSeriesSnapshot`.

## Inputs

- posiciones normalizadas actuales
- `usdars_oficial`
- `usdars_mep`
- `usdars_ccl`
- referencias ya usadas por el modulo local:
  - `BADLAR`
  - `IPC`

## Outputs

`LocalMacroSignalsService.calculate()` agrega:

- `usdars_mep`
- `usdars_ccl`
- `usdars_financial`
- `fx_gap_pct`
- `fx_gap_mep_pct`
- `fx_gap_ccl_pct`
- `fx_mep_ccl_spread_pct`
- `fx_signal_state`
- `fx_gap_change_30d`
- `fx_gap_change_pct_30d`

`LocalMacroSignalsService.build_recommendation_signals()` puede agregar:

- `local_fx_gap_high`
- `local_fx_gap_deteriorating`
- `local_fx_regime_tensioned`
- `local_fx_regime_divergent`

## Algoritmo MVP

- si existen `usdars_oficial` y una referencia financiera disponible, calcula:
  - `fx_gap_pct = (financial / oficial - 1) * 100`
- si existen `MEP` y `CCL`, calcula ademas:
  - `fx_gap_mep_pct`
  - `fx_gap_ccl_pct`
  - `fx_mep_ccl_spread_pct`
  - `fx_signal_state`
- si existen referencias comparables con al menos 30 dias:
  - `fx_gap_change_30d`
  - `fx_gap_change_pct_30d`
- si la exposicion argentina es material y la brecha es alta:
  - genera una senal de sensibilidad cambiaria local
- si el regimen financiero local muestra tension o divergencia:
  - genera senales especificas de `FX regime`

## Fuente default actual

La app usa por default ArgentinaDatos para:

- `MEP`
  - `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- `CCL`
  - `https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui`

Campos usados:

- `venta`
- `fechaActualizacion`

## Limitaciones

- sigue siendo una lectura heuristica, no una mesa cambiaria ni un motor de arbitraje
- si falta `usdars_ccl`, la brecha puede seguir calculandose solo con `MEP`
- si falta `usdars_oficial`, la brecha deja de ser interpretable
- el deterioro usa una comparacion simple contra la ultima referencia disponible a 30 dias
