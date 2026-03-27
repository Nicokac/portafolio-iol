# Inventario de superficies Dashboard

## Objetivo

Este documento deja trazabilidad corta de que rutas y vistas del `dashboard` siguen teniendo valor real en UX, cuales quedaron como soporte tecnico y cuales hoy ya no tienen entrada visible en la interfaz principal.

Se uso para cerrar el modulo `E2 - Auditoria de funciones y vistas realmente usadas` del roadmap `ux_simplicity_v2`.

## Criterio de clasificacion

- `flujo principal`: visible y util para una decision real de compra, aporte o rebalanceo
- `secundaria`: visible, pero no primera prioridad de uso diario
- `experta`: visible desde una hoja avanzada, no desde la navegacion principal
- `staff visible`: disponible solo para staff con entrada visible
- `staff oculta`: existe en rutas y tests, pero ya no tiene boton o acceso visible en la UI actual
- `candidata a deprecacion`: hoy no agrega valor de producto proporcional a la superficie que mantiene

## Inventario actual

### Flujo principal

| Ruta | Vista | Estado | Evidencia |
|---|---|---|---|
| `dashboard:dashboard` | `ResumenView` | mantener | marca raiz del producto en [apps/dashboard/urls.py](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/apps/dashboard/urls.py) y navbar en [templates/base.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/base.html) |
| `dashboard:resumen` | `ResumenView` | mantener por ahora | entry visible en navbar y CTAs cruzados en [templates/dashboard/resumen.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/dashboard/resumen.html) |
| `dashboard:estrategia` | `DashboardView` | mantener | entry visible en navbar y hoja ejecutiva principal |
| `dashboard:planeacion` | `PlaneacionView` | mantener | entry visible en navbar y foco actual del flujo de aporte |

### Secundarias visibles

| Ruta | Vista | Estado | Evidencia |
|---|---|---|---|
| `dashboard:analisis` | `AnalisisView` | mantener como secundaria | visible en dropdown `Mas` en [templates/base.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/base.html) y unifica composición, performance y métricas |
| `dashboard:cartera_detalle` | `CarteraDetalleView` | mantener | visible desde `Estrategia` como extension operativa puntual |
| `dashboard:laboratorio` | `LaboratorioView` | mantener | visible desde `Planeacion` como superficie avanzada separada |
| `dashboard:riesgo_avanzado` | `RiesgoAvanzadoView` | mantener | visible desde `Estrategia` como unico entry point analitico profundo |

### Redirects de compatibilidad

| Ruta | Vista | Estado | Evidencia |
|---|---|---|---|
| `dashboard:performance` | `PerformanceView` | mantener como alias tecnico | redirige a `dashboard:analisis#analisis-performance` |
| `dashboard:metricas` | `MetricasView` | mantener como alias tecnico | redirige a `dashboard:analisis#analisis-metricas` |

### Expertas visibles desde hojas avanzadas

| Ruta | Vista | Estado | Evidencia |
|---|---|---|---|
| `dashboard:risk_contribution_detail` | `RiskContributionDetailView` | mantener como experta | link en [templates/dashboard/riesgo_avanzado.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/dashboard/riesgo_avanzado.html) |
| `dashboard:scenario_analysis_detail` | `ScenarioAnalysisDetailView` | mantener como experta | link en `riesgo_avanzado.html` |
| `dashboard:factor_exposure_detail` | `FactorExposureDetailView` | mantener como experta | link en `riesgo_avanzado.html` |
| `dashboard:stress_fragility_detail` | `StressFragilityDetailView` | mantener como experta | link en `riesgo_avanzado.html` |
| `dashboard:expected_return_detail` | `ExpectedReturnDetailView` | mantener como experta | link en `riesgo_avanzado.html` |

### Staff visibles

