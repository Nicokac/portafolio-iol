# Exposicion local en dashboard

## Objetivo

Hacer visible una lectura local breve y reusable en `Estrategia` y `Resumen` sin mover logica macro al template.

## Integracion aplicada

- `get_analytics_v2_dashboard_summary()` incorpora `local_macro`
- `Estrategia` muestra:
  - card `Macro Local`
  - `Carry real BADLAR`
  - `Brecha FX`
  - `CCL`
  - `Estado FX`
  - `Spread MEP / CCL`
  - `UVA anualizada 30d`
  - `Tasa real BADLAR vs UVA`
  - peso Argentina
  - cobertura CER

## Datos mostrados

- `badlar_real_carry_pct`
- `usdars_ccl`
- `fx_gap_pct`
- `fx_mep_ccl_spread_pct`
- `fx_signal_state`
- `uva_annualized_pct_30d`
- `real_rate_badlar_vs_uva_30d`
- `argentina_weight_pct`
- `cer_weight_pct`
- `confidence`

## Limitaciones

- no agrega grafico propio de FX o UVA
- no crea una vista nueva
- usa la lectura heuristica del servicio local ya implementado

## Macro local en Resumen

`Resumen` ahora expone dentro del bloque de contexto macro local:

- `Riesgo pais Argentina`
- `Dolar financiero y regimen FX`
- `UVA y tasa real local`

Reglas de integracion:

- reutiliza `LocalMacroSeriesService.get_context_summary()`
- consume `riesgo_pais_arg` y `riesgo_pais_arg_date`
- consume `riesgo_pais_arg_change_30d` y `riesgo_pais_arg_change_pct_30d`
- consume `usdars_financial`, `fx_gap_pct`, `fx_mep_ccl_spread_pct` y `fx_signal_state`
- consume `uva_annualized_pct_30d` y `real_rate_badlar_vs_uva_30d`
- muestra la referencia como dato operativo breve
- documenta la fuente actual como `ArgentinaDatos` para riesgo pais y `UVA`
