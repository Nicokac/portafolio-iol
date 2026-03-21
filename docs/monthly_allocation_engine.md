# Motor MVP de Asignacion Mensual Incremental

## Objetivo

Traducir la analitica actual de la app en una propuesta simple y explicable de uso del capital mensual incremental.

## Inputs

- `capital_amount`
- `RiskContributionService` / `CovarianceAwareRiskContributionService`
- `FactorExposureService`
- `StressFragilityService`
- `ScenarioAnalysisService`
- `ExpectedReturnService`
- `RecommendationEngine`

## Reglas del MVP

1. Penalizar bloques que hoy agravan:
   - concentracion de riesgo
   - fragilidad
   - shocks dominantes
   - exceso de liquidez
2. Favorecer bloques que ayudan a:
   - cubrir `defensive_gap`
   - cubrir `dividend_gap`
   - reforzar buckets con mejor retorno estructural
   - diversificar fuera de bloques sobrecargados
3. Resolver conflictos de forma conservadora:
   - si un bloque tiene senal de retorno positiva pero tambien una penalizacion fuerte de riesgo/stress, se excluye en el MVP
4. Distribuir el capital entre los mejores bloques por score relativo.

## Output

- resumen general del criterio
- bloques recomendados con monto sugerido
- bloques evitados
- explicacion consolidada

## Score explanation

Cada bloque recomendado expone:

- `positive_signals`
- `negative_signals`
- `notes`

La idea no es recalcular el score, sino dejar trazabilidad de que reglas existentes lo empujaron hacia arriba o hacia abajo.

Las senales salen solo de:

- factor exposure
- expected return
- risk contribution
- scenario analysis
- stress fragility
- recommendation engine

## Candidate Asset Ranking Engine

Despues de decidir que bloques conviene reforzar, el ranking de candidatos baja un nivel y ordena activos ya presentes en cartera que mejor encajan dentro de esos bloques.

El motor:

- no cambia la asignacion mensual
- no simula compras
- no optimiza portafolio

Solo rankea candidatos usando senales ya existentes de:

- factor exposure
- risk contribution
- stress fragility
- scenario analysis
- bloques recomendados/evitados del motor mensual

La salida expone:

- activo
- bloque sugerido
- score de idoneidad
- razones principales del ranking

Limitacion deliberada del MVP:

- usa unicamente activos ya presentes en cartera
- no abre universo externo de nuevos instrumentos

## Limitaciones

- no recomienda activos concretos
- no simula antes/despues por activo
- no optimiza matematicamente
- usa reglas explicables y deterministicas

## Evolucion futura

- bajar de bloque a activo
- incorporar simulacion incremental antes/despues
- usar scoring mas fino por candidato
- abrir interaccion directa con el capital mensual elegido por el usuario
