## Objetivo

Cerrar la habilitacion operativa de `USDARS MEP` en entorno sin cambiar logica de dominio.

## Estado actual

`USDARS MEP` ya no requiere una variable de entorno obligatoria para funcionar.
La app trae por default como fuente:

- `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH=venta`
- `USDARS_MEP_API_DATE_PATH=fechaActualizacion`

## Pasos minimos

1. Ejecutar:
   - `python manage.py sync_local_macro`
   - o usar `Sincronizar Macro Local` en `Ops`
2. Verificar en `Ops`:
   - `usdars_mep` deja de estar en `Sin datos` o `Stale`
   - el bloque `Series macro criticas para decision` lo muestra como `Listo`
3. Verificar en `Resumen` o `Estrategia`:
   - aparece `Dolar financiero`
   - aparece `Brecha FX`
   - aparece `Estado FX`

## Si queres sobrescribir la fuente

Podes redefinir por entorno:

- `USDARS_MEP_API_URL`
- `USDARS_MEP_API_VALUE_PATH`
- `USDARS_MEP_API_DATE_PATH`

## Proveedor recomendado hoy

- `ArgentinaDatos`
- endpoint:
  - `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`
- campos usados:
  - `venta`
  - `fechaActualizacion`

## Limitaciones

- este modulo no documenta `CCL`; ese flujo vive ya en la misma familia de defaults pero como serie separada
- la validez del path JSON depende del proveedor si decidis sobrescribirlo
