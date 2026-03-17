# Pipeline de datos

## Propósito

Explicar cómo entra la data al sistema, cómo se persiste y qué superficies dependen del pipeline operativo.

## Inputs

Fuentes principales:

- API de IOL
  - estado de cuenta
  - portafolio
  - operaciones
- Alpha Vantage
  - benchmarks históricos
- BCRA
  - USDARS oficial
  - BADLAR
- datos.gob.ar
  - IPC nacional
- fuentes JSON opcionales
  - USDARS MEP
  - riesgo país

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

- auditoría de sync IOL
- continuidad diaria de snapshots
- readiness para covarianza
- estado de benchmarks
- estado de macro local

## Superficies donde impacta

- `Resumen`
  - KPIs de portafolio y contexto macro
- `Estrategia`
  - composición
  - riesgo
  - Analytics v2
  - calidad de datos
- `Performance`
  - evolución histórica
  - benchmarking
  - comparación macro
- `Métricas`
  - volatility
  - returns
  - benchmarking
- `Planeación`
  - recomendaciones
  - simulación
  - optimización
- `Ops`
  - observabilidad del pipeline
  - acciones staff

## Cómo consumen los selectors

Patrón actual:

```text
models persistidos
  -> services
  -> apps/dashboard/selectors.py
  -> views server-rendered / APIs internas
```

Los selectors no deberían sincronizar ni persistir.
Su rol es consolidar outputs para UI.

## Estado actual / brechas

Estado actual:

- el pipeline patrimonial funciona extremo a extremo
- benchmarks y macro local tienen sync propio
- `Ops` ya muestra un resumen unificado del pipeline

Brechas:

- `last_successful_iol_sync` no tiene historial persistido de éxitos
- la historia útil para covarianza sigue dependiendo de continuidad real de snapshots
- algunas superficies todavía consumen observabilidad vía AJAX y no todo está unificado server-render

## Limitaciones actuales

- el pipeline depende de disponibilidad externa de IOL y proveedores de mercado/macro
- la integridad histórica no implica automáticamente suficiencia para covarianza
- la observabilidad del pipeline es operativa, no reemplaza monitoreo externo o alertado dedicado
