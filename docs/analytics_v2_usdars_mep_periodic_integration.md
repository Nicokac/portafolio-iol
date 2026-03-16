## Objetivo

Integrar el sync de macro local, incluido `USDARS MEP` cuando exista configuracion, a la rutina periodica del sistema.

## Implementacion

- nueva task Celery:
  - `apps.core.tasks.portfolio_tasks.sync_local_macro_series`
- nueva periodic task:
  - `core.sync_local_macro_series`
  - horario: `18:30`
  - timezone: `America/Argentina/Buenos_Aires`

## Razon del horario

- queda separada del snapshot patrimonial diario de las `06:00`
- corre en una ventana razonable post-cierre para referencias locales diarias

## Settings requeridos para USDARS MEP

- `USDARS_MEP_API_URL`
- `USDARS_MEP_API_VALUE_PATH`
- `USDARS_MEP_API_DATE_PATH`

## Comportamiento operativo

- si `USDARS_MEP_API_URL` no esta configurada:
  - la serie `usdars_mep` queda en `skipped`
  - el sync macro general sigue siendo exitoso
- si la fuente esta configurada:
  - `usdars_mep` se persiste en `MacroSeriesSnapshot`

## Limitaciones

- no agrega un proveedor definitivo por default
- no integra alertas sobre `skipped`
- no cambia la salud historica de snapshots patrimoniales
