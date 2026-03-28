# Senales y recomendaciones

## Proposito

Explicar como se generan senales analiticas y como terminan convertidas en recomendaciones visibles en producto.

## Inputs

Fuentes de senales actuales:

- `RiskContributionService`
- `CovarianceAwareRiskContributionService`
- `ScenarioAnalysisService`
- `FactorExposureService`
- `StressFragilityService`
- `ExpectedReturnService`
- `LocalMacroSignalsService`
- `FinvizOpportunityWatchlistService` como capa complementaria de compra

Ademas, el engine combina recomendaciones legacy basadas en:

- liquidez
- concentracion geografica
- concentracion sectorial
- concentracion patrimonial
- revision de rendimiento

## Servicios principales

### Servicios analiticos

Cada servicio expone:

- calculo principal
- `build_recommendation_signals()`

Esas senales ya salen serializadas con:

- `signal_key`
- `severity`
- `title`
- `description`
- `affected_scope`
- `evidence`

### `RecommendationEngine`

Responsabilidades:

- combinar recomendaciones legacy y senales de `Analytics v2`
- incorporar overlays externos compatibles cuando agregan criterio de compra real
- mapear senales a formato de recomendacion visible
- sugerir acciones simples
- priorizar y deduplicar

## Flujo actual

```text
Servicios analytics_v2
  -> build_recommendation_signals()
  -> RecommendationEngine._analyze_analytics_v2()
  -> _map_signal_to_recommendation()
  -> _prioritize_recommendations()
  -> Planeacion / API de recomendaciones
```

Y en paralelo:

```text
Heuristicas legacy
  -> RecommendationEngine._analyze_liquidity()
  -> _analyze_geographic_concentration()
  -> _analyze_sector_concentration()
  -> _analyze_risk_profile()
  -> _analyze_performance()
  -> _analyze_finviz_buy_intelligence()
```

## Outputs

Formato final de recomendacion:

- `tipo`
- `prioridad`
- `titulo`
- `descripcion`
- `acciones_sugeridas`
- `impacto_esperado`
- `origen`
- `activos_sugeridos` cuando aplica
- `modelo_riesgo` cuando aplica

## Como llega a las superficies

### Planeacion

- consume recomendaciones combinadas
- mezcla legacy + `Analytics v2`
- muestra la lista priorizada para lectura tactica
- la recomendacion combinada convive con el workflow incremental de futuras compras, pero no lo reemplaza

### API

- `/api/recommendations/all/`
- `/api/recommendations/by-priority/`

### Estrategia

- no muestra la lista completa del engine
- si muestra senales resumidas en `Analytics v2`

## Casos relevantes ya implementados

### Risk Contribution

Senales como:

- `risk_concentration_top_assets`
- `risk_concentration_tech`
- `risk_concentration_argentina`
- `risk_vs_weight_divergence`
- `sector_risk_overconcentration`
- `country_risk_overconcentration`
- `country_risk_underconcentration`

### Macro local

Senales como:

- `local_liquidity_real_carry_negative`
- `local_inflation_hedge_gap`
- `local_country_risk_high`
- `local_sovereign_risk_excess`
- `local_sovereign_hard_dollar_dependence`
- `local_fx_gap_high`
- `local_fx_gap_deteriorating`
- `local_fx_regime_tensioned`
- `local_fx_regime_divergent`

## Priorizacion y deduplicacion

La deduplicacion actual vive en:

- `_recommendation_topic_key()`
- `_recommendation_specificity_rank()`
- `_prioritize_recommendations()`

Criterios actuales:

- preferir `Analytics v2` frente a heuristicas legacy cuando hablan del mismo topico
- preferir senales mas especificas frente a senales genericas
- usar `evidence` cuando hace falta distinguir si dos senales realmente hablan del mismo bloque

Ejemplos actuales:

- `country_risk_overconcentration` para Argentina gana sobre `risk_concentration_argentina`
- `sector_risk_overconcentration` para tecnologia gana sobre `risk_concentration_tech`
- `country_risk_underconcentration` se mantiene como senal informativa distinta
- los topicos locales se deduplican para reducir ruido entre riesgo soberano, cobertura CER y FX local

## Superficies donde impacta

- `Planeacion`
- endpoints de recomendaciones
- senales resumidas de `Estrategia`

## Estado actual y brechas

Estado actual:

- la app ya tiene una capa rica de senales de `Analytics v2`
- el engine ya deduplica varios solapamientos importantes
- las acciones sugeridas son simples y trazables
- el workflow incremental de futuras compras opera arriba de estas recomendaciones, sin duplicar el engine base
- Finviz ya puede entrar como recomendacion complementaria para sourcing o refuerzo cuando hay conviccion suficiente

Brechas:

- no existe una superficie dedicada para auditar todas las senales emitidas por corrida
- la explicacion de por que una senal gano sobre otra no se expone en UI
- la deduplicacion sigue siendo heuristica y puntual
- la integracion con `parking` y ejecucion reciente vive principalmente en `Planeacion`, no como recomendaciones persistidas de primer nivel

## Limitaciones actuales

- el engine no fusiona senales: elige una y descarta la otra por topico
- las recomendaciones no exponen toda la evidencia interna del servicio origen
- parte de la priorizacion depende de reglas manuales por `tipo`
