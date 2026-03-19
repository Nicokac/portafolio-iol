# Senales locales de macro, carry y riesgo pais

## Objetivo

Agregar una lectura local simple y explicable para carteras con peso relevante en Argentina, renta fija AR y liquidez en pesos.

## Inputs

- posiciones normalizadas actuales
- BADLAR privada
- IPC nacional
- USDARS oficial
- USDARS MEP opcional
- USDARS CCL opcional
- riesgo pais Argentina opcional
- UVA opcional

## Output

- resumen local serializable
- senales estructuradas de:
  - carry real de liquidez en ARS
  - cobertura inflacionaria via CER
  - concentracion en soberanos locales
  - concentracion en un soberano puntual
  - sesgo del bloque local hacia hard dollar frente a CER
  - brecha cambiaria local
  - regimen FX local
  - aceleracion inflacionaria indexada
  - tasa real local contra UVA
  - riesgo pais alto con soberano local relevante

## Senales MVP

- `local_liquidity_real_carry_negative`
- `local_inflation_hedge_gap`
- `local_sovereign_risk_excess`
- `local_sovereign_single_name_concentration`
- `local_sovereign_hard_dollar_dependence`
- `local_fx_gap_high`
- `local_fx_gap_deteriorating`
- `local_fx_regime_tensioned`
- `local_fx_regime_divergent`
- `inflation_accelerating`
- `real_rate_negative`
- `local_country_risk_high`
- `local_country_risk_deteriorating`

## Metodologia

- `ars_liquidity_weight_pct`: peso de posiciones cash-like en ARS
- `cer_weight_pct`: peso de posiciones con sector `CER`
- `argentina_bond_weight_pct`: bonos con exposicion Argentina
- `sovereign_bond_weight_pct`: posiciones con sector `Soberano`
- `top_local_sovereign_symbol`: bono soberano local dominante
- `top_local_sovereign_share_pct`: peso del bono dominante dentro del bloque soberano local
- `local_sovereign_concentration_hhi`: concentracion interna del bloque soberano local
- `local_hard_dollar_share_pct`: split hard dollar dentro del bloque local hard dollar + CER
- `local_cer_share_pct`: split CER dentro del bloque local hard dollar + CER
- `badlar_real_carry_pct = BADLAR - IPC yoy`
- `usdars_financial`: promedio MEP/CCL si ambos existen; si no, la mejor referencia disponible
- `fx_gap_pct = (financial / oficial - 1) * 100`
- `fx_gap_mep_pct`: gap puntual contra MEP
- `fx_gap_ccl_pct`: gap puntual contra CCL
- `fx_mep_ccl_spread_pct`: divergencia relativa entre MEP y CCL
- `fx_signal_state`: `normal`, `tensioned` o `divergent`
- `fx_gap_change_30d`: cambio en puntos de la brecha contra la ultima referencia disponible con al menos 30 dias de lookback
- `fx_gap_change_pct_30d`: cambio porcentual sobre esa misma referencia
- `uva_change_pct_30d`: variacion de UVA a 30 dias
- `uva_annualized_pct_30d`: proxy anualizada de inflacion indexada sobre la trayectoria reciente de UVA
- `real_rate_badlar_vs_uva_30d = BADLAR - UVA anualizada 30d`
- `riesgo_pais_arg`: ultimo valor persistido de la serie local configurada
- `riesgo_pais_arg_change_30d`: cambio en puntos contra la ultima referencia disponible con al menos 30 dias de lookback
- `riesgo_pais_arg_change_pct_30d`: cambio porcentual sobre esa misma referencia

## Limitaciones

- no usa spreads soberanos por tramo
- no usa break-even de inflacion
- no separa hard dollar vs tasa fija local con una taxonomia mas fina
- MEP, CCL, UVA y riesgo pais solo se usan si la serie ya existe en `MacroSeriesSnapshot`
- el deterioro de brecha FX usa una comparacion simple contra la ultima observacion disponible a 30 dias, sin suavizados ni ventanas multiples
- el deterioro de riesgo pais usa una comparacion simple contra la ultima observacion disponible a 30 dias, sin suavizados ni ventanas multiples