| Ruta | Vista | Estado | Evidencia |
|---|---|---|---|
| `dashboard:ops` | `OpsView` | mantener | visible para staff en dropdown de usuario |
| `dashboard:run_sync` | `RunSyncView` | mantener | boton visible para staff en [templates/dashboard/resumen.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/dashboard/resumen.html) |
| `dashboard:generate_snapshot` | `GenerateSnapshotView` | mantener | boton visible para staff en `resumen.html` |
| `dashboard:sync_local_macro` | `SyncLocalMacroView` | mantener | boton visible para staff en [templates/dashboard/ops.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/dashboard/ops.html) |
| `dashboard:refresh_iol_market_snapshot` | `RefreshIOLMarketSnapshotView` | mantener | boton visible para staff en `ops.html` y panel de market snapshot |
| `dashboard:sync_benchmarks` | `SyncBenchmarksView` | mantener | boton visible para staff en `ops.html` |

### Staff ocultas o migradas fuera del dashboard web

| Ruta | Vista | Estado actual | Observacion |
|---|---|---|---|
| `dashboard:sync_iol_historical_prices` | `SyncIOLHistoricalPricesView` | retirada | la capacidad se mantiene por `python manage.py sync_iol_historical_prices --statuses=missing` |
| `dashboard:sync_iol_historical_prices_partial` | `SyncIOLHistoricalPricesPartialView` | retirada | la capacidad se mantiene por `python manage.py sync_iol_historical_prices --statuses=partial` |
| `dashboard:sync_iol_historical_prices_retry_metadata` | `SyncIOLHistoricalPricesRetryMetadataView` | retirada | la capacidad se mantiene por `python manage.py sync_iol_historical_prices --statuses=unsupported --eligibility-reason-keys=title_metadata_unresolved` |

### Acciones del flujo de planeacion

Estas rutas no son navegacion, pero si sostienen el flujo actual y por eso deben mantenerse:

- `dashboard:save_incremental_proposal`
- `dashboard:promote_incremental_baseline`
- `dashboard:promote_incremental_backlog_front`
- `dashboard:reactivate_incremental_deferred_proposal`
- `dashboard:decide_incremental_proposal`
- `dashboard:bulk_decide_incremental_proposal`
- `dashboard:set_preferences`

Evidencia:

- formularios activos en [templates/dashboard/planeacion.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/dashboard/planeacion.html)
- formulario de preferencias activo en [templates/base.html](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/templates/base.html)

## Candidatos a deprecacion prioritaria

### 1. Acciones staff ocultas de historicos IOL

Rutas:

- `dashboard:sync_iol_historical_prices`
- `dashboard:sync_iol_historical_prices_partial`
- `dashboard:sync_iol_historical_prices_retry_metadata`

Resolucion:

- ya no forman parte del dashboard web
- la operacion se resuelve por management command
- si en el futuro hace falta una consola tecnica, conviene crearla fuera de la familia `dashboard`

Decision sugerida:

- `mantener en observacion corta`
- si nadie las usa en una iteracion mas, moverlas fuera del dashboard web

### 2. Alias doble de resumen

Rutas:

- `dashboard:dashboard`
- `dashboard:resumen`

Motivo:

- ambas sirven la misma vista `ResumenView`
- hoy no rompen UX, pero mantienen duplicidad de naming y routing

Decision sugerida:

- mantener por ahora
- en una iteracion futura elegir una ruta canonicamente visible y hacer redirect desde la otra

## Superficies que no son candidatas a retiro hoy

- `Riesgo avanzado` y sus cinco drilldowns
  - siguen teniendo entrada clara y coherente desde la nueva arquitectura
- `Laboratorio`
  - hoy es la contencion correcta para simulacion y optimizacion
- `Cartera detallada`
  - resuelve una necesidad real que ya no debe contaminar `Estrategia`
- `Ops`
  - ya no es sobredimensionada y mantiene un rol staff concreto

## Decisiones del modulo E2

- no retirar rutas del flujo principal en este modulo
- no tocar acciones de `Planeacion`, porque siguen activas y visibles
- documentar como primera poda futura las tres acciones ocultas de historicos IOL
- dejar explicitado que el dashboard ya diferencia:
  - producto principal
  - experto
  - staff tecnico
