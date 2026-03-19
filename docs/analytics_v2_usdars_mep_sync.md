## Objetivo

Agregar un sync de `USDARS MEP` sobre la infraestructura ya existente de `MacroSeriesSnapshot`.

## Reutilizacion

- `LocalMacroSeriesService.sync_series()`
- `MacroSeriesSnapshot`
- comando `sync_local_macro`

## Settings

Defaults actuales:

- `USDARS_MEP_API_URL=https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH=venta`
- `USDARS_MEP_API_DATE_PATH=fechaActualizacion`

Se pueden sobrescribir por entorno si queres usar otra fuente.

## Comportamiento

- con la fuente default, `sync_series("usdars_mep")` persiste una observacion diaria
- si redefinis la fuente y esa configuracion no existe, la serie puede quedar `skipped`
- si la fuente falla, la serie queda `failed` sin romper `sync_all()`

## Limitaciones

- no hace backfill historico
- persiste una observacion diaria por ejecucion
