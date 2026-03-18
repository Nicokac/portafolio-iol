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

## Comparacion operativa entre backlog pendiente y baseline activo

La hoja `Planeacion` agrega una lectura operativa del backlog pendiente contra el baseline incremental activo.

Objetivo:

- priorizar rapido snapshots pendientes ya guardados
- detectar si el backlog contiene alternativas mejores que la referencia vigente
- reutilizar la comparacion incremental ya existente sin recalcular analitica nueva

Inputs reutilizados:

- `get_incremental_proposal_tracking_baseline()`
- `get_incremental_proposal_history(..., decision_status="pending")`
- `_build_incremental_snapshot_comparison(...)`
- `_build_incremental_baseline_drift_summary(...)`

Salida:

- conteo de snapshots pendientes que:
  - superan baseline
  - empatan baseline
  - quedan por debajo
- candidato operativo prioritario
- tabla compacta por snapshot pendiente

Limitaciones:

- compara solo backlog pendiente visible
- no reordena ni persiste prioridades nuevas
- sigue usando score y deltas ya existentes

## Priorizacion operativa explicita del backlog incremental

La hoja `Planeacion` agrega una lectura ordenada del backlog pendiente para que el usuario vea rapido que revisar primero.

Objetivo:

- transformar la comparacion backlog vs baseline en prioridad accionable
- ordenar snapshots pendientes sin cambiar score ni decision manual
- mantener el workflow operativo en la misma superficie

Reglas del MVP:

- prioridad `alta`:
  - el snapshot pendiente supera al baseline activo
- prioridad `media`:
  - el snapshot pendiente empata con el baseline
- prioridad `baja`:
  - el snapshot pendiente queda por debajo del baseline

Salida:

- conteo por prioridad
- top item operativo
- proximo paso sugerido por snapshot

Limitaciones:

- la prioridad es derivada y heuristica
- no persiste orden nuevo del backlog
- no reemplaza la decision manual final

## Resumen operativo del frente de backlog y baseline

La hoja `Planeacion` agrega una sintesis corta para leer rapido que referencia manda y que snapshot queda primero para revision.

Objetivo:

- condensar baseline activo y frente del backlog en una sola lectura
- evitar tener que recorrer toda la seccion operativa para entender el estado actual
- reutilizar la priorizacion y el baseline ya calculados

Inputs reutilizados:

- `get_incremental_proposal_tracking_baseline()`
- `get_incremental_backlog_prioritization()`

Salida:

- headline operativo
- baseline activo
- frente del backlog
- prioridad del frente
- score relativo vs baseline

Limitaciones:

- no agrega logica nueva de priorizacion
- no reemplaza el detalle de backlog ni el historial
- sigue siendo una sintesis heuristica de lectura

## Semaforizacion operativa del backlog incremental

La hoja `Planeacion` agrega un semaforo simple para leer rapido el estado operativo incremental.

Objetivo:

- sintetizar drift, baseline y backlog en una señal unica
- ayudar a decidir si conviene revisar backlog o sostener baseline
- mantener una lectura server-rendered y explicable

Reglas del MVP:

- `rojo`:
  - drift desfavorable frente al baseline
- `amarillo`:
  - existe backlog alta prioridad
  - o el frente del backlog supera al baseline
  - o el frente fue promovido manualmente
- `verde`:
  - drift favorable/estable y sin backlog urgente
- `gris`:
  - señal insuficiente

Limitaciones:

- es una lectura operativa, no un score nuevo
- depende de estados ya derivados
- no reemplaza detalle de drift ni priorizacion

## Resumen ejecutivo unificado de decision incremental

La hoja `Planeacion` agrega una sintesis unica para cerrar la lectura operativa del aporte incremental.

Objetivo:

- resumir en una sola lectura si conviene adoptar, sostener baseline o revisar backlog
- evitar tener que combinar mentalmente semaforo, checklist, drift y frente del backlog
- mantener una salida server-rendered y explicable

Inputs reutilizados:

- `get_incremental_backlog_operational_semaphore()`
- `get_incremental_followup_executive_summary()`
- `get_incremental_adoption_checklist()`
- `get_incremental_backlog_front_summary()`

Estados del MVP:

- `adopt`
- `hold`
- `review_backlog`
- `review_current`
- `pending`

Limitaciones:

- es una sintesis heuristica
- no crea score nuevo ni persistencia adicional
- no reemplaza el detalle de checklist, drift o backlog

## Racionalizacion de la UI de Planeacion

La hoja `Planeacion` se reordeno para que la lectura recomendada arranque por `Aportes` y responda mas rapido la pregunta:

- que bloques reforzar
- que activos mirar
- cual propuesta incremental parece mejor
- que impacto tendria esa compra

Jerarquia visible actual dentro de `Aportes`:

