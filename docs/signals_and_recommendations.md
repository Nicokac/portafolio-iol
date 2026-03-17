# Señales y recomendaciones

## Propósito

Explicar cómo se generan señales analíticas y cómo terminan convertidas en recomendaciones visibles en producto.

## Inputs

Fuentes de señales actuales:

- `RiskContributionService`
- `CovarianceAwareRiskContributionService`
- `ScenarioAnalysisService`
- `FactorExposureService`
- `StressFragilityService`
- `ExpectedReturnService`
- `LocalMacroSignalsService`

Además, el engine combina recomendaciones legacy basadas en:

- liquidez
- concentración geográfica
- concentración sectorial
- concentración patrimonial
- revisión de rendimiento

## Servicios principales

### Servicios analíticos

Cada servicio expone:

- cálculo principal
- `build_recommendation_signals()`

Esas señales ya salen serializadas con:

- `signal_key`
- `severity`
- `title`
- `description`
- `affected_scope`
- `evidence`

### `RecommendationEngine`

Responsabilidades:

- combinar recomendaciones legacy y señales de `Analytics v2`
- mapear señales a formato de recomendación visible
- sugerir acciones simples
- priorizar y deduplicar

## Flujo actual

```text
Servicios analytics_v2
  -> build_recommendation_signals()
  -> RecommendationEngine._analyze_analytics_v2()
  -> _map_signal_to_recommendation()
  -> _prioritize_recommendations()
  -> Planeación / API de recomendaciones
```

Y en paralelo:

```text
Heurísticas legacy
  -> RecommendationEngine._analyze_liquidity()
  -> _analyze_geographic_concentration()
  -> _analyze_sector_concentration()
  -> _analyze_risk_profile()
  -> _analyze_performance()
```

## Outputs

Formato final de recomendación:

- `tipo`
- `prioridad`
- `titulo`
- `descripcion`
- `acciones_sugeridas`
- `impacto_esperado`
- `origen`
- `activos_sugeridos` cuando aplica
- `modelo_riesgo` cuando aplica

## Cómo llega a las superficies

### Planeación

- consume recomendaciones combinadas
- mezcla legacy + `Analytics v2`
- muestra la lista priorizada para lectura táctica

### API

- `/api/recommendations/all/`
- `/api/recommendations/by-priority/`

### Estrategia

- no muestra la lista completa del engine
- sí muestra señales resumidas en `Analytics v2`

## Casos relevantes ya implementados

### Risk Contribution

Señales como:

- `risk_concentration_top_assets`
- `risk_concentration_tech`
- `risk_concentration_argentina`
- `risk_vs_weight_divergence`
- `sector_risk_overconcentration`
- `country_risk_overconcentration`
- `country_risk_underconcentration`

### Macro local

Señales como:

- `local_liquidity_real_carry_negative`
- `local_inflation_hedge_gap`
- `local_country_risk_high`
- `local_sovereign_risk_excess`
- `local_sovereign_hard_dollar_dependence`

## Priorización y deduplicación

La deduplicación actual vive en:

- `_recommendation_topic_key()`
- `_recommendation_specificity_rank()`
- `_prioritize_recommendations()`

Criterios actuales:

- preferir `Analytics v2` frente a heurísticas legacy cuando hablan del mismo tópico
- preferir señales más específicas frente a señales genéricas
- usar `evidence` cuando hace falta distinguir si dos señales realmente hablan del mismo bloque

Ejemplos actuales:

- `country_risk_overconcentration` para Argentina gana sobre `risk_concentration_argentina`
- `sector_risk_overconcentration` para tecnología gana sobre `risk_concentration_tech`
- `country_risk_underconcentration` se mantiene como señal informativa distinta

## Superficies donde impacta

- `Planeación`
- endpoints de recomendaciones
- señales resumidas de `Estrategia`

## Estado actual / brechas

Estado actual:

- la app ya tiene una capa rica de señales de `Analytics v2`
- el engine ya deduplica varios solapamientos importantes
- las acciones sugeridas son simples y trazables

Brechas:

- no existe una superficie dedicada para auditar todas las señales emitidas por corrida
- la explicación de por qué una señal ganó sobre otra no se expone en UI
- la deduplicación sigue siendo heurística y puntual

## Limitaciones actuales

- el engine no fusiona señales: elige una y descarta la otra por tópico
- las recomendaciones no exponen toda la evidencia interna del servicio origen
- parte de la priorización depende de reglas manuales por `tipo`
