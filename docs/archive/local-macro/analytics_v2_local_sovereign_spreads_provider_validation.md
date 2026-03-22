# Validacion de proveedor para spreads soberanos locales

## Objetivo

Determinar si hoy existe una fuente externa razonable para integrar spreads soberanos locales por instrumento dentro de Analytics v2.

## Resultado

Conclusion actual:

- si hay fuentes reutilizables para `riesgo_pais_arg` agregado
- no hay una fuente ya validada para spreads soberanos locales por bono con el contrato minimo requerido

Por eso no conviene abrir implementacion de spreads todavia.

## Fuentes relevadas

### 1. ArgenStats

Lo util detectado:

- expone `Riesgo País` agregado
- ofrece API para desarrolladores
- requiere API key

Lectura:

- sirve como candidato para mantener o mejorar `riesgo_pais_arg`
- no valida por si sola spreads por instrumento tipo `GD30`, `AL30`, `GD35`

### 2. DolarApi

Lo util detectado:

- expone cotizaciones locales simples
- ya es consistente con el uso actual de `usdars_mep`

Lectura:

- es una fuente buena para FX local
- no es una fuente de spreads soberanos por bono

## Contrato minimo requerido para aprobar proveedor

Para que un proveedor sea apto, deberia permitir como minimo:

- identificacion por instrumento local explicita
- valor diario estable por bono
- JSON simple o facilmente adaptable
- fecha de actualizacion clara
- disponibilidad razonable

Ejemplo de series esperadas:

- `soberano_spread_gd30`
- `soberano_spread_al30`
- `soberano_spread_gd35`

## Brecha actual

Hoy no quedo validado un proveedor que cumpla eso con evidencia suficiente.

La brecha no es de arquitectura interna.
La brecha es de fuente externa aprobable.

## Decision tecnica

No avanzar con sync de spreads soberanos locales hasta que exista una fuente concreta que permita:

1. validar el instrumento
2. validar la unidad del valor
3. validar frecuencia diaria
4. validar estabilidad operativa

## Recomendacion

Mantener por ahora:

- `riesgo_pais_arg`
- detalle soberano local por instrumento con datos internos
- concentracion en nombre puntual dentro del bloque soberano

Eso da una lectura local util sin introducir una dependencia externa fragil.

## Fuentes consultadas

- ArgenStats home: https://argenstats.com/
- ArgenStats documentacion: https://argenstats.com/documentacion
- DolarApi home: https://dolarapi.com/
- DolarApi docs: https://dolarapi.com/docs/
