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

## Integracion con recomendaciones

Las senales locales no quedan solo como contexto descriptivo.

`RecommendationEngine` ya consume este output y lo traduce a recomendaciones accionables para:

- `local_fx_gap_high`
- `local_fx_gap_deteriorating`
- `local_fx_regime_tensioned`
- `local_fx_regime_divergent`
- `inflation_accelerating`
- `real_rate_negative`
- `local_country_risk_high`
- `local_country_risk_deteriorating`

Regla de priorizacion actual:

- el topico `FX local` se deduplica para evitar recomendaciones casi iguales
- si conviven varias senales FX, se prioriza:
  - `local_fx_regime_divergent`
  - `local_fx_regime_tensioned`
  - `local_fx_gap_deteriorating`
  - `local_fx_gap_high`

Esto busca que el motor emita la lectura mas informativa del contexto cambiario, no varias variaciones del mismo problema.

## Exposicion actual en producto

Las senales y el contexto local hoy se exponen en tres superficies distintas:

### Resumen

Lectura compacta de contexto local:

- `Riesgo pais Argentina`
- `Dolar financiero y regimen FX`
- `UVA y tasa real local`

Uso recomendado:

- chequeo rapido del entorno local antes de pasar a `Estrategia` o `Planeacion`

### Estrategia

Lectura mas analitica de macro local dentro de `Analytics v2`:

- `CCL`
- `Estado FX`
- `Spread MEP / CCL`
- `UVA anualizada 30d`
- `Tasa real BADLAR vs UVA`

Uso recomendado:

- entender si el contexto macro local cambia la lectura de retorno esperado, fragilidad o sensibilidad local

### Planeacion

Las senales nuevas no crean una pantalla propia.
Se integran dentro de `Diagnostico previo al aporte`.

Exposicion actual:

- el bloque distingue `Macro local FX/UVA`
- muestra la primera accion sugerida como lectura rapida
- sigue conviviendo con alertas y rebalanceo, pero con framing especifico para macro local

Uso recomendado:

- usarlo como filtro previo antes de ejecutar el aporte mensual, no como reemplazo del flujo principal de `Aportes`
