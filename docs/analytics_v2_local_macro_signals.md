# Senales locales de macro, carry y riesgo pais

## Objetivo

Agregar una lectura local simple y explicable para carteras con peso relevante en Argentina, renta fija AR y liquidez en pesos.

## Inputs

- posiciones normalizadas actuales
- BADLAR privada
- IPC nacional
- USDARS oficial
- USDARS MEP opcional
- riesgo pais Argentina opcional

## Output

- resumen local serializable
- senales estructuradas de:
  - carry real de liquidez en ARS
  - cobertura inflacionaria via CER
  - concentracion en soberanos locales
  - concentracion en un soberano puntual
  - sesgo del bloque local hacia hard dollar frente a CER
  - brecha cambiaria local
  - riesgo pais alto con soberano local relevante

## Senales MVP

- `local_liquidity_real_carry_negative`
- `local_inflation_hedge_gap`
- `local_sovereign_risk_excess`
- `local_sovereign_single_name_concentration`
- `local_sovereign_hard_dollar_dependence`
- `local_fx_gap_high`
- `local_country_risk_high`

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
- `fx_gap_pct = (MEP / oficial - 1) * 100`
- `riesgo_pais_arg`: ultimo valor persistido de la serie local configurada

## Limitaciones

- no usa spreads soberanos por tramo
- no usa CCL
- no usa break-even de inflacion
- no separa hard dollar vs tasa fija local con una taxonomia mas fina
- MEP y riesgo pais solo se usan si la serie ya existe en `MacroSeriesSnapshot`
