# Analytics v2 - USDARS MEP Operating Model

## Objetivo

Consolidar la documentacion operativa de `USDARS MEP` como serie local usada por brecha FX y diagnostico cambiario.

## Fuente default actual

La app usa por default ArgentinaDatos:

- `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH=venta`
- `USDARS_MEP_API_DATE_PATH=fechaActualizacion`

## Flujo operativo

### Sync manual

Desde `Ops`:

- accion `Sincronizar Macro Local`
- ejecuta `LocalMacroSeriesService().sync_all()`
- registra auditoria sensible `sync_local_macro`

### Sync periodico

- task `sync_local_macro_series`
- periodic task `core.sync_local_macro_series`
- horario operativo configurado: `18:30`
- timezone: `America/Argentina/Buenos_Aires`

## Observabilidad

La salud de `usdars_mep` se lee en `Ops` dentro de series macro criticas para decision.

Estados relevantes:

- `ready`
- `stale`
- `missing`
- `not_configured`

Tambien se registra el estado agregado del ultimo sync macro local.

## Consumo funcional

`usdars_mep` alimenta:

- `usdars_financial`
- `fx_gap_pct`
- `fx_gap_mep_pct`
- `fx_mep_ccl_spread_pct`
- `fx_signal_state`

Si `usdars_ccl` falta, `MEP` puede seguir funcionando como referencia financiera parcial.

## Override por entorno

Se puede sobrescribir con:

- `USDARS_MEP_API_URL`
- `USDARS_MEP_API_VALUE_PATH`
- `USDARS_MEP_API_DATE_PATH`

## Limitaciones

- no hace backfill historico profundo
- depende de disponibilidad de red al momento del sync
- no agrega por si solo alertas especiales sobre fallos o staleness

## Documentacion archivada relacionada

La evolucion de esta familia queda preservada en `docs/archive/usdars-mep/`.
