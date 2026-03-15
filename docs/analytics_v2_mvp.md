# Analytics v2 - Definicion del MVP

## Objetivo

Cerrar el alcance del primer release util de Analytics v2, fijando:

- prioridad de modulos
- criterios de aceptacion minimos
- dependencias previas
- explicitacion de lo que queda fuera del primer release

Este documento toma como base:

- `docs/portfolio_analytics_v2_spec.md`
- `docs/analytics_v2_architecture.md`
- `docs/analytics_v2_data_contracts.md`
- `docs/analytics_v2_gap_analysis.md`

## Definicion de MVP para Analytics v2

En este proyecto, el MVP de Analytics v2 no significa "version rapida" ni "demo visual".
Significa la primera version que:

- agrega valor analitico real sobre la app actual
- es metodologicamente defendible
- es serializable y reusable
- tiene tests suficientes
- no rompe v1
- puede integrarse despues con dashboard y recomendaciones sin reescribirse

## Corte de alcance del primer release util

El primer release util de Analytics v2 debe incluir exactamente estos modulos:

1. `risk contribution`
2. `scenario analysis`
3. `factor exposure proxy`
4. `stress testing` ampliado
5. `expected return simple`

Orden de implementacion recomendado:

1. `risk contribution`
2. `scenario analysis`
3. `factor exposure proxy`
4. `stress testing` ampliado
5. `expected return simple`

Razon del orden:

- `risk contribution` reutiliza mejor los datos ya disponibles y entrega valor rapido
- `scenario analysis` se apoya parcialmente en el stress heuristico ya existente
- `factor exposure proxy` requiere decisiones de mapping, pero no infraestructura nueva
- `stress testing` ampliado conviene hacer despues de escenarios para reutilizar catalogo y reglas
- `expected return simple` debe entrar al final para evitar inflar expectativas antes de cerrar riesgo y sensibilidad

## Fuera del MVP inicial

Queda fuera del MVP inicial:

- simulacion avanzada
- Monte Carlo
- covarianza robusta por activo
- betas por benchmark
- frontier optimization
- factor models estadisticos
- expected return sofisticado
- integracion completa con recomendaciones y rebalanceo
- integracion visual completa en dashboard

Nota:

- la integracion con producto podra venir inmediatamente despues del MVP tecnico, pero no forma parte del cierre de esta fase

## Criterios transversales de aceptacion

Todo modulo MVP debe cumplir estos criterios generales:

1. usar maximo de reutilizacion razonable de servicios y modelos existentes
2. exponer output serializable y consistente con `analytics_v2_data_contracts.md`
3. incluir metadata minima:
   - `methodology`
   - `data_basis`
   - `limitations`
   - `confidence`
   - `warnings`
4. manejar explicitamente:
   - portafolio vacio
   - datos faltantes
   - historia insuficiente
   - clasificacion desconocida
   - divisiones por cero
5. tener tests unitarios y de edge cases
6. no mover logica de calculo a templates
7. no romper contratos existentes de v1 sin justificacion

## Criterios de aceptacion por modulo

### 1. Risk Contribution

#### Objetivo del MVP

Responder de forma explicativa:

> que activos explican la mayor parte del riesgo relativo del portafolio bajo un modelo proxy simple

#### Debe incluir

- score de riesgo por activo
- contribucion porcentual por activo
- top contributors
- agregacion por sector
- agregacion por pais
- agregacion por tipo de activo
- metadata metodologica
- flags de fallback de volatilidad cuando corresponda

#### Debe cumplir

- suma de `contribution_pct` aproximadamente 100%
- portafolio vacio no rompe
- liquidez operativa aporta cero o casi cero de forma explicita
- activos sin volatilidad propia usan fallback documentado
- agregados consistentes con el detalle

#### No necesita todavia

- matriz de covarianza
- marginal contribution real
- risk parity
- optimizacion de riesgo

### 2. Scenario Analysis

#### Objetivo del MVP

Responder:

> que pasa con el portafolio si ocurre un shock cerrado y explicable

#### Debe incluir

- catalogo cerrado de escenarios MVP
- impacto total estimado
- impacto por activo
- impacto por sector
- impacto por pais
- top contribuidores negativos
- metadata de metodologia y limitaciones

#### Escenarios minimos del MVP

- `spy_down_10`
- `spy_down_20`
- `tech_shock`
- `argentina_stress`
- `ars_devaluation`
- `em_stress`

#### Debe cumplir

