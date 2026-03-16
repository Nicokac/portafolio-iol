# Señales locales de macro y carry

## Objetivo

Agregar una lectura local simple y explicable para carteras con peso relevante en Argentina, renta fija AR y liquidez en pesos.

## Inputs

- posiciones normalizadas actuales
- BADLAR privada
- IPC nacional
- USDARS oficial

## Output

- resumen local serializable
- señales estructuradas de:
  - carry real de liquidez en ARS
  - cobertura inflacionaria vía CER
  - concentración en soberanos locales

## Señales MVP

- `local_liquidity_real_carry_negative`
- `local_inflation_hedge_gap`
- `local_sovereign_risk_excess`

## Metodología

- `ars_liquidity_weight_pct`: peso de posiciones cash-like en ARS
- `cer_weight_pct`: peso de posiciones con sector `CER`
- `argentina_bond_weight_pct`: bonos con exposición Argentina
- `sovereign_bond_weight_pct`: posiciones con sector `Soberano`
- `badlar_real_carry_pct = BADLAR - IPC yoy`

## Limitaciones

- no usa riesgo país
- no usa MEP ni brecha cambiaria
- no usa break-even de inflación
- no separa hard dollar vs tasa fija local con una taxonomía más fina