- nucleo de decision:
  - propuesta de compra mensual
  - ranking de candidatos
  - propuesta incremental preferida
  - simulacion incremental default
- exploracion secundaria:
  - resumen ejecutivo unificado
  - comparador general de propuestas incrementales
  - comparadores especificos por candidato, split y plan manual en secciones secundarias
  - plan manual y herramientas alternativas
- seguimiento y governance:
  - baseline activo
  - ultima decision manual
  - historial reciente de propuestas guardadas

Bloques legacy que siguen en la hoja pero ya no ocupan el camino principal:

- simulacion tactica
- optimizacion teorica
- configuracion base
- plan mensual por perfil

Criterio de exposicion:

- sirven como soporte para validar o contrastar decisiones
- no deben competir visualmente con el flujo principal del aporte mensual

Bloques operativos retirados del render principal:

- checklist de adopcion
- resumen ejecutivo de seguimiento
- semaforo operativo del backlog
- resumen del frente de backlog
- drift detallado vs baseline
- backlog pendiente vs baseline
- priorizacion operativa explicita
- comparacion snapshot guardado vs propuesta actual

Criterio:

- mantener visible el nucleo decisional
- dejar exploracion y workflow manual disponibles, pero subordinados
- evitar duplicar varias lecturas derivadas del mismo estado incremental

## Deuda tecnica detectada

Hallazgos principales despues de la racionalizacion:

- `apps/dashboard/selectors.py` concentra demasiada logica incremental en un solo archivo
- siguen existiendo selectors operativos de backlog, drift y baseline que ya no se renderizan en la hoja principal
- `PlaneacionView` todavia orquesta muchos contratos incrementales en una sola vista
- varios comparadores comparten conceptos (`proposal_key`, `proposal_label`, `label`, `comparison_score`) con contratos parecidos pero no unificados
- el historial incremental mezcla concerns de:
  - snapshot persistido
  - baseline activo
  - backlog front
  - decision manual
- los tests de `Planeacion` quedaron sensibles a copy y a labels de UI, lo que aumenta costo de mantenimiento

Deuda prioritaria:

1. extraer un modulo o facade dedicado para selectors incrementales de `Planeacion`
2. unificar contrato de propuesta incremental reutilizado por comparadores, preferida e historial
3. separar mas claramente:
   - nucleo decisional
   - workflow manual
   - historial operativo
4. bajar la dependencia de tests respecto de copy exacto de template

No abordado en este modulo:

- refactor mayor de `selectors.py`
- migracion de workflow manual a una vista separada
- eliminacion de selectors legacy todavia reutilizables

## Fachada incremental de Planeacion

Para bajar acoplamiento en la capa dashboard, `PlaneacionView` consume ahora una unica fachada:

- `get_planeacion_incremental_context(...)`

Responsabilidad:

- concentrar el contrato incremental visible de la hoja
- delegar en los selectors ya existentes sin cambiar su logica
- mantener serializacion y forwarding consistente de:
  - `capital_amount`
  - `query_params`
  - `history_limit`
  - `user`

Objetivo del refactor:

- reducir wiring repetido en la view
- simplificar tests de `Planeacion`
- dejar un unico punto de entrada para futuros ajustes de superficie incremental

Queda fuera de alcance:

- unificar toda la logica incremental en un servicio nuevo
- cambiar los contratos de los selectors subyacentes
- mover workflow incremental fuera de `Planeacion`

## Contrato incremental comun

Los selectors incrementales de dashboard exponen ahora un shape base compartido para propuestas y snapshots:

- `proposal_key`
- `proposal_label`
- `label`
- `purchase_plan`
- `purchase_summary`
- `comparison_score`
- `simulation`
- `simulation_delta`

Objetivo:

- bajar friccion entre comparadores
- simplificar la propuesta preferida
- facilitar comparacion con snapshots historicos

Compatibilidad:

- se mantienen las claves historicas existentes
- `proposal_label` y `label` conviven como aliases compatibles
- `simulation_delta` queda disponible tanto en snapshots como en propuestas comparadas

## Serializacion del historial incremental

La normalizacion base de snapshots incrementales vive ahora en:

- `IncrementalProposalHistoryService.serialize(...)`
- `apps/core/services/incremental_proposal_contracts.py`

Ese punto devuelve el contrato comun minimo para snapshots persistidos:

- `proposal_label`
- `label`
- `purchase_plan`
- `purchase_summary`
- `comparison_score`
- `simulation`
- `simulation_delta`

El selector de historial en dashboard solo agrega enriquecimiento de lectura:

- labels de decision manual
- flag visible de backlog front
- querystring de reaplicacion

Helpers compartidos actuales:

- `build_incremental_purchase_plan_summary(...)`
- `normalize_incremental_proposal_payload(...)`
