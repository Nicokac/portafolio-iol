## Objetivo

Agregar un sync opcional de `USDARS MEP` sobre la infraestructura ya existente de `MacroSeriesSnapshot`.

## Reutilizacion

- `LocalMacroSeriesService.sync_series()`
- `MacroSeriesSnapshot`
- comando `sync_local_macro`

## Settings

- `USDARS_MEP_API_URL`
- `USDARS_MEP_API_VALUE_PATH`
- `USDARS_MEP_API_DATE_PATH`

## Comportamiento

- si la fuente esta configurada, `sync_series("usdars_mep")` persiste una observacion diaria
- si la fuente no esta configurada, la serie se marca como:
  - `skipped = True`
  - sin romper `sync_all()`

## Limitaciones

- no fija un proveedor unico de MEP
- no hace backfill historico
- persiste una observacion diaria por ejecucion
