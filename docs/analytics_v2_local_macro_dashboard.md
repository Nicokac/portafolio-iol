# Exposición local en dashboard

## Objetivo

Hacer visible una lectura local breve y reusable en `Estrategia` sin mover lógica macro al template.

## Integración aplicada

- `get_analytics_v2_dashboard_summary()` ahora incorpora `local_macro`
- `Estrategia` muestra:
  - card `Macro Local`
  - carry real BADLAR
  - peso Argentina
  - cobertura CER

## Datos mostrados

- `badlar_real_carry_pct`
- `argentina_weight_pct`
- `cer_weight_pct`
- `confidence`

## Limitaciones

- no muestra MEP ni brecha
- no muestra riesgo país
- no agrega gráfico propio todavía
- usa la lectura heurística del servicio local ya implementado

## Riesgo pais en Resumen

`Resumen` ahora expone una card dedicada de `Riesgo pais Argentina` dentro del bloque de contexto macro local.

Reglas de integracion:

- reutiliza `LocalMacroSeriesService.get_context_summary()`
- consume `riesgo_pais_arg` y `riesgo_pais_arg_date`
- consume tambien `riesgo_pais_arg_change_30d` y `riesgo_pais_arg_change_pct_30d`
- muestra la referencia como dato operativo breve
- documenta la fuente actual como `ArgentinaDatos`
