# Pipeline de datos

## Proposito

Explicar como entra la data al sistema, como se persiste y que superficies dependen del pipeline operativo.

Complemento recomendado:

- `docs/iol_endpoint_usage_map.md`
  - explica endpoint por endpoint de IOL
  - detalla donde se usa cada uno
  - ayuda a detectar subaprovechamiento del contrato

## Inputs

Fuentes principales:

- API de IOL
  - estado de cuenta
  - portafolio
  - operaciones
  - metadata de titulos y FCI
  - cotizacion puntual y cotizacion detalle
  - serie historica por simbolo
- Alpha Vantage
  - benchmarks historicos
- BCRA
  - USDARS oficial
  - BADLAR
- datos.gob.ar
  - IPC nacional
- fuentes JSON opcionales
  - USDARS MEP
  - riesgo pais

## Servicios principales

### Sync IOL

- `IOLSyncService`
- `PortfolioSnapshotService`
- `IOLSyncAuditService`

Flujo:

```text
IOL API
  -> IOLSyncService.sync_estado_cuenta()
  -> ResumenCuentaSnapshot

IOL API
  -> IOLSyncService.sync_portafolio()
  -> ActivoPortafolioSnapshot

IOL API
  -> IOLSyncService.sync_operaciones()
  -> OperacionIOL

IOL API
  -> IOLHistoricalPriceService.sync_symbol_history()
  -> IOLHistoricalPriceSnapshot

IOL API
  -> IOLHistoricalPriceService.resolve_symbol_history_support()
  -> metadata de titulo / FCI / market snapshot puntual

sync_all()
  -> PortfolioSnapshotService.generate_daily_snapshot()
  -> PortfolioSnapshot / PositionSnapshot
```

### Benchmarks

- `BenchmarkSeriesService`
- `AlphaVantageClient`

Flujo:

```text
Alpha Vantage
  -> BenchmarkSeriesService.sync_all()
  -> BenchmarkSnapshot
```

### Macro local

- `LocalMacroSeriesService`
- `BCRAClient`
- `DatosGobSeriesClient`
- `FXJSONClient`

Flujo:

```text
BCRA / datos.gob.ar / FX JSON
  -> LocalMacroSeriesService.sync_all()
  -> MacroSeriesSnapshot
```

### Salud operativa

- `SnapshotHistoryAuditService`
- `DailySnapshotContinuityService`
- `HistoricalCoverageHealthService`
- `SnapshotIntegrityService`
- `PipelineObservabilityService`

## Outputs

Persistencia principal:

- `ResumenCuentaSnapshot`
- `ActivoPortafolioSnapshot`
- `PortfolioSnapshot`
- `PositionSnapshot`
- `OperacionIOL`
- `BenchmarkSnapshot`
- `MacroSeriesSnapshot`

Salidas operativas:

- auditoria de sync IOL
- continuidad diaria de snapshots
- readiness para covarianza
- estado de benchmarks
- estado de macro local
- market snapshot puntual para validacion operativa en `Ops`

## Superficies donde impacta

- `Resumen`
  - KPIs de portafolio y contexto macro
  - chequeo tactico de `parking` visible en cartera
- `Estrategia`
  - composicion
  - riesgo
  - Analytics v2
  - calidad de datos
- `Performance`
  - evolucion historica
  - benchmarking
  - comparacion macro
- `Metricas`
  - volatility
  - returns
  - benchmarking
- `Planeacion`
  - recomendaciones
  - simulacion
  - optimizacion
  - lectura historica corta de ejecucion reciente desde `CotizacionDetalle` para decidir compras futuras con mejor spread/libro/actividad
  - degradacion de shortlist y propuesta sugerida cuando la ejecucion reciente del bloque viene debil
  - degradacion de `score` y `confidence` cuando esa friccion reciente sigue activa
  - chequeo tactico de `parking` antes de decidir despliegue
  - señal tactica de `parking` dentro de `Modo decision`
  - compuerta de ejecucion cuando `parking` sigue visible
  - recomendacion condicionada cuando el bloque sugerido se superpone con posiciones en `parking`
  - shortlist sugerida degradada cuando el candidato cae en un bloque con `parking`
  - shortlist reordenada para priorizar candidatos sin `parking` visible
  - propuesta preferida condicionada cuando su plan cae en bloques con `parking`
  - propuesta preferida sustituida por una alternativa limpia cuando el overlap con `parking` es evitable
  - `score` y `confidence` degradados cuando persiste `parking` visible
- `Portafolio`
  - lectura visible de `parking` por activo
  - valorizado y disponible inmediato sobre la hoja actual
- `Operaciones`
  - filtros locales y sync remoto contra IOL
  - enriquecimiento batch de detalle y backfill de `pais_consulta`
  - auditoria operativa visible sobre acciones recientes
  - metricas historicas de ejecucion y costo sobre el subset filtrado
  - comparacion operativa entre compras, ventas, dividendos y flujos FCI
- `Ops`
  - observabilidad del pipeline
  - acciones staff
  - validacion puntual de market snapshot IOL

## Como consumen los selectors

Patron actual:

```text
models persistidos
  -> services
  -> apps/dashboard/selectors.py
  -> views server-rendered / APIs internas
```

Los selectors no deberian sincronizar ni persistir.
Su rol es consolidar outputs para UI.

## Estado actual / brechas

Estado actual:

- el pipeline patrimonial funciona extremo a extremo
- benchmarks y macro local tienen sync propio
- `Ops` ya muestra un resumen unificado del pipeline
- `Ops` tambien puede validar market snapshot puntual del portfolio actual

Brechas:

- `last_successful_iol_sync` no tiene historial persistido de exitos
- la historia util para covarianza sigue dependiendo de continuidad real de snapshots
- algunas superficies todavia consumen observabilidad via AJAX y no todo esta unificado server-render

## Limitaciones actuales

- el pipeline depende de disponibilidad externa de IOL y proveedores de mercado/macro
- la integridad historica no implica automaticamente suficiencia para covarianza
- la observabilidad del pipeline es operativa, no reemplaza monitoreo externo o alertado dedicado
