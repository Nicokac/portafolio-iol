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

## Reaplicacion guiada de snapshots

El historial reciente de `Planeacion` permite reaplicar un snapshot guardado sobre el comparador manual existente.

Reglas del modulo:

- no crea un simulador nuevo
- traduce el snapshot guardado al querystring que ya entiende el comparador manual
- precarga `Plan manual A` con capital y hasta 3 lineas del snapshot elegido
- reutiliza el mismo flujo de simulacion incremental ya disponible en la hoja

Limitaciones:

- la reaplicacion usa solo las primeras 3 lineas del snapshot
- no reconstruye automaticamente `Plan manual B`
- no restaura estados de otros comparadores

## Comparacion snapshot guardado vs propuesta actual

La hoja `Planeacion` permite contrastar un snapshot guardado contra la propuesta incremental preferida actual.

Reglas del modulo:

- reutiliza el historial persistente de propuestas
- reutiliza la propuesta preferida actual ya calculada por la hoja
- compara score comparativo y deltas principales:
  - expected return
  - real expected return
  - fragility
  - worst scenario loss
  - top risk concentration

Limitaciones:

- compara contra una unica propuesta actual, no contra todas las variantes historicas
- el winner se define por `comparison_score`
- no recalcula snapshots historicos; solo contrasta valores ya guardados contra la propuesta vigente

## Baseline incremental de seguimiento

La hoja `Planeacion` permite promover un snapshot guardado a baseline incremental activo.

Reglas del modulo:

- el baseline es por usuario
- solo puede haber un baseline activo por usuario
- la promocion se ejecuta por `POST`
- reutiliza snapshots ya persistidos, sin crear una tabla paralela

Uso previsto:

- fijar una referencia operativa manual
- contrastar futuras propuestas contra un punto de seguimiento elegido

Limitaciones:

- no congela el estado completo de la hoja
- no activa alertas ni seguimiento automatico
- no reemplaza la propuesta preferida actual; solo marca una referencia persistente

## Drift entre baseline y propuesta actual

La hoja `Planeacion` expone un seguimiento simple de drift entre:

- el baseline incremental activo
- la propuesta incremental preferida actual

Reglas del modulo:

- reutiliza el mismo contrato de comparacion ya usado para `snapshot guardado vs propuesta actual`
- no recalcula snapshots historicos
- clasifica el drift por metrica como:
  - `favorable`
  - `desfavorable`
  - `estable`

Metricas consideradas:

- expected return change
- real expected return change
- fragility change
- worst scenario loss change
- top risk concentration change

Uso previsto:

- detectar si la propuesta actual mejora o empeora frente a la referencia operativa elegida
- sostener seguimiento manual sin abrir un sistema de alertas nuevo

Limitaciones:

- el drift se mide solo contra el baseline activo, no contra todo el historial
- la clasificacion es heuristica por direccion de mejora, no un score nuevo
- no hay alertas persistentes ni notificaciones automaticas

## Alertas livianas de drift

Sobre el bloque de drift, `Planeacion` expone alertas livianas por request.

Reglas del modulo:

- no persiste alertas en `Alert`
- no agrega cron ni seguimiento automatico
- deriva avisos directamente desde el resumen de drift actual

Tipos de lectura:

- `info` cuando no hay drift material
- `warning` cuando el drift es mixto o hay metricas desfavorables
- `critical` cuando el drift global es desfavorable y acumula multiples deterioros

Uso previsto:

- dar una lectura operativa rapida sin salir de `Planeacion`
- marcar cuando la propuesta actual ya se alejo del baseline elegido

Limitaciones:

- son alertas efimeras, no historicas
- no reemplazan el bloque de drift detallado
- no se integran al centro global de alertas del dashboard

## Resumen ejecutivo de seguimiento incremental

La hoja `Planeacion` sintetiza una lectura ejecutiva sobre:

- propuesta incremental preferida actual
- baseline incremental activo
- drift entre ambos

Objetivo:

- resolver rapido si la situacion esta:
  - alineada
  - para seguimiento cercano
  - para revision
  - pendiente por falta de baseline o propuesta

Reglas del modulo:

- no agrega scoring nuevo
- reutiliza `comparison_score` y el resumen de drift existente
- compacta el estado en una sola lectura server-rendered

Limitaciones:

- resume, no reemplaza el detalle analitico
- la decision ejecutiva sigue siendo heuristica
- no persiste una bitacora de estados ejecutivos

## Checklist de adopcion de propuesta incremental

La hoja `Planeacion` agrega un checklist operativo minimo antes de pasar de propuesta a decision manual.

Inputs reutilizados:

- propuesta incremental preferida actual
- baseline incremental activo
- drift respecto del baseline
- alertas livianas de drift

Checks MVP:

- existe propuesta incremental preferida
- la propuesta tiene compra resumida
- existe baseline incremental activo
- el drift no es desfavorable
- no hay alertas criticas de drift

Salida:

- estado general:
  - `ready`
  - `review`
  - `pending`
- cantidad de checks aprobados
- detalle por check

Limitaciones:

- no ejecuta ni bloquea acciones reales
- no reemplaza criterio humano
- sigue siendo una validacion operativa simple y heuristica

## Workflow de decision manual

La hoja `Planeacion` agrega un workflow manual minimo sobre snapshots incrementales ya guardados.

Objetivo:

- registrar si un snapshot fue aceptado, diferido o rechazado
- dejar trazabilidad operativa separada del calculo analitico

Implementacion MVP:

- reutiliza `IncrementalProposalSnapshot`
- persiste:
  - `manual_decision_status`
  - `manual_decision_note`
  - `manual_decided_at`
- expone un resumen de la ultima decision manual registrada
- permite decidir desde el historial reciente por `POST`

Estados:

- `accepted`
- `deferred`
- `rejected`

Limitaciones:

- la decision vive sobre snapshots guardados, no sobre propuestas efimeras
- no hay workflow multi-etapa ni aprobacion colaborativa
- no existe una vista dedicada fuera de `Planeacion`

## Lectura operativa del historial por estado

La hoja `Planeacion` permite filtrar el historial incremental por estado de decision manual.

Estados soportados:

- `pending`
- `accepted`
- `deferred`
- `rejected`

Objetivo:

- separar rapido propuestas pendientes de propuestas ya resueltas
- dar una lectura operativa del backlog incremental sin crear otra superficie

Salida:

- filtro activo
- conteos por estado
- headline operativo segun el filtro aplicado

Limitaciones:

- el filtro es solo de lectura
- no agrega persistencia nueva
- no reemplaza una vista historica dedicada

## Acciones masivas minimas sobre historial

La hoja `Planeacion` permite aplicar una decision manual comun a los snapshots actualmente visibles en el historial filtrado.

Objetivo:

- acelerar cierre operativo del backlog incremental
- reutilizar el mismo historial y los mismos estados ya existentes

Reglas del MVP:

- la accion masiva opera solo sobre las filas visibles
- respeta el filtro activo del historial
- permite marcar visibles como:
  - `accepted`
  - `deferred`
  - `rejected`

Limitaciones:

- no permite seleccionar filas arbitrarias
- no hay confirmacion avanzada ni preview del lote
- no actualiza notas en bloque desde UI
