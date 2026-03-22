# Analytics v2 - Local Macro Operating Model

## Objetivo

Consolidar la lectura local de macro, carry, FX y riesgo soberano en un unico documento operativo.

## Universo funcional

La capa local esta pensada para carteras con peso relevante en:

- liquidez ARS
- CER
- renta fija local
- soberanos hard dollar
- exposicion Argentina en general

## Inputs principales

- `badlar_privada`
- `ipc_nacional`
- `usdars_oficial`
- `usdars_mep`
- `usdars_ccl`
- `uva`
- `riesgo_pais_arg`
- posiciones normalizadas actuales

## Outputs principales

- carry real de liquidez ARS
- cobertura inflacionaria via CER
- brecha FX y regimen cambiario
- tasa real BADLAR vs UVA
- riesgo soberano local agregado
- concentracion local en soberanos
- senales locales de recomendacion

## Senales estructuradas vigentes

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

## Superficies actuales

### Resumen

Chequeo operativo breve de:

- riesgo pais
- dolar financiero y regimen FX
- UVA y tasa real local

### Estrategia

Lectura analitica ampliada de:

- carry real BADLAR
- brecha FX
- CCL
- spread MEP / CCL
- UVA anualizada 30d
- tasa real BADLAR vs UVA
- peso Argentina y cobertura CER

### Planeacion

Integracion dentro de `Diagnostico previo al aporte` como filtro tactico previo a mover capital.

### Ops

Estado operativo de series macro criticas para decision:

- `usdars_oficial`
- `usdars_mep`
- `usdars_ccl`
- `badlar_privada`
- `ipc_nacional`
- `uva`
- `riesgo_pais_arg`

## Priorizacion de recomendaciones

La deduplicacion local busca reducir ruido cuando varias senales describen el mismo problema argentino.

Preferencias ya usadas:

- `local_country_risk_high` sobre `local_sovereign_risk_excess`
- `local_sovereign_hard_dollar_dependence` sobre `local_inflation_hedge_gap`

## Brechas deliberadas

Todavia no se integran spreads soberanos locales por bono.

Se mantiene solo:

- riesgo pais agregado
- concentracion interna del bloque soberano local
- lectura por bono dominante usando datos internos

## Limitaciones

- lectura heuristica y explicable, no modelo macro cuantitativo complejo
- comparaciones a 30 dias simples, sin suavizados avanzados
- calidad dependiente de la disponibilidad de las series locales

## Documentacion archivada relacionada

La evolucion de esta familia queda preservada en `docs/archive/local-macro/`.
