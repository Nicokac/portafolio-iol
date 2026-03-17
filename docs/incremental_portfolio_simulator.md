# Incremental Portfolio Simulator

## Objetivo

Evaluar cÃ³mo cambia el portafolio si se aplica una compra incremental propuesta, comparando `before` vs `after` sin modificar datos persistidos.

## Inputs

- `capital_amount`
- `purchase_plan`
- posiciones normalizadas actuales

## ReutilizaciÃ³n del MVP

El simulador no crea nueva analÃ­tica.

Reutiliza:

- `ExpectedReturnService`
- `RiskContributionService`
- `CovarianceAwareRiskContributionService`
- `FactorExposureService`
- `StressFragilityService`
- `ScenarioAnalysisService`

## LÃ³gica del MVP

1. cargar posiciones actuales
2. copiar portafolio en memoria
3. aplicar compras propuestas por sÃ­mbolo
4. recalcular analÃ­tica sobre `before` y `after`
5. construir `delta`
6. devolver una interpretaciÃ³n simple basada en cambios de:
   - retorno esperado
   - fragilidad
   - peor escenario
   - concentraciÃ³n de riesgo
   - sesgo defensivo/dividend

## Output

- `before`
- `after`
- `delta`
- `interpretation`
- `warnings`

## Integración actual

En `Planeación`, el MVP se usa con una regla simple:

1. tomar los bloques recomendados por el motor mensual
2. elegir el top candidato de cada bloque desde `Candidate Asset Ranking Engine`
3. construir un `purchase_plan` default
4. mostrar comparaciÃ³n `before/after` server-rendered

## Limitaciones

- simula un Ãºnico plan de compra por vez
- no asigna montos Ã³ptimos
- no rankea combinaciones
- no modifica persistencia
- depende de metadata disponible para activos nuevos al portafolio actual

## EvoluciÃ³n futura

- integrar comparaciÃ³n directa desde `PlaneaciÃ³n`
- evaluar mÃºltiples propuestas candidatas
- comparar simulaciones del top ranking de activos
