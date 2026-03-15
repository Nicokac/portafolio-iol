# Analytics v2 - Modelo de Factores MVP

## Objetivo

Definir el universo cerrado de factores del MVP de `factor exposure proxy` antes de
clasificar activos individuales.

Este modulo no hace mapping por simbolo todavia. Solo fija:

- lista de factores permitidos
- significado operativo de cada factor
- notas de clasificacion para el modulo siguiente

## Factores MVP

Factores definidos:

- `growth`
- `value`
- `quality`
- `dividend`
- `defensive`
- `cyclical`

## Base reutilizada del proyecto

El modelo no parte de cero. Se apoya en metadata ya existente:

- `ParametroActivo.bloque_estrategico`
- `ParametroActivo.tipo_patrimonial`
- `ParametroActivo.sector`

Eso permite que `4.2` use primero mappings controlados y despues fallbacks acotados,
sin crear una taxonomia paralela al proyecto actual.

## Definicion operativa breve

- `growth`: crecimiento esperado, expansion y reinversion
- `value`: sesgo a valuacion relativamente baja o descuento
- `quality`: negocios robustos y resilientes
- `dividend`: renta recurrente o perfil orientado a dividendos
- `defensive`: menor sensibilidad relativa al ciclo
- `cyclical`: mayor sensibilidad a actividad economica y ciclo

## Limitaciones

- no es un factor model estadistico
- no estima betas
- no obliga a clasificar todos los activos
- permite `unknown` cuando no haya confianza razonable

## Extension inmediata

El siguiente modulo debe usar este catalogo para:

- mapping explicito por simbolo cuando haga falta
- fallback por bloque estrategico
- fallback por sector o tipo de activo
- clasificacion `unknown` cuando corresponda
