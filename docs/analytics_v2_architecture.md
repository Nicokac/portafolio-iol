# Analytics v2 - Arquitectura tecnica

## Objetivo

Definir como se integra `Analytics v2` al proyecto actual sin romper `v1` y sin duplicar la capa de servicios ya existente.

## Problema arquitectonico

La aplicacion ya tiene:

- servicios de riesgo
- servicios de performance
- benchmark compuesto
- snapshots historicos
- metadata por activo
- motor de recomendaciones
- dashboard server-rendered
- API interna para metricas

`Analytics v2` no debe crear otra arquitectura paralela.
Debe ubicarse como una extension modular dentro de `apps/core/services`, con contratos serializables y consumo limpio desde dashboard y API.

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

## Overlays externos compatibles

`Analytics v2` puede convivir con overlays externos de decision de compra siempre que:

- no reemplacen fuentes core de IOL
- no alteren la valuacion oficial del portafolio
- entren como capas complementarias y serializables

Caso actual alineado:

- `apps/core/services/finviz/`
  - mapping
  - fundamentals snapshot
  - buy score
  - portfolio overlay

Uso actual:

- `Planeacion`
  - shortlist externa de compra
- `Centro analitico`
  - overlay agregado de beta, valuation, quality y leverage

Regla:

- Finviz y overlays equivalentes complementan a `Analytics v2`, pero no se mezclan con sus metricas core sin dejar explicita la familia de señal.

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
- payloads agregados por sector, pais y tipo
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
La adaptacion hoy vive en servicios y helpers existentes, por ejemplo:

- `ScenarioAnalysisService._load_current_positions()`
- `RiskContributionService._load_current_invested_positions()`
- helpers de `analytics_v2/helpers.py`

### Servicios principales

- `risk_contribution_service.py`
  - calculo MVP por activo
  - agregacion por sector, pais y tipo
  - senales base de riesgo y divergencia
- `covariance_risk_contribution_service.py`
  - activa covarianza cuando la historia lo permite
  - cae a `mvp_proxy` cuando no hay historia o cobertura suficiente
  - reutiliza el builder de senales del servicio base
- `scenario_analysis_service.py`
  - aplica shocks heuristicos cerrados
  - produce impacto por activo, sector y pais
  - genera senales de vulnerabilidad
- `factor_exposure_service.py`
  - clasifica posiciones por factor proxy
  - agrega exposicion clasificada
  - genera senales factoriales
- `stress_fragility_service.py`
  - combina escenarios extremos
  - resume perdida, sectores y activos vulnerables
  - genera senales de fragilidad
- `expected_return_service.py`
  - calcula baseline estructural por buckets
  - usa benchmarks y macro local
  - genera senales de retorno esperado
- `analytics_explanation_service.py`
  - transforma resultados ya calculados en interpretacion textual
  - no recalcula modelos

## Contratos de integracion

### Dashboard server-rendered

Patron actual:

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

Ya existen drill-downs visibles para los cinco modulos principales:

- `get_risk_contribution_detail()`
- `get_scenario_analysis_detail()`
- `get_factor_exposure_detail()`
- `get_stress_fragility_detail()`
- `get_expected_return_detail()`

Regla comun:

- reutilizan servicios y summaries ya calculados
- agregan lectura y breakdown para UI
- no mueven logica analitica a la vista

### RecommendationEngine

Patron actual:

```text
services analytics_v2
  -> build_recommendation_signals()
  -> RecommendationEngine._analyze_analytics_v2()
  -> priorizacion / deduplicacion
  -> Planeacion
```

Regla:

- el calculo vive en cada servicio
- el engine solo consume senales y decide prioridad relativa

## Inputs principales

- `ActivoPortafolioSnapshot`
- `PortfolioSnapshot`
- `ParametroActivo`
- `BenchmarkSnapshot`
- `MacroSeriesSnapshot`

## Outputs principales

- payloads serializables por modulo
- senales analiticas para recomendaciones
- interpretaciones automaticas para UI
- summaries server-rendered para `Estrategia`

## Superficies donde impacta

- `Estrategia`
  - tarjetas resumen
  - senales Analytics v2
  - cinco drill-downs analiticos
- `Planeacion`
  - recomendaciones combinadas
  - diagnostico previo y workflow incremental de futuras compras
- `Ops`
  - activacion del modelo de riesgo
  - readiness historica
  - observabilidad de insumos macro y pipeline
- APIs internas existentes
  - algunas metricas siguen expuestas por endpoints legacy, no por endpoints dedicados `analytics-v2/*`

## Estado actual y brechas

Estado actual:

- la carpeta `analytics_v2/` ya concentra los modulos principales del sistema
- `Estrategia` ya consume un summary integrado con interpretaciones
- `RecommendationEngine` ya consume senales de `Analytics v2`
- los cinco modulos principales ya tienen drill-down propio en UI

Brechas:

- no hay endpoints dedicados `analytics-v2/*`
- algunos adapters siguen implicitos dentro de servicios y no en una capa separada
- la integracion con `Planeacion` ocurre sobre todo por recomendaciones y decision incremental, no por vistas analiticas dedicadas
- la documentacion operativa de rollout conviene mantenerse consolidada y no volver a fragmentarse en micro-notas

## Limitaciones actuales

- parte de la arquitectura fue pensada como MVP y todavia mezcla adaptacion de datos dentro de algunos servicios
- no toda la analitica avanzada tiene superficie API propia
- la trazabilidad de outputs en UI depende mas de selectors server-rendered que de contratos API dedicados
