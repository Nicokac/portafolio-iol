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

El comparador incremental agrega variantes simples sobre la misma base:

- top candidato por bloque
- segundo candidato si existe
- split del bloque mÃ¡s grande entre top 2 candidatos

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

## Comparador manual

La hoja `Planeacion` tambien permite contrastar dos planes manuales simples.

Reglas del MVP:

- hasta 2 planes
- hasta 3 lineas por plan
- cada plan define `symbol` + `amount`
- el comparador reutiliza el mismo `IncrementalPortfolioSimulator`
- el resultado se ordena con el mismo score comparativo heuristico usado en el comparador automatico

## Comparador incremental por candidato

La hoja `Planeacion` permite ahora elegir un bloque recomendado y contrastar sus candidatos principales uno contra otro.

Reglas del MVP:

- usa el `suggested_amount` del bloque elegido
- compara hasta 3 candidatos del mismo bloque
- cada candidato se simula como compra individual
- reutiliza `CandidateAssetRankingService` + `IncrementalPortfolioSimulator`
- ordena por el mismo score comparativo heuristico del simulador incremental

## Comparador incremental por split de bloque

La hoja `Planeacion` permite contrastar dos construcciones simples dentro de un mismo bloque recomendado:

- concentrar todo el monto en el top candidato
- repartir el monto entre los top 2 candidatos

Reglas del MVP:

- usa el `suggested_amount` del bloque elegido
- requiere al menos 2 candidatos elegibles en el bloque
- reutiliza `CandidateAssetRankingService` + `IncrementalPortfolioSimulator`
- ordena con el mismo score comparativo heuristico ya usado en los otros comparadores

## Propuesta incremental preferida

La hoja `Planeacion` sintetiza una propuesta incremental preferida a partir de los comparadores ya disponibles.

Reglas del MVP:

- toma la mejor propuesta de cada comparador activo
- compara por `comparison_score`
- usa una prioridad explicita para desempates
- si hay comparacion manual valida, puede prevalecer como override funcional
- no recalcula simulaciones nuevas fuera de las ya expuestas por cada comparador

## Historial persistente de propuestas

La hoja `Planeacion` permite guardar explicitamente la propuesta incremental preferida actual.

Reglas del modulo:

- el guardado se ejecuta solo por `POST`
- la propuesta se recalcula desde el querystring actual para no confiar en payloads armados en cliente
- se persiste un snapshot liviano por usuario con:
  - origen
  - etiqueta de propuesta
  - compra resumida
  - deltas principales
  - interpretacion
- se conserva un historial corto por usuario

Limitaciones:

- no persiste comparadores completos ni variantes descartadas
- no hay versionado profundo ni restauracion automatica
- el historial es operativo y breve, no una bitacora completa de decisiones
