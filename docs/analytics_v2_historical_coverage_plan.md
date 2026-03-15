## Objetivo

Definir cómo pasar de la situación actual:

- `6` fechas diarias útiles
- `5` retornos utilizables en `30` días

a una base donde `covariance_aware` pueda activarse con regularidad.

## Reutilización aplicada

Se usaron componentes ya existentes:

- `PortfolioSnapshotService`
- `IOLSyncService`
- `SnapshotHistoryAuditService`
- `IOLSyncAuditService`
- `setup_periodic_tasks`

Además se agregó un resumen operativo reusable:

- `HistoricalCoverageHealthService`

## Diagnóstico técnico

### 1. Causa dominante

La causa principal no es la deduplicación.

La causa principal es la baja continuidad de días con sync útil reciente de `ActivoPortafolioSnapshot`.

Base real observada:

- `33` símbolos esperados
- `6` fechas con matriz diaria de precios
- `5` retornos utilizables

### 2. Causa secundaria

Existen fechas con `ActivoPortafolioSnapshot` reciente pero sin `PortfolioSnapshot`:

- `2026-03-08`
- `2026-03-10`
- `2026-03-11`
- `2026-03-12`

Esto sugiere una de estas dos cosas:

- hubo sync de portafolio pero no se ejecutó o no completó la generación de snapshot diario
- o parte de la carga reciente ingresó por un camino que no consolidó `PortfolioSnapshot`

### 3. Scheduler

Las tareas periódicas requeridas existen y están habilitadas:

- `core.sync_portfolio_data`
- `core.generate_daily_snapshot`

Por lo tanto, el problema no parece ser ausencia de configuración.

La brecha probable está en ejecución efectiva o fallos operativos de sync.

### 4. Señal operativa adicional

El `IOLSyncAuditService` mostró:

- token expirado
- operaciones stale

Eso no explica por sí solo todas las fechas faltantes, pero sí confirma fragilidad operativa reciente.

## Métricas operativas de salud histórica

El módulo deja definidas estas métricas mínimas:

- `expected_symbols_count`
- `available_price_dates_count`
- `usable_observations_count`
- `missing_calendar_dates_count`
- `complete_price_dates_count`
- `asset_days_without_portfolio_snapshot`
- `latest_asset_snapshot_at`
- `latest_account_snapshot_at`
- `latest_portfolio_snapshot_date`
- `required_periodic_tasks`

## Plan técnico mínimo recomendado

### Paso 1. Asegurar continuidad diaria de raw snapshots

Meta:

- tener al menos un día útil por fecha calendario operativa en `ActivoPortafolioSnapshot`

Acciones:

- verificar ejecución real de `core.sync_portfolio_data`
- revisar logs y errores de token/API alrededor de fechas faltantes
- alertar si pasan más de `24h` sin nuevas filas de `ActivoPortafolioSnapshot`

### Paso 2. Asegurar consolidación diaria consistente

Meta:

- cada día con sync válido debe dejar también `PortfolioSnapshot`, salvo razón explícita

Acciones:

- detectar y alertar días con `ActivoPortafolioSnapshot` pero sin `PortfolioSnapshot`
- revisar fallos silenciosos en `PortfolioSnapshotService.generate_daily_snapshot()`
- considerar envolver el paso `sync + snapshot` con mejor logging estructurado

### Paso 3. Monitorear progreso hacia covarianza usable

Meta operativa mínima:

- `20+` observaciones utilizables en ventana reciente

Seguimiento:

- observar `usable_observations_count`
- observar activación real del modelo en `Ops`

## Estrategia de backfill recomendada

Backfill sí, pero mínimo y controlado.

### Backfill sugerido

- re-ejecutar snapshots diarios faltantes de `PortfolioSnapshot` para días que ya tienen raw snapshots completos
- no intentar reconstruir precios inexistentes desde covarianza ni inventar mercado faltante

### Backfill no sugerido todavía

- inventar días de `ActivoPortafolioSnapshot`
- interpolar precios
- usar proxies de benchmarks para reemplazar historia faltante por símbolo

## Decisión práctica

Antes de abrir otra subfase cuantitativa:

1. corregir continuidad diaria de sync
2. cerrar el gap entre raw snapshots y `PortfolioSnapshot`
3. medir si `usable_observations_count` empieza a crecer de forma sostenida

Recién ahí conviene volver a empujar más fuerte `covariance_aware`.
