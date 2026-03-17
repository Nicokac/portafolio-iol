# Motor MVP de Asignación Mensual Incremental

## Objetivo

Traducir la analítica actual de la app en una propuesta simple y explicable de uso del capital mensual incremental.

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
   - concentración de riesgo
   - fragilidad
   - shocks dominantes
   - exceso de liquidez
2. Favorecer bloques que ayudan a:
   - cubrir `defensive_gap`
   - cubrir `dividend_gap`
   - reforzar buckets con mejor retorno estructural
   - diversificar fuera de bloques sobrecargados
3. Resolver conflictos de forma conservadora:
   - si un bloque tiene señal de retorno positiva pero también una penalización fuerte de riesgo/stress, se excluye en el MVP
4. Distribuir el capital entre los mejores bloques por score relativo.

## Output

- resumen general del criterio
- bloques recomendados con monto sugerido
- bloques evitados
- explicación consolidada

## Score explanation

Cada bloque recomendado expone:

- `positive_signals`
- `negative_signals`
- `notes`

La idea no es recalcular el score, sino dejar trazabilidad de qué reglas existentes lo empujaron hacia arriba o hacia abajo.

Las señales salen solo de:

- factor exposure
- expected return
- risk contribution
- scenario analysis
- stress fragility
- recommendation engine

## Limitaciones

- no recomienda activos concretos
- no simula antes/después por activo
- no optimiza matemáticamente
- usa reglas explicables y determinísticas

## Evolución futura

- bajar de bloque a activo
- incorporar simulación incremental antes/después
- usar scoring más fino por candidato
- abrir interacción directa con el capital mensual elegido por el usuario
