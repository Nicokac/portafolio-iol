## Objetivo

Integrar el sync de macro local, incluido `USDARS MEP`, a la rutina periodica del sistema.

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

## Settings relevantes para USDARS MEP

Defaults actuales:

- `USDARS_MEP_API_URL=https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH=venta`
- `USDARS_MEP_API_DATE_PATH=fechaActualizacion`

Solo hace falta definirlos si queres sobrescribir el proveedor.

## Comportamiento operativo

- con la configuracion default:
  - `usdars_mep` se intenta sincronizar contra ArgentinaDatos
- si redefinis la fuente por entorno:
  - el sync usa el `URL`, `VALUE_PATH` y `DATE_PATH` configurados
- si la fuente falla:
  - el sync macro general sigue siendo exitoso a nivel lote y reporta `failed` para la serie puntual

## Limitaciones

- no integra alertas sobre `failed` o `stale`
- no cambia la salud historica de snapshots patrimoniales
- la lectura sigue dependiendo de disponibilidad de red al momento del sync
