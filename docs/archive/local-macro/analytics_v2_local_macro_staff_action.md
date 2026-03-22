## Objetivo

Permitir desde `Ops` la ejecucion manual del sync macro local.

## Implementacion

- nueva vista staff:
  - `SyncLocalMacroView`
- nueva ruta:
  - `dashboard:sync_local_macro`
- nuevo boton en `Ops`:
  - `Sincronizar Macro Local`

## Comportamiento

- ejecuta `LocalMacroSeriesService().sync_all()`
- registra auditoria sensible con accion:
  - `sync_local_macro`
- redirige a `Ops`
- informa:
  - exito
  - fallos parciales
  - o error total

## Limitaciones

- no muestra todavia el detalle fino por serie en un flash message separado
- no dispara task asincronica; la accion es sincrona y staff-only