- escenario invalido devuelve error controlado o warning serializable
- liquidez no recibe shock indebido de mercado
- activos tech reaccionan mas que defensivos en `tech_shock`
- instrumentos argentinos reaccionan mas en `argentina_stress`
- salida consistente y auditable

#### No necesita todavia

- escenarios parametrizados por usuario
- elasticidades calibradas empiricamente
- motor de correlacion

### 3. Factor Exposure Proxy

#### Objetivo del MVP

Responder:

> a que estilos o factores esta expuesto el portafolio usando clasificacion proxy controlada

#### Debe incluir

- exposicion por factor
- factor dominante
- factores subrepresentados
- activos `unknown`
- metadata de confianza
- trazabilidad de mapping o fallback

#### Factores minimos del MVP

- `growth`
- `value`
- `quality`
- `dividend`
- `defensive`
- `cyclical`

#### Debe cumplir

- consistencia basica entre suma de exposiciones y pesos clasificados
- activos sin clasificacion confiable quedan en `unknown`
- no se fuerza clasificacion total
- mapping explicito y fallback quedan diferenciados

#### No necesita todavia

- factor model estadistico
- exposiciones por beta
- regresiones historicas

### 4. Stress Testing ampliado

#### Objetivo del MVP

Responder:

> que tan fragil es el portafolio ante eventos extremos discretos

#### Debe incluir

- catalogo de stresses extremos MVP
- perdida estimada total
- ranking de activos vulnerables
- ranking de sectores vulnerables
- ranking de paises vulnerables
- score simple de fragilidad
- metadata metodologica

#### Stresses minimos del MVP

- `usa_crash_severe`
- `local_crisis_severe`
- `rates_equity_double_shock`
- `em_deterioration`

#### Debe cumplir

- resultados serializables
- no duplicar innecesariamente `StressTestService`, sino extenderlo o apoyarse en el
- liquidez funciona como amortiguador parcial o nulo, no como equity
- score de fragilidad auditable por reglas simples

#### No necesita todavia

- modelo probabilistico
- calibracion por colas complejas
- simulacion de cascadas

### 5. Expected Return Simple

#### Objetivo del MVP

Responder:

> que retorno esperado estructural simple sugiere la composicion actual del portafolio

#### Debe incluir

- expected return total simple
- expected return real simple cuando haya base razonable
- baseline por bucket o benchmark asociado
- metadata de referencias usadas
- warnings por precision limitada

#### Debe cumplir

- no presentarse como forecast preciso
- usar referencias explicables: benchmark, BADLAR, IPC, baseline por clase de activo
- si falta base suficiente, degradar confidence o devolver warning
- salida apta para consumo futuro por planeacion

#### No necesita todavia

- forecasting por activo
- modelos fundamentales
- supuestos macro avanzados

## Dependencias previas para pasar a Fase 1

Antes de implementar codigo nuevo, el proyecto ya debe considerar cerrados estos puntos:

- especificacion funcional inicial
- arquitectura tecnica v2
- contratos de datos
- gap analysis de datos
- priorizacion y acceptance criteria del MVP

Con este documento, Fase 0 queda lista para cerrarse.

## Definicion operativa de "modulo terminado"

Un modulo de Analytics v2 se considerara terminado solo si:

1. reutiliza lo que corresponde
2. implementa servicio y contratos consistentes
3. tiene tests de comportamiento y edge cases
4. devuelve metadata metodologica
5. no rompe v1
6. queda documentado brevemente
7. puede ser consumido despues sin reescribir su salida

## Riesgos a controlar en la fase de implementacion

### 1. Sobrepromesa metodologica

Mitigacion:

- usar naming prudente
- exponer `confidence`
- documentar fallbacks

### 2. Duplicacion de logica existente

Mitigacion:

- inspeccion obligatoria previa a cada modulo
- reutilizar servicios actuales antes de crear otros nuevos

### 3. Integracion prematura con UI

Mitigacion:

- primero cerrar backend y contratos
- integrar con dashboard despues

### 4. Expansion innecesaria del alcance

Mitigacion:

- mantener cada modulo en version MVP defendible
- no adelantar fase avanzada

## Decision final de roadmap inmediato

El siguiente paso correcto no es integrar con UI.
El siguiente paso correcto es iniciar Fase 1:

1. `1.1 — Schemas y contratos compartidos`
2. `1.2 — Helpers compartidos`
3. `2.x — Risk Contribution MVP`

Ese orden minimiza duplicacion y deja una base tecnica comun para todos los modulos posteriores.
