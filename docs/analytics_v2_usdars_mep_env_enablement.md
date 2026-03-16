## Objetivo

Cerrar la habilitacion operativa de `USDARS MEP` en entorno sin cambiar logica de dominio.

## Pasos minimos

1. Definir:
   - `USDARS_MEP_API_URL`
   - `USDARS_MEP_API_VALUE_PATH`
   - `USDARS_MEP_API_DATE_PATH`
2. Ejecutar:
   - `python manage.py sync_local_macro`
   - o usar `Sincronizar Macro Local` en `Ops`
3. Verificar en `Ops`:
   - `usdars_mep` deja de estar en `Sin configurar`
   - el ultimo sync macro local muestra `success` o `success_with_skips`

## Comportamiento esperado

- si la fuente responde bien:
  - se persiste `usdars_mep`
  - se habilita `fx_gap_pct`
  - pueden aparecer señales `local_fx_gap_high`

## Limitaciones

- este modulo no define un proveedor unico
- la validez del path JSON depende del proveedor elegido
