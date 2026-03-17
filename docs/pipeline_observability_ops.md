# Observabilidad del pipeline de datos

## Objetivo

Unificar en `Ops` un resumen operativo del pipeline sin recalcular métricas fuera de los servicios existentes.

## Reutilización aplicada

El consolidado reutiliza:

- `IOLSyncAuditService`
- `HistoricalCoverageHealthService`
- `SnapshotIntegrityService`
- `BenchmarkSeriesService`
- `LocalMacroSeriesService`

## Salida consolidada

`PipelineObservabilityService.build_summary()` expone al menos:

- `last_successful_iol_sync`
- `days_since_last_portfolio_snapshot`
- `latest_asset_snapshot_at`
- `latest_account_snapshot_at`
- `latest_portfolio_snapshot_date`
- `covariance_readiness`
- `usable_observations_count`
- `available_price_dates_count`
- `benchmark_status_summary`
- `local_macro_status_summary`

## Integración

La hoja `Ops` renderiza este resumen server-side como bloque superior, y mantiene debajo las tablas detalladas ya existentes.

## Limitaciones

- `last_successful_iol_sync` se deriva del estado patrimonial de snapshots, no de una auditoría histórica persistida
- no agrega endpoints nuevos
- no reemplaza la observabilidad AJAX existente de métricas internas y state metrics
