# Checklist de Exposición Feature por Feature - Toda la App

## Objetivo

Dejar un inventario operativo de la aplicación completa con estado de exposición por feature:

- `UI completa`
- `API-only`
- `No expuesta`

La meta no es listar archivos sin contexto, sino responder qué capacidades reales ya están disponibles para el usuario, cuáles viven solo por API y cuáles existen solo como backend o dependencia interna.

## Criterio usado

- `UI completa`: la feature ya tiene pantalla, bloque visible o acción usable desde la UI.
- `API-only`: la feature ya tiene endpoint funcional, pero no una superficie clara dentro de la UI actual.
- `No expuesta`: la feature existe en servicios/backend, pero no tiene ni pantalla ni endpoint funcional dedicado para consumo externo.

## Columnas

- `Área`: módulo funcional de la app.
- `Feature`: capacidad concreta.
- `Estado`: `UI completa` / `API-only` / `No expuesta`.
- `Superficie actual`: pantalla, acción o endpoint donde vive hoy.
- `Dependencias principales`: selector, servicio o motor principal reutilizado.
- `Observación`: lectura práctica del estado.

## Checklist

| Área | Feature | Estado | Superficie actual | Dependencias principales | Observación |
| --- | --- | --- | --- | --- | --- |
| Acceso | Login | UI completa | `users/login.html` | `RateLimitedLoginView` | Login con rate limit ya expuesto. |
| Salud | Health check | API-only | `/health/` | `apps.core.views.health_check` | Superficie técnica, no de usuario final. |
| Resumen | Hoja Resumen | UI completa | `/`, `/panel/resumen/` | `ResumenView`, selectors dashboard | Pantalla principal del producto. |
| Resumen | Contexto macro local resumido | UI completa | `Resumen` | `LocalMacroSeriesService`, selectors | Ya visible como bloque de contexto. |
| Estrategia | Hoja Estrategia | UI completa | `/estrategia/` | `DashboardView`, selectors | Superficie principal de lectura analítica. |
| Estrategia | Resumen ejecutivo de cartera | UI completa | `Estrategia` | `get_dashboard_kpis()` | KPIs visibles y operativos. |
| Estrategia | Calidad de datos resumida | UI completa | `Estrategia` | `/api/metrics/data-quality/`, `/api/metrics/snapshot-integrity/`, `/api/metrics/sync-audit/` | Se consume por fetch en la hoja. |
| Estrategia | Analytics v2 resumido | UI completa | `Estrategia` | `get_analytics_v2_dashboard_summary()` | Tarjetas, tabla resumen y señales visibles. |
| Estrategia | Risk contribution resumido | UI completa | `Estrategia` | `RiskContributionService`, `CovarianceAwareRiskContributionService` | Top activo, top sector y modelo activo visibles. |
| Estrategia | Interpretaciones automáticas de Risk Contribution | UI completa | `Estrategia` | `AnalyticsExplanationService`, selectors | Explica el modelo activo y el origen dominante del riesgo. |
| Estrategia | Scenario analysis resumido | UI completa | `Estrategia` | `ScenarioAnalysisService` | Se ve peor escenario comparando shocks clave. |
| Estrategia | Interpretaciones automáticas de Scenario Analysis | UI completa | `Estrategia` | `AnalyticsExplanationService`, selectors | Resume shock dominante y bloque más afectado. |
| Estrategia | Factor exposure resumido | UI completa | `Estrategia` | `FactorExposureService` | Se ve factor dominante y unknown assets. |
| Estrategia | Interpretaciones automáticas de Factor Exposure | UI completa | `Estrategia` | `AnalyticsExplanationService`, selectors | Explica factor dominante y activos sin clasificar. |
| Estrategia | Stress fragility resumido | UI completa | `Estrategia` | `StressFragilityService` | Se muestra score y pérdida estimada. |
| Estrategia | Interpretaciones automáticas de Stress Fragility | UI completa | `Estrategia` | `AnalyticsExplanationService`, selectors | Explica score, pérdida y sector vulnerable dominante. |
| Estrategia | Expected return resumido | UI completa | `Estrategia` | `ExpectedReturnService` | Se muestra retorno nominal/real esperado. |
| Estrategia | Interpretaciones automáticas de Expected Return | UI completa | `Estrategia` | `AnalyticsExplanationService`, selectors | Explica retorno estructural, bucket dominante y retorno real. |
| Estrategia | Macro local resumido | UI completa | `Estrategia` | `LocalMacroSignalsService` | Carry, CER, FX, riesgo país y perfil soberano local visibles. |
| Estrategia | Señales Analytics v2 | UI completa | `Estrategia` | servicios Analytics v2 combinados | Lista de señales ordenadas por severidad. |
| Estrategia | Risk contribution detallado por activo/sector/país | UI completa | `/estrategia/risk-contribution/` | `get_risk_contribution_detail()`, servicios de risk contribution | Drill-down visible con detalle por activo y agregados por sector/país. |
| Estrategia | Scenario analysis detallado | UI completa | `/estrategia/scenario-analysis/` | `get_scenario_analysis_detail()`, `ScenarioAnalysisService` | Drill-down visible con shocks, agregados y contribuyentes. |
| Estrategia | Factor exposure detallado | UI completa | `/estrategia/factor-exposure/` | `get_factor_exposure_detail()`, `FactorExposureService` | Drill-down visible con factores, dominancia y activos clasificados/unknown. |
| Estrategia | Stress fragility detallado | UI completa | `/estrategia/stress-fragility/` | `get_stress_fragility_detail()`, `StressFragilityService` | Drill-down visible con score, pérdidas y vulnerabilidad por bloque. |
| Estrategia | Expected return detallado | UI completa | `/estrategia/expected-return/` | `get_expected_return_detail()`, `ExpectedReturnService` | Drill-down visible con buckets, retorno nominal/real y composición esperada. |
| Análisis | Centro analítico | UI completa | `/analisis/` | `AnalisisView`, selectors dashboard + APIs métricas | Vista unificada de composición, performance y métricas cuantitativas. |
| Análisis | Distribución sectorial | UI completa | `Análisis` | `get_distribucion_sector()` | Visible en tablas/gráficos. |
| Análisis | Distribución geográfica | UI completa | `Análisis` | `get_distribucion_pais()` | Visible sobre bases distintas. |
| Análisis | Distribución patrimonial | UI completa | `Análisis` | `get_distribucion_tipo_patrimonial()` | Visible como lectura composicional. |
| Análisis | Riesgo detallado descriptivo | UI completa | `Análisis` | selectors dashboard | `% USA`, `% Argentina`, `% Tech`, liquidez, etc. |
| Análisis | Retornos históricos | UI completa | `Centro analítico` + `/api/metrics/returns/` | `TemporalMetricsService` | Visible en UI y expuesto por API. |
| Análisis | Comparación histórica por períodos | UI completa | `Centro analítico` + `/api/metrics/historical-comparison/` | `TemporalMetricsService` | Visible en UI y disponible por API. |
| Análisis | Evolución histórica | UI completa | `Centro analítico` + `/api/historical/evolution/` | `PortfolioSnapshot`, fallback histórico | Visible en UI y disponible por API. |
| Análisis | Comparación macro histórica | UI completa | `Centro analítico` + `/api/metrics/macro-comparison/` | `LocalMacroSeriesService` | Visible en UI y disponible por API. |
| Análisis | Curva vs benchmark compuesto | UI completa | `Centro analítico` + `/api/metrics/benchmark-curve/` | `TrackingErrorService` y benchmarking | Visible en UI y disponible por API. |
| Análisis | Volatilidad | UI completa | `Centro analítico` + `/api/metrics/volatility/` | `TemporalMetricsService` | Visible en UI y expuesto por API. |
| Análisis | Benchmarking | UI completa | `Centro analítico` + `/api/metrics/benchmarking/` | `TrackingErrorService` | Visible en UI y expuesto por API. |
| Análisis | Returns agregados | UI completa | `Centro analítico` + `/api/metrics/returns/` | `TemporalMetricsService` | Visible en UI y expuesto por API. |
| Análisis | Alias legacy `performance` | UI completa | `/analisis/performance/` | `PerformanceView` redirect | Alias de compatibilidad hacia `#analisis-performance`. |
| Análisis | Alias legacy `metricas` | UI completa | `/analisis/metricas/` | `MetricasView` redirect | Alias de compatibilidad hacia `#analisis-metricas`. |
| Métricas | VaR | API-only | `/api/metrics/var/` | `VaRService` | Hay endpoint, pero no hoja específica dedicada en UI actual. |
| Métricas | CVaR | API-only | `/api/metrics/cvar/` | `CVaRService` | Igual que VaR: endpoint sí, superficie UI dedicada no. |
| Métricas | Attribution | API-only | `/api/metrics/attribution/` | `AttributionService` | No aparece como bloque visible propio en UI actual. |
| Métricas | Liquidity metrics | API-only | `/api/metrics/liquidity/` | `LiquidityService` | Endpoint funcional, no hoja dedicada visible. |
| Planeación | Hoja Planeación | UI completa | `/planeacion/` | `PlaneacionView` + APIs | Superficie operativa para recomendaciones y simulación. |
| Planeación | Recomendaciones combinadas | UI completa | `Planeación` + `/api/recommendations/all/` | `RecommendationEngine` | Integra legacy + Analytics v2. |
| Planeación | Diagnóstico macro local FX/UVA | UI completa | `Planeación` + `/api/recommendations/all/` | `RecommendationEngine`, `LocalMacroSignalsService` | Visible dentro de `Diagnóstico previo` con rótulo `Macro local FX/UVA` y acción sugerida resumida. |
| Planeación | Recomendaciones por prioridad | API-only | `/api/recommendations/by-priority/` | `RecommendationEngine` | Endpoint útil, pero la UI usa el total combinado. |
| Planeación | Alertas activas | UI completa | `Planeación` + `/api/alerts/active/` | `AlertsEngine` | Visible y disponible por API. |
| Planeación | Alertas por severidad | API-only | `/api/alerts/by-severity/` | `AlertsEngine` | No hay control visible dedicado en UI. |
| Planeación | Sugerencias de rebalanceo | UI completa | `Planeación` + `/api/rebalance/suggestions/` | `RebalanceEngine` | Visible y funcional. |
| Planeación | Acciones críticas de rebalanceo | API-only | `/api/rebalance/critical/` | `RebalanceEngine` | Endpoint dedicado, no superficie separada clara. |
| Planeación | Acciones de oportunidad de rebalanceo | API-only | `/api/rebalance/opportunity/` | `RebalanceEngine` | Endpoint dedicado, no superficie separada clara. |
| Planeación | Simulación de compra | UI completa | `Planeación` + `/api/simulation/purchase/` | `PortfolioSimulator` | Accionable desde la UI. |
| Planeación | Simulación de venta | UI completa | `Planeación` + `/api/simulation/sale/` | `PortfolioSimulator` | Accionable desde la UI. |
| Planeación | Simulación de rebalanceo | UI completa | `Planeación` + `/api/simulation/rebalance/` | `PortfolioSimulator` | Accionable desde la UI. |
| Planeación | Propuesta de compra mensual incremental | UI completa | `Planeación` | `MonthlyAllocationService`, `get_monthly_allocation_plan()` | Traduce Analytics v2 y señales en bloques recomendados, montos y score explicable. |
| Planeación | Ranking de activos candidatos | UI completa | `Planeación` | `CandidateAssetRankingService`, `get_candidate_asset_ranking()` | Ordena activos existentes dentro de los bloques recomendados. |
| Planeación | Simulación incremental before/after | UI completa | `Planeación` | `IncrementalPortfolioSimulator`, `get_incremental_portfolio_simulation()` | Muestra impacto incremental simulado sobre expected return, fragilidad y peor escenario. |
| Planeación | Comparador de propuestas incrementales | UI completa | `Planeación` | selectors incrementales de dashboard | Contrasta variantes automáticas del mismo aporte mensual. |
| Planeación | Comparador incremental por candidato | UI completa | `Planeación` | selectors incrementales de dashboard | Compara top candidatos dentro de un mismo bloque recomendado. |
| Planeación | Comparador incremental por split de bloque | UI completa | `Planeación` | selectors incrementales de dashboard | Compara concentrar el bloque en un activo vs repartirlo entre los top 2. |
| Planeación | Comparador manual de planes incrementales | UI completa | `Planeación` | selectors incrementales de dashboard | Permite contrastar dos planes cargados manualmente en memoria. |
| Planeación | Propuesta incremental preferida | UI completa | `Planeación` | `get_preferred_incremental_portfolio_proposal()` | Sintetiza una única propuesta preferida entre los comparadores disponibles. |
| Planeación | Resumen ejecutivo unificado de decisión incremental | UI completa | `Planeación` | `get_incremental_decision_executive_summary()` | Resume si conviene adoptar, sostener baseline o revisar backlog antes de mover el aporte. |
| Planeación | Seguimiento operativo incremental | UI completa | `Planeación` | historial incremental, baseline y decisión manual | Expone baseline activo, última decisión y snapshots recientes con acciones visibles. |
| Planeación | Historial reciente de propuestas guardadas | UI completa | `Planeación` | `IncrementalProposalHistoryService`, `get_incremental_proposal_history()` | Historial operativo con filtros, decisiones manuales y acciones masivas sobre filas visibles. |
| Planeación | Shortlist unificada de futuras compras | UI completa | `Planeación` | selectors incrementales de dashboard | Unifica backlog nuevo y reactivadas para destacar que propuesta conviene reconsiderar primero. |
| Planeación | Workflow superior de futuras compras | UI completa | `Planeación` | selectors incrementales de dashboard | Expone fuente mas solida, propuesta `Recomendada ahora`, acciones directas y estado superior del workflow. |
| Planeación | Plan mensual custom | UI completa | `Planeación` + `/api/monthly-plan/custom/` | `MonthlyInvestmentPlanner` | Accionable desde la UI. |
| Planeación | Plan mensual básico | API-only | `/api/monthly-plan/basic/` | `MonthlyInvestmentPlanner` | Existe endpoint, no gatillo visible específico en la UI actual. |
| Planeación | Optimización risk parity | UI completa | `Planeación` + `/api/optimizer/risk-parity/` | `PortfolioOptimizer` | Accionable desde la UI. |
| Planeación | Optimización Markowitz | UI completa | `Planeación` + `/api/optimizer/markowitz/` | `PortfolioOptimizer` | Accionable desde la UI. |
| Planeación | Optimización target allocation | UI completa | `Planeación` + `/api/optimizer/target-allocation/` | `PortfolioOptimizer` | Accionable desde la UI. |
| Planeación | Lectura de parámetros de portafolio | UI completa | `Planeación` + `/api/portfolio/parameters/` | `PortfolioParameters` | Consumida por UI. |
| Planeación | Actualización de parámetros de portafolio | UI completa | `Planeación` + `/api/portfolio/parameters/update/` | `PortfolioParameters` | Consumida por UI staff. |
| Ops | Hoja Observabilidad | UI completa | `/ops/` | `OpsView` + servicios staff | Superficie operativa staff/expert. |
| Ops | Resumen unificado del pipeline de datos | UI completa | `Ops` | `PipelineObservabilityService` | Consolida sync IOL, snapshots, readiness de covarianza, benchmarks y macro local. |
| Ops | Series macro críticas para decisión | UI completa | `Ops` | `PipelineObservabilityService`, `LocalMacroSeriesService.get_status_summary()` | Destaca `USDARS oficial`, `MEP`, `CCL`, `BADLAR`, `IPC`, `UVA` y `riesgo país` como series operativas prioritarias. |
| Ops | Estado de benchmarks | UI completa | `Ops` | `BenchmarkSeriesService` | Visible en staff. |
| Ops | Observabilidad interna | UI completa | `Ops` + `/api/metrics/internal-observability/` | observabilidad interna | Visible y expuesta por API staff. |
| Ops | Estado de macro local | UI completa | `Ops` | `LocalMacroSeriesService.get_status_summary()` | Visible con series listas/stale/sin datos. |
| Ops | Continuidad diaria de snapshots | UI completa | `Ops` | `DailySnapshotContinuityService`, `SnapshotHistoryAuditService` | Visible por fecha con estado healthy/warning/broken. |
| Ops | Snapshot integrity | API-only | `/api/metrics/snapshot-integrity/` | `SnapshotIntegrityService` | También consumido indirectamente en `Estrategia`. |
| Ops | Sync audit | API-only | `/api/metrics/sync-audit/` | `IOLSyncAuditService` | También consumido indirectamente en `Estrategia`. |
| Ops | Data quality audit | API-only | `/api/metrics/data-quality/` | `MetadataAuditService` | También consumido indirectamente en `Estrategia`. |
| Ops | Auditoría histórica de snapshots | No expuesta | Sin superficie propia | `SnapshotHistoryAuditService` | Se usa como insumo, no como feature autónoma. |
| Ops | Resumen de salud histórica | No expuesta | Sin superficie propia | `HistoricalCoverageHealthService` | Backend reusable, no expuesto directo. |
| Operación staff | Actualizar IOL | UI completa | `/acciones/sync/` | `RunSyncView`, `IOLSyncService` | Acción manual staff visible. |
| Operación staff | Generar/refresh snapshot | UI completa | `/acciones/snapshot/` | `GenerateSnapshotView`, `PortfolioSnapshotService` | Acción manual staff visible. |
| Operación staff | Sincronizar benchmarks | UI completa | `/acciones/benchmarks/` | `SyncBenchmarksView`, `BenchmarkSeriesService` | Acción manual staff visible. |
| Operación staff | Sincronizar macro local | UI completa | `/acciones/macro-local/` | `SyncLocalMacroView`, `LocalMacroSeriesService` | Acción manual staff visible. |
| Preferencias | Ajuste de preferencias UI | UI completa | `/preferencias/` | `SetPreferencesView`, context processor | Superficie de preferencias existente. |
| Legacy CRUD | Lista de portafolio IOL | UI completa | `portafolio_iol/portafolio_list.html` | `PortafolioListView` | Vista legacy/listado. |
| Legacy CRUD | Lista de resumen IOL | UI completa | `resumen_iol/resumen_list.html` | `ResumenListView` | Vista legacy/listado. |
| Legacy CRUD | Lista de operaciones IOL | UI completa | `operaciones_iol/operaciones_list.html` | `OperacionesListView` | Vista legacy/listado. |
| Legacy CRUD | Lista de parámetros | UI completa | `parametros/parametros_list.html` | `ParametrosListView` | Vista legacy/listado. |
| API de Analytics v2 dedicada | Endpoints `analytics-v2/*` específicos | No expuesta | No existe | N/A | La arquitectura los contemplaba, pero no se implementaron. |

