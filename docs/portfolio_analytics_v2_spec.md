# Portfolio Analytics v2 - Especificacion Funcional

## Proposito

Portfolio Analytics v2 agrega una segunda capa analitica sobre la plataforma actual de Portafolio IOL.

No reemplaza la analitica existente ni redefine la metodologia financiera base ya documentada en `docs/financial_methodology.md`.
Su objetivo es extender la capacidad actual desde metricas descriptivas hacia explicaciones de riesgo, sensibilidad y soporte mas profundo para decisiones de inversion.

## Problema que resuelve

La plataforma actual ya responde correctamente preguntas como:

- cuanto vale el portafolio
- como esta distribuido
- que retorno tuvo
- que volatilidad, tracking error o drawdown presenta
- como se compara contra un benchmark compuesto

Pero todavia no responde con suficiente profundidad preguntas como:

- que activos explican la mayor parte del riesgo
- que tan sensible es la cartera a shocks especificos
- a que estilos o factores esta expuesta
- donde hay fragilidad estructural mas alla del peso patrimonial
- como mejorar recomendaciones y rebalanceos con senales mas explicativas

Analytics v2 cubre ese gap.

## Objetivos funcionales

Analytics v2 debe permitir:

1. explicar mejor de donde viene el riesgo del portafolio
2. estimar sensibilidad ante escenarios y shocks
3. medir exposicion a factores o estilos de inversion
4. fortalecer recomendaciones y rebalanceos con senales mas profundas
5. preparar el terreno para simulacion avanzada futura

## Alcance funcional inicial

El alcance inicial de Analytics v2 incluye cinco lineas de trabajo priorizadas:

1. risk contribution
2. scenario analysis
3. factor exposure proxy
4. stress testing ampliado
5. expected return simple

Estas capacidades deben consumir los datos y servicios existentes siempre que sea posible.

## Que es Analytics v2

Analytics v2 es una capa adicional de analisis explicativo y de sensibilidad que:

- reutiliza snapshots y metadata ya disponibles
- produce resultados serializables para consumo por dashboard y recomendaciones
- expone senales interpretables y auditables
- usa proxies controlados cuando no existe informacion mas sofisticada
- prioriza MVPs metodologicamente defendibles antes que modelos avanzados

## Que no es Analytics v2

En su alcance inicial, Analytics v2 no es:

- un motor de optimizacion avanzada
- un framework de Monte Carlo
- un modelo multifactor estadistico completo
- un covariance engine de produccion institucional
- una frontera eficiente operativa para ejecucion real
- un sistema de pricing avanzado por activo

## Dependencias funcionales y tecnicas existentes

Analytics v2 parte sobre estas piezas ya disponibles en el proyecto:

- `PortfolioSnapshot` y `PositionSnapshot`
- `ActivoPortafolioSnapshot` y `ResumenCuentaSnapshot`
- `ParametroActivo` como taxonomia analitica principal
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

Esto implica que Analytics v2 debe integrarse sobre una base analitica viva, no sobre un sistema vacio.

## Modulos funcionales previstos

### 1. Risk Contribution

Pregunta que responde:

> Que posiciones explican la mayor parte del riesgo del portafolio?

Version inicial esperada:

- score de riesgo por activo basado en `peso * volatilidad_proxy`
- contribucion porcentual al riesgo por activo
- agregacion por sector, pais y tipo de activo
- flags para recomendaciones

### 2. Scenario Analysis

Pregunta que responde:

> Que pasa con el portafolio si ocurre un shock especifico?

Version inicial esperada:

- catalogo de escenarios cerrados
- sensibilidad heuristica por activo, sector, pais y moneda
- impacto estimado total y por agrupacion
- senales reutilizables para planeacion y alertas

### 3. Factor Exposure Proxy

Pregunta que responde:

> A que factores o estilos esta expuesto el portafolio?

Version inicial esperada:

- clasificacion proxy por activo
- agregacion por factor
- dominante, faltantes y concentracion factorial
- soporte para recomendaciones

### 4. Stress Testing ampliado

Pregunta que responde:

> Que tan fragil es el portafolio ante escenarios extremos?

Version inicial esperada:

- escenarios extremos adicionales a los ya disponibles
- score o lectura de fragilidad
- ranking de vulnerabilidad por activo, sector y pais

### 5. Expected Return Simple

Pregunta que responde:

> Que retorno esperado simple y explicable sugiere la estructura actual?

Version inicial esperada:

- baseline por benchmark, asset class o referencia local
- sin pretension de forecasting sofisticado
- foco en interpretabilidad, no en pseudo precision

## Fuera de alcance inicial

Quedan explicitamente fuera del alcance del MVP inicial:

- Monte Carlo avanzado
- optimizacion de frontera eficiente
- motores complejos de covarianza
- betas sofisticadas
- modelos de factores estadisticos completos
- calibraciones macro avanzadas
- optimizacion de rebalanceo con restricciones complejas

## Principios metodologicos

Analytics v2 debe seguir estas reglas:

- priorizar explicabilidad sobre complejidad
- preferir resultados auditables a estimaciones opacas
- usar metadata existente como primera fuente de clasificacion
- declarar bases de calculo y limitaciones de cada output
- marcar explicitamente cuando se use un proxy o fallback
- no publicar una cifra como robusta si la historia no lo soporta

## Contratos esperados de salida

Los outputs de Analytics v2 deben tender a:

- ser serializables
- tener metadata de metodologia
- tener metadata de base de calculo
- tener flags de calidad o confianza cuando aplique
- ser consumibles por dashboard y motores de recomendaciones sin logica adicional en templates

## Integracion esperada con producto

Analytics v2 debe integrarse de forma gradual con:

- dashboard analitico
- centro de metricas
- centro de performance
- planeacion
- motor de recomendaciones
- motor de rebalanceo

La integracion funcional no se implementa en esta especificacion, pero queda definida como destino natural del roadmap.

## Supuestos permitidos en MVP

Se permiten proxies controlados cuando no exista mejor fuente disponible, siempre que:

- esten documentados
- no oculten incertidumbre metodologica
- no dupliquen logica si ya existe una implementacion reutilizable
- puedan reemplazarse luego sin romper contratos principales

## Criterios de exito de Analytics v2

Se considera que Analytics v2 agrega valor si logra:

- explicar riesgo mejor que una simple lectura patrimonial
- detectar concentraciones de fragilidad no visibles por peso
- enriquecer recomendaciones con senales mas inteligentes
- soportar escenarios simples pero utiles para decisiones reales
- mantenerse compatible con la arquitectura actual y con v1

## Relacion con documentacion existente

Esta especificacion no reemplaza:

- `docs/financial_methodology.md`
- `docs/DECISIONS.md`

Las complementa.

- `financial_methodology.md` sigue definiendo las metricas ya operativas del sistema
- `DECISIONS.md` sigue registrando decisiones de diseno y restricciones operativas
- este documento define el alcance funcional especifico de Analytics v2

## Estado

Documento base de alcance funcional.
Listo para convivir con la arquitectura tecnica, los contratos de datos y el checklist de exposicion de features.
