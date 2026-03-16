## Objetivo

Exponer en `Ops` el estado operativo de las series macro locales que alimentan Analytics v2.

## Implementacion

- `LocalMacroSeriesService.get_status_summary()`
- bloque server-rendered en `Ops`

## Estados

- `ready`
  - la serie existe y su ultima fecha esta dentro de la ventana de frescura esperada
- `stale`
  - la serie existe pero su ultima fecha quedo vieja
- `missing`
  - no hay snapshots persistidos para la serie
- `not_configured`
  - aplica a series opcionales como `usdars_mep` cuando la fuente externa no esta configurada

## Uso operativo

Permite distinguir entre:

- falta real de datos
- configuracion faltante de una fuente opcional
- serie presente pero desactualizada