## Lectura rápida

### UI completa

La app ya expone en UI, de forma usable:

- Resumen
- Estrategia
- Análisis
- centro analítico unificado con performance y métricas
- Planeación
- Ops
- acciones staff de sincronización
- simuladores y optimizadores usados desde Planeación
- preferencias y vistas legacy/listados
- drill-downs de `Risk Contribution`, `Scenario Analysis`, `Factor Exposure`, `Stress Fragility` y `Expected Return`
- interpretaciones automáticas en tarjetas de `Analytics v2`
- resumen unificado del pipeline en `Ops`
- series macro criticas para decision en `Ops`
- motor incremental visible en `Planeación` con propuesta mensual, ranking de activos, simulación before/after y comparadores
- diagnostico macro local `FX/UVA` visible dentro de `Planeación`

### API-only

Hoy quedan principalmente como `API-only`:

- `VaR`
- `CVaR`
- `Attribution`
- `Liquidity metrics`
- `alerts/by-severity`
- `rebalance/critical`
- `rebalance/opportunity`
- `monthly-plan/basic`
- auditorías técnicas usadas indirectamente por UI (`snapshot-integrity`, `sync-audit`, `data-quality`)

### No expuesta

Hoy siguen sin superficie propia:

- endpoints dedicados `analytics-v2/*`
- auditoría histórica de snapshots como feature autónoma
- resumen de salud histórica como feature autónoma

## Conclusión

La app ya no es solo un dashboard descriptivo:

- tiene producto visible multi-hoja
- tiene planeación accionable
- tiene observabilidad staff
- tiene una capa API bastante amplia
- ya expone parte de `Analytics v2` con explicaciones e interpretación, no solo métricas crudas

La principal brecha ya no es “falta UI”, sino decidir si conviene abrir:

- endpoints dedicados por dominio
- o mayor trazabilidad operativa y analítica sin volver a sobrecargar `Planeación`
