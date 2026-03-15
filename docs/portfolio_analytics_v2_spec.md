# Portfolio Analytics v2 - Especificación Funcional

## Propósito

Portfolio Analytics v2 agrega una segunda capa analítica sobre la plataforma actual de Portafolio IOL.

No reemplaza la analítica existente ni redefine la metodología financiera base ya documentada en `docs/financial_methodology.md`.
Su objetivo es extender la capacidad actual desde métricas descriptivas hacia explicaciones de riesgo, sensibilidad y soporte más profundo para decisiones de inversión.

## Problema que resuelve

La plataforma actual ya responde correctamente preguntas como:

- cuánto vale el portafolio
- cómo está distribuido
- qué retorno tuvo
- qué volatilidad, tracking error o drawdown presenta
- cómo se compara contra un benchmark compuesto

Pero todavía no responde con suficiente profundidad preguntas como:

- qué activos explican la mayor parte del riesgo
- qué tan sensible es la cartera a shocks específicos
- a qué estilos o factores está expuesta
- dónde hay fragilidad estructural más allá del peso patrimonial
- cómo mejorar recomendaciones y rebalanceos con señales más explicativas

Analytics v2 cubre ese gap.

## Objetivos funcionales

Analytics v2 debe permitir:

1. explicar mejor de dónde viene el riesgo del portafolio
2. estimar sensibilidad ante escenarios y shocks
3. medir exposición a factores o estilos de inversión
4. fortalecer recomendaciones y rebalanceos con señales más profundas
5. preparar el terreno para simulación avanzada futura

## Alcance funcional inicial

El alcance inicial de Analytics v2 incluye cinco líneas de trabajo priorizadas:

1. risk contribution
2. scenario analysis
3. factor exposure proxy
4. stress testing ampliado
5. expected return simple

Estas capacidades deben consumir los datos y servicios existentes siempre que sea posible.

## Qué es Analytics v2

Analytics v2 es una capa adicional de análisis explicativo y de sensibilidad que:

- reutiliza snapshots y metadata ya disponibles
- produce resultados serializables para consumo por dashboard y recomendaciones
- expone señales interpretables y auditables
- usa proxies controlados cuando no existe información más sofisticada
- prioriza MVPs metodológicamente defendibles antes que modelos avanzados

## Qué no es Analytics v2

En su alcance inicial, Analytics v2 no es:

- un motor de optimización avanzada
- un framework de Monte Carlo
- un modelo multifactor estadístico completo
- un covariance engine de producción institucional
- una frontera eficiente operativa para ejecución real
- un sistema de pricing avanzado por activo

## Dependencias funcionales y técnicas existentes

Analytics v2 parte sobre estas piezas ya disponibles en el proyecto:

- `PortfolioSnapshot` y `PositionSnapshot`
- `ActivoPortafolioSnapshot` y `ResumenCuentaSnapshot`
- `ParametroActivo` como taxonomía analítica principal
- `VolatilityService`
- `TWRService`
- `TrackingErrorService`
- `StressTestService`
- `AttributionService`
- `BenchmarkSeriesService`
- `LocalMacroSeriesService`
- `RecommendationEngine`
- `RebalanceEngine`

Benchmark compuesto actual:

- CEDEAR USA -> SPY
- Bonos argentinos -> EMB
- Liquidez ARS -> BADLAR

Esto implica que Analytics v2 debe integrarse sobre una base analítica viva, no sobre un sistema vacío.

## Módulos funcionales previstos

### 1. Risk Contribution

Pregunta que responde:

> ¿Qué posiciones explican la mayor parte del riesgo del portafolio?

Versión inicial esperada:

- score de riesgo por activo basado en `peso * volatilidad_proxy`
- contribución porcentual al riesgo por activo
- agregación por sector, país y tipo de activo
- flags para recomendaciones

### 2. Scenario Analysis

Pregunta que responde:

> ¿Qué pasa con el portafolio si ocurre un shock específico?

Versión inicial esperada:

- catálogo de escenarios cerrados
- sensibilidad heurística por activo/sector/país/moneda
- impacto estimado total y por agrupación
- señales reutilizables para planeación y alertas

### 3. Factor Exposure Proxy

Pregunta que responde:

> ¿A qué factores o estilos está expuesto el portafolio?

Versión inicial esperada:

- clasificación proxy por activo
- agregación por factor
- dominante, faltantes y concentración factorial
- soporte para recomendaciones

### 4. Stress Testing ampliado

Pregunta que responde:

> ¿Qué tan frágil es el portafolio ante escenarios extremos?

Versión inicial esperada:

- escenarios extremos adicionales a los ya disponibles
- score o lectura de fragilidad
- ranking de vulnerabilidad por activo, sector y país

### 5. Expected Return Simple

Pregunta que responde:

> ¿Qué retorno esperado simple y explicable sugiere la estructura actual?

Versión inicial esperada:

- baseline por benchmark, asset class o referencia local
- sin pretensión de forecasting sofisticado
- foco en interpretabilidad, no en pseudo precisión

## Fuera de alcance inicial

Quedan explícitamente fuera del alcance del MVP inicial:

- Monte Carlo avanzado
- optimización de frontera eficiente
- motores complejos de covarianza
- betas sofisticadas
- modelos de factores estadísticos completos
- calibraciones macro avanzadas
- optimización de rebalanceo con restricciones complejas

## Principios metodológicos

Analytics v2 debe seguir estas reglas:

- priorizar explicabilidad sobre complejidad
- preferir resultados auditables a estimaciones opacas
- usar metadata existente como primera fuente de clasificación
- declarar bases de cálculo y limitaciones de cada output
- marcar explícitamente cuando se use un proxy o fallback
- no publicar una cifra como robusta si la historia no lo soporta

## Contratos esperados de salida

Sin definir todavía la arquitectura final, los outputs de Analytics v2 deben tender a:

- ser serializables
- tener metadata de metodología
- tener metadata de base de cálculo
- tener flags de calidad o confianza cuando aplique
- ser consumibles por dashboard y motores de recomendaciones sin lógica adicional en templates

## Integración esperada con producto

Analytics v2 debe integrarse de forma gradual con:

- dashboard analítico
- centro de métricas
- centro de performance
- planeación
- motor de recomendaciones
- motor de rebalanceo

La integración funcional no se implementa en esta especificación, pero queda definida como destino natural del roadmap.

## Supuestos permitidos en MVP

Se permiten proxies controlados cuando no exista mejor fuente disponible, siempre que:

- estén documentados
- no oculten incertidumbre metodológica
- no dupliquen lógica si ya existe una implementación reutilizable
- puedan reemplazarse luego sin romper contratos principales

## Criterios de éxito de Analytics v2

Se considerará que Analytics v2 agrega valor si logra:

- explicar riesgo mejor que una simple lectura patrimonial
- detectar concentraciones de fragilidad no visibles por peso
- enriquecer recomendaciones con señales más inteligentes
- soportar escenarios simples pero útiles para decisiones reales
- mantenerse compatible con la arquitectura actual y con v1

## Relación con documentación existente

Esta especificación no reemplaza:

- `docs/financial_methodology.md`
- `docs/DECISIONS.md`

Las complementa.

- `financial_methodology.md` sigue definiendo las métricas ya operativas del sistema
- `DECISIONS.md` sigue registrando decisiones de diseño y restricciones operativas
- este documento define el alcance funcional específico de Analytics v2

## Estado

Documento inicial de alcance funcional.
Listo para servir como base del siguiente módulo: arquitectura técnica v2 y contratos de datos.
