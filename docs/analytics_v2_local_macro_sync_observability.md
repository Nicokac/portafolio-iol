## Objetivo

Dar trazabilidad operativa al ultimo resultado del sync macro local en `Ops`.

## Implementacion

- metric name de estado:
  - `analytics_v2.local_macro.sync_status`
- se registra tanto en:
  - `sync_local_macro_series` (task)
  - `SyncLocalMacroView` (accion manual staff)

## Estados posibles

- `success`
- `success_with_skips`
- `failed`

## Detalle expuesto

- `synced_series`
- `skipped_series`
- `failed_series`
- `reason` cuando hay excepcion

## Superficie

- endpoint staff:
  - `/api/metrics/internal-observability/`
- tabla `Activación modelo de riesgo` / estados internos en `Ops`

## Limitaciones

- observabilidad en cache, no persistente
- no guarda duracion del sync macro como timing separado
