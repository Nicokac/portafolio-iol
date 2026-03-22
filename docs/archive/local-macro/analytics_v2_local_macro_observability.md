## Objetivo

Exponer en `Ops` el estado operativo de las series macro locales que alimentan Analytics v2.

## Implementacion

- `LocalMacroSeriesService.get_status_summary()`
- bloque server-rendered en `Ops`
- `PipelineObservabilityService` como capa de consolidacion operativa
- bloque `Series macro criticas para decision` en `Ops`

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

## Series criticas destacadas

`Ops` ahora separa del resto del universo macro las series que mas afectan decisiones reales:

- `usdars_oficial`
- `usdars_mep`
- `usdars_ccl`
- `badlar_privada`
- `ipc_nacional`
- `uva`
- `riesgo_pais_arg`

El objetivo no es duplicar el estado macro completo, sino detectar rapido si falta alguna de estas referencias:

- brecha FX
- regimen FX
- tasa real local
- inflacion indexada
- riesgo soberano local

## Interpretacion practica

- si faltan `usdars_mep` o `usdars_ccl`, la lectura de FX financiero queda parcial
- si falta `uva`, el sistema puede hacer fallback a `IPC`, pero baja la calidad de la referencia real
- si falta `riesgo_pais_arg`, se debilita la lectura de riesgo soberano local
- si falta `usdars_oficial`, la brecha FX deja de ser interpretable
