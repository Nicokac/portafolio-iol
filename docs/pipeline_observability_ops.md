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
- `ArgentinaDatosClient`

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
- `external_sources_status_summary`

## Integración

La hoja `Ops` renderiza este resumen server-side como bloque superior, y mantiene debajo las tablas detalladas ya existentes.

Tambien expone un bloque de `Estado de fuentes externas` para health checks operativos de proveedores remotos. La primera fuente integrada es:

- `ArgentinaDatos` via `GET /v1/estado`

## Limitaciones

- `last_successful_iol_sync` se deriva del estado patrimonial de snapshots, no de una auditoría histórica persistida
- los health checks externos son lecturas operativas del proveedor, no series persistidas de producto
- no reemplaza la observabilidad AJAX existente de métricas internas y state metrics
