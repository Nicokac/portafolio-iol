# Analytics v2 - Arquitectura técnica

## Objetivo

Definir cómo se integra `Analytics v2` al proyecto actual sin romper `v1` y sin duplicar la capa de servicios ya existente.

## Problema arquitectonico

La aplicación ya tiene:

- servicios de riesgo
- servicios de performance
- benchmark compuesto
- snapshots historicos
- metadata por activo
- motor de recomendaciones
- dashboard server-rendered
- API interna para métricas

`Analytics v2` no debe crear otra arquitectura paralela.
Debe ubicarse como una extensión modular dentro de `apps/core/services`, con contratos serializables y consumo limpio desde dashboard y API.

## Arquitectura actual reutilizable

### Capa de datos existente

Fuentes actuales:

- `ActivoPortafolioSnapshot`
- `ResumenCuentaSnapshot`
- `PortfolioSnapshot`
- `PositionSnapshot`
- `ParametroActivo`
- `BenchmarkSnapshot`
- `MacroSeriesSnapshot`

### Capa de servicios existente

Namespaces actuales en `apps/core/services`:

- `risk/`
- `performance/`
- `liquidity/`
- `portfolio/`
- `market_data/`
- `data_quality/`
- servicios top-level como:
  - `temporal_metrics_service.py`
  - `benchmark_series_service.py`
  - `local_macro_series_service.py`
  - `recommendation_engine.py`
  - `rebalance_engine.py`

### Capa de consumo actual

- `apps/dashboard/views.py`
  - consume selectores y renderiza templates
- `apps/api/views.py`
  - expone endpoints JSON para metricas y planeacion
- `apps/dashboard/selectors.py`
  - arma KPIs y estructuras para vistas server-rendered

## Decision de arquitectura para v2

`Analytics v2` se integra como una subcarpeta dentro de `apps/core/services`:

```text
apps/core/services/analytics_v2/
```

No reemplaza servicios existentes de `v1`.
Convive con ellos y reutiliza sus salidas cuando es razonable.

## Estructura actual relevante

```text
apps/core/services/analytics_v2/
    __init__.py
    schemas.py
    helpers.py
    analytics_explanation_service.py
    risk_contribution_service.py
    covariance_risk_contribution_service.py
    scenario_analysis_service.py
    factor_exposure_service.py
    stress_fragility_service.py
    expected_return_service.py
```

## Rol de cada archivo

### `schemas.py`

Define estructuras de salida serializables y estables para v2.

Contenido esperado:

- payloads por activo
- payloads agregados por sector/pais/tipo
- metadata metodologica
- flags de calidad de datos
- resultados por escenario
- resultados por factor

### `helpers.py`

Contendra helpers puros y reutilizables.

Contenido esperado:

- normalizacion de pesos
- agregacion por buckets
- ordenamiento de top contributors
- manejo de faltantes y proxys
- banderas de confianza

No existe un `adapters.py` dedicado.
La adaptación hoy vive en servicios y helpers existentes, por ejemplo:

- `ScenarioAnalysisService._load_current_positions()`
- `RiskContributionService._load_current_invested_positions()`
- helpers de `analytics_v2/helpers.py`

### `risk_contribution_service.py`

Responsable del modulo MVP 1.

### `scenario_analysis_service.py`

Responsable del modulo MVP 2.

### `factor_exposure_service.py`

Responsable del modulo MVP 3.

### `stress_fragility_service.py`

Responsable del modulo MVP 4.

### `expected_return_service.py`

Responsable del modulo MVP 5.

## Servicios principales y responsabilidades

### `risk_contribution_service.py`

- cálculo MVP por activo
- agregación por sector, país y tipo
- señales base de riesgo y divergencia

### `covariance_risk_contribution_service.py`

- activa covarianza cuando la historia lo permite
- cae a `mvp_proxy` cuando no hay historia/cobertura suficiente
- reutiliza el builder de señales del servicio base

### `scenario_analysis_service.py`

- aplica shocks heurísticos cerrados
- produce impacto por activo, sector y país
- genera señales de vulnerabilidad

### `factor_exposure_service.py`

- clasifica posiciones por factor proxy
- agrega exposición clasificada
- genera señales factoriales

