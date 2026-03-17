# Diseno minimo de fuente externa para spreads soberanos locales

## Objetivo

Definir como integrar spreads soberanos locales por instrumento sin abrir todavia un stack de mercado complejo ni romper el flujo actual de macro local.

## Estado actual

Hoy el sistema ya puede leer:

- riesgo pais Argentina agregado
- peso soberano local total
- bono soberano local dominante
- concentracion del bloque soberano en un solo instrumento

Eso alcanza para una lectura local explicable, pero no permite diferenciar:

- GD30 vs AL30 vs GD35 por spread propio
- widening o compresion puntual por bono
- dispersion interna del bloque soberano

## Reutilizacion disponible

La integracion futura debe reutilizar:

- `MacroSeriesSnapshot`
- `ParametrosMacroLocal.SERIES`
- `LocalMacroSeriesService.sync_series()`
- `FXJSONClient` o un cliente JSON equivalente si la fuente devuelve escalares por instrumento
- `LocalMacroSignalsService`

No conviene crear:

- un modelo nuevo de persistencia
- un pipeline separado de sync
- un endpoint dedicado solo para spreads

## Contrato minimo recomendado

Si se integra una fuente real, cada bono soberano local debe entrar como una serie diaria independiente:

- `soberano_spread_gd30`
- `soberano_spread_al30`
- `soberano_spread_gd35`

Cada serie deberia persistir:

- `series_key`
- `source`
- `external_id`
- `frequency = daily`
- `fecha`
- `value`

El `value` recomendado es un spread en basis points o un valor equivalente estable y documentado.

## Resumen derivado esperado

Sobre esas series, el modulo local deberia poder construir:

- `top_local_sovereign_spread_symbol`
- `top_local_sovereign_spread_bps`
- `local_sovereign_spread_dispersion_bps`
- `local_sovereign_spread_signals`

## Senales MVP futuras

Una vez exista la fuente, las primeras senales utiles serian:

- `local_sovereign_spread_top_bond_high`
- `local_sovereign_spread_dispersion_high`

Lectura esperada:

- un bono puntual concentra el mayor spread del bloque
- el bloque soberano local no solo esta concentrado en peso, tambien en stress de spread

## Restricciones metodologicas

No conviene implementar todavia:

- curvas completas por duration
- modelos de TIR
- paridades
- Z-spreads
- comparacion contra curva teorica

Eso seria una fase posterior. El primer release debe limitarse a spreads diarios simples por instrumento.

## Proveedor externo: criterio minimo

Antes de implementar, el proveedor elegido debe cumplir:

- disponibilidad diaria razonable
- identificacion por instrumento local explicita
- valor estable y documentado
- licencia o uso aceptable para el proyecto
- JSON sencillo o contrato facil de adaptar

Si el proveedor no cumple eso, no conviene integrarlo.

## Integracion recomendada

Orden recomendado:

1. aprobar proveedor real
2. agregar series en `ParametrosMacroLocal`
3. extender cliente de mercado existente
4. persistir series en `MacroSeriesSnapshot`
5. exponer resumen minimo en `LocalMacroSignalsService`
6. derivar senales y recomendaciones
7. exponer una fila breve en `Estrategia`

## Riesgos

- elegir una fuente inestable y tener ruido operativo
- mezclar riesgo pais agregado con spreads puntuales y duplicar senales
- sobredisenar una capa cuantitativa sin tener antes datos confiables

## Criterio de habilitacion

No conviene abrir implementacion de spreads soberanos locales hasta que exista una fuente concreta aprobada y verificable.
