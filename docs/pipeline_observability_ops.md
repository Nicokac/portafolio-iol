# Observabilidad del pipeline de datos

## Objetivo

Unificar en `Ops` un resumen operativo del pipeline sin recalcular metricas fuera de los servicios existentes.

## Reutilizacion aplicada

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
- `critical_local_macro_summary`
- `external_sources_status_summary`

## Integracion

La hoja `Ops` renderiza este resumen server-side como bloque superior, y mantiene debajo las tablas detalladas ya existentes.

Tambien expone un bloque de `Estado de fuentes externas` para health checks operativos de proveedores remotos. La primera fuente integrada es:

- `ArgentinaDatos` via `GET /v1/estado`

Ademas, `Ops` ahora destaca un bloque de `Series macro criticas para decision`.

Tambien expone un bloque de `Market snapshot puntual del portfolio` que reutiliza:

- `IOLHistoricalPriceService.get_current_portfolio_market_snapshot_rows()`
- `IOLAPIClient.get_titulo_market_snapshot()`
  - prioriza `CotizacionDetalle`
  - usa `Cotizacion` como fallback

Series incluidas:

- `usdars_oficial`
- `usdars_mep`
- `usdars_ccl`
- `badlar_privada`
- `ipc_nacional`
- `uva`
- `riesgo_pais_arg`

## Para que sirve el bloque critico

- detectar rapido faltantes que impactan decisiones reales
- separar el universo macro total de las series que hoy alimentan:
  - brecha FX
  - regimen FX
  - tasa real local
  - inflacion indexada
  - riesgo pais

Cada fila muestra:

- serie
- por que importa
- fuente
- rows persistidas
- ultima fecha
- estado

## Interpretacion operativa

- `Listo`: la serie esta disponible y usable para el contexto actual
- `Stale`: la serie existe, pero quedo vieja para una lectura operativa confiable
- `Sin configurar`: la serie es opcional y todavia no tiene fuente habilitada
- `Sin datos`: la serie deberia existir para la lectura esperada, pero hoy no tiene snapshots utiles

Lectura rapida recomendada:

- si faltan `usdars_mep` o `usdars_ccl`, la lectura FX queda parcial
- si falta `uva`, el sistema hace fallback de tasa real a `IPC`, pero pierde calidad para CER / inflacion indexada
- si falta `riesgo_pais_arg`, se deteriora la lectura de stress soberano local
- si falta `usdars_oficial`, la brecha FX deja de ser interpretable

## Accion recomendada

1. revisar `Estado de fuentes externas`
2. ejecutar `Sincronizar macro local`
3. verificar si la serie quedo en `Sin configurar`, `Stale` o `Sin datos`
4. recien despues revisar `Resumen`, `Estrategia` o `Planeacion`

Para validacion puntual de instrumentos IOL:

1. revisar `Market snapshot puntual del portfolio`
2. usar `Refrescar market snapshot IOL`
3. verificar:
   - precio
   - hora
   - cantidad de operaciones
   - puntas visibles
   - spread
4. si falta snapshot, distinguir entre:
   - `Sin snapshot`
   - `No elegible`
   - `Cotizacion fallback`

Notas operativas adicionales:

- el refresh persiste observaciones en `IOLMarketSnapshotObservation`
- si el proceso reinicia o el cache puntual vence, el dashboard recompone el payload desde esas observaciones persistidas
- `Sin libro visible` no implica fallo del refresh: puede significar que IOL devolvio precio puntual sin puntas utilizables

## Limitaciones

- `last_successful_iol_sync` se deriva del estado patrimonial de snapshots, no de una auditoria historica persistida
- los health checks externos son lecturas operativas del proveedor, no series persistidas de producto
- no reemplaza la observabilidad AJAX existente de metricas internas y state metrics
- el bloque critico no genera alertas automaticas ni remediation automatica