### `stress_fragility_service.py`

- combina escenarios extremos
- resume pérdida, sectores y activos vulnerables
- genera señales de fragilidad

### `expected_return_service.py`

- calcula baseline estructural por buckets
- usa benchmarks y macro local
- genera señales de retorno esperado

### `analytics_explanation_service.py`

- transforma resultados ya calculados en interpretación textual
- no recalcula modelos
- hoy cubre:
  - risk contribution
  - scenario analysis
  - factor exposure
  - stress fragility
  - expected return

## Contratos de integración

### Dashboard server-rendered

Patrón actual:

```text
services analytics_v2
  -> apps/dashboard/selectors.py
  -> views
  -> templates
```

Ejemplo concreto:

- `get_analytics_v2_dashboard_summary()`
  - resuelve el modelo activo de `Risk Contribution`
  - consulta escenarios, factores, stress, retorno esperado y macro local
  - agrega interpretaciones
  - devuelve un summary ya listo para `Estrategia`

### Drill-downs

- `get_risk_contribution_detail()`
  - reutiliza el mismo resultado activo que alimenta el resumen
  - agrega métricas derivadas de lectura, no del modelo
- `get_scenario_analysis_detail()`
  - reutiliza `ScenarioAnalysisService` y el catálogo de escenarios MVP
  - consolida tabla de escenarios, peor escenario y breakdown por activo/sector/país
  - alimenta `/estrategia/scenario-analysis/` sin recalcular lógica en la vista
- `get_factor_exposure_detail()`
  - reutiliza `FactorExposureService` y `AnalyticsExplanationService`
  - expone ranking por factor, factores subrepresentados y bloque de unknown assets
  - alimenta `/estrategia/factor-exposure/` sin recalcular exposiciones en la vista
- `get_stress_fragility_detail()`
  - reutiliza `StressFragilityService`, `StressCatalogService` y `AnalyticsExplanationService`
  - compara stresses cerrados del catálogo y expone el breakdown del stress más severo
  - alimenta `/estrategia/stress-fragility/` sin recalcular fragilidad en la vista

### RecommendationEngine

Patrón actual:

```text
services analytics_v2
  -> build_recommendation_signals()
  -> RecommendationEngine._analyze_analytics_v2()
  -> priorización / deduplicación
  -> Planeación
```

Regla:

- el cálculo vive en cada servicio
- el engine solo consume señales y decide priorización relativa

## Inputs

Principales insumos:

- `ActivoPortafolioSnapshot`
- `PortfolioSnapshot`
- `ParametroActivo`
- `BenchmarkSnapshot`
- `MacroSeriesSnapshot`

## Outputs

Outputs principales:

- payloads serializables por módulo
- señales analíticas para recomendaciones
- interpretaciones automáticas para UI
- summaries server-rendered para `Estrategia`

## Superficies donde impacta

- `Estrategia`
  - tarjetas resumen
  - señales analytics v2
  - drill-down de risk contribution
- `Planeación`
  - recomendaciones combinadas
- `Ops`
  - activación del modelo de riesgo
  - readiness histórica
- APIs internas existentes
  - algunas métricas siguen expuestas por endpoints legacy, no por endpoints dedicados `analytics-v2/*`

## Estado actual / brechas

Estado actual:

- la carpeta `analytics_v2/` ya concentra los módulos principales del sistema
- `Estrategia` ya consume un summary integrado con interpretaciones
- `RecommendationEngine` ya consume señales de `Analytics v2`
- existe drill-down de `Risk Contribution`

Brechas:

- no hay endpoints dedicados `analytics-v2/*`
- solo `Risk Contribution` tiene drill-down propio en UI
- algunos adapters siguen implícitos dentro de servicios y no en una capa separada
- la integración con `Planeación` ocurre por recomendaciones, no por vistas analíticas detalladas

## Limitaciones actuales

- parte de la arquitectura fue diseñada como MVP y todavía mezcla adaptación de datos dentro de algunos servicios
- no toda la analítica avanzada tiene superficie propia de exploración
- la trazabilidad de outputs en UI depende de selectors server-rendered más que de contratos API dedicados
