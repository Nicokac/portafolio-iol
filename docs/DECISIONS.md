# DECISIONS.md — Portafolio IOL

Registro de decisiones de diseño que una auditoría podría marcar como issue.

---

## D-001 — Celery beat_schedule eliminado de celery.py

**Issue relacionada:** H-OPS-03  
**Fecha:** 2026-03-09  
**Estado:** ✅ Implementado

### Contexto
`celery.py` definía `beat_schedule` hardcodeado mientras `settings/base.py` configuraba
`CELERY_BEAT_SCHEDULER = DatabaseScheduler`. El `DatabaseScheduler` ignora `app.conf.beat_schedule`
por diseño, por lo que las tasks nunca se ejecutaban automáticamente.

### Decisión
Eliminar `beat_schedule` de `celery.py`. Las tasks periódicas se configuran exclusivamente
desde el admin de Django (`/admin/django_celery_beat/`) cuando Celery esté operativo.

### Riesgo aceptado
Las tasks no se ejecutan automáticamente hasta que se configuren desde el admin.
Aceptable mientras el entorno de producción no tenga Redis disponible (Render Free Tier).

---

## D-002 — Celery/Redis postergado para fase posterior

**Issue relacionada:** H-OPS-05  
**Fecha:** 2026-03-09  
**Estado:** ⏳ Pendiente

### Contexto
Celery requiere Redis como broker. Render Free Tier no incluye Redis.
La app tiene tareas de sincronización con IOL API definidas pero no operativas.

### Decisión
Mantener Celery en el proyecto sin operarlo en producción hasta definir
la estrategia de infraestructura (Render Hobby Tier con Redis, o reemplazo por APScheduler).

### Riesgo aceptado
Las sincronizaciones automáticas con IOL API no corren en producción.
Los datos del portafolio requieren actualización manual hasta resolver este punto.

---

## D-003 - PortfolioParameters blindado con validacion y constraints

**Issue relacionada:** H04  
**Fecha:** 2026-03-22  
**Estado:** Implementado

### Contexto
`PortfolioParameters` dependia de validaciones en Python para comprobar que la asignacion objetivo sumara `100` y que ciertos porcentajes quedaran dentro de rangos razonables.

Eso dejaba una brecha entre:

- validacion de aplicacion
- persistencia real en base de datos

### Decision
Blindar `PortfolioParameters` en dos niveles:

- validacion de modelo con `clean()` para errores legibles
- `CheckConstraint` en base para rangos y suma total de targets

Ademas, el endpoint de actualizacion de parametros ahora ejecuta `full_clean()` antes de guardar para devolver `400` controlado en lugar de fallas opacas.

### Riesgo aceptado
La restriccion de `risk_free_rate` queda acotada a `-100..100` como rango operativo conservador.
Si mas adelante aparece un caso real que requiera otro rango, el ajuste debe hacerse de forma explicita con migracion y tests.


---

## D-004 - IOLToken guardado de forma atomica

**Issue relacionada:** H09  
**Fecha:** 2026-03-22  
**Estado:** Implementado

### Contexto
`IOLToken.save_token()` eliminaba todos los tokens y luego creaba uno nuevo.

Ese patron introducia una ventana de inconsistencia: si el `create()` fallaba despues del `delete()`, la app podia quedar sin token persistido valido.

### Decision
Mantener la semantica operativa de un unico token vigente, pero reemplazar `delete() + create()` por actualizacion atomica dentro de transaccion.

Comportamiento final:

- si no existe token, se crea uno nuevo
- si existe uno, se reutiliza la fila mas reciente
- cualquier fila extra se purga dentro de la misma transaccion

### Riesgo aceptado
Se mantiene la decision de negocio de guardar un unico token IOL vigente en base.
Si en el futuro aparece un caso multi-cuenta o multi-credencial, el modelo debe evolucionar explicitamente en lugar de acumular multiples filas implicitas.


---

## D-005 - Data stamp cacheado para selectors del dashboard

**Issue relacionada:** B1  
**Fecha:** 2026-03-22  
**Estado:** Implementado

### Contexto
Los selectors del dashboard ya tenian cache por resultado, pero cada llamada cacheada recalculaba de todos modos el `data_stamp` consultando tablas base para invalidacion.

En pantallas densas como `Resumen` y `Planeacion`, eso multiplicaba queries de bajo valor aun cuando el resultado principal ya estaba cacheado.

### Decision
Cachear tambien el `data_stamp` durante la misma ventana TTL de los selectors.

Con esto:

- la primera llamada sigue calculando el stamp desde base

---

## D-006 - Planeacion incorpora costo operativo observado como senal tactica

**Issue relacionada:** P-OPS-01  
**Fecha:** 2026-03-24  
**Estado:** Implementado

### Contexto
`Planeacion` ya usaba huella operativa reciente para cobertura y fragmentacion, pero seguia faltando una lectura compacta del costo observado en ejecuciones comparables.

### Decision
Agregar una senal tactica de costo visible usando `aranceles visibles / monto ejecutado comparable` sobre operaciones terminadas recientes de `OperacionIOL`.

La decision engine ahora diferencia entre:

- falta de cobertura operativa
- fragmentacion operativa
- costo observado alto o a vigilar

### Riesgo aceptado
La metrica usa aranceles visibles y monto ejecutado como proxy operativo simple.
No modela todavia spread, slippage ni conversion FX implicita, por lo que se interpreta como friccion observada minima y no como costo total de ejecucion.
- las siguientes llamadas dentro de la ventana reutilizan ese stamp sin nuevas queries
- se reduce el costo repetido de invalidacion en cargas consecutivas del dashboard

### Riesgo aceptado
Se acepta una ventana corta de consistencia igual al TTL ya existente de los selectors.
No se introdujo una estrategia mas compleja de invalidacion inmediata para mantener el cambio acotado y de bajo riesgo.


---

## D-006 - Indices operativos para alertas e historial incremental

**Issue relacionada:** B2  
**Fecha:** 2026-03-22  
**Estado:** Implementado

### Contexto
El producto consulta con frecuencia:

- alertas activas por severidad y fecha
- snapshots incrementales por usuario, estado manual, backlog front y baseline

Los modelos ya estaban funcionales, pero no reflejaban esas rutas de acceso en indices especificos.

### Decision
Agregar indices operativos acotados a los filtros y ordenes que hoy usa el producto:

- `Alert(is_active, severidad, created_at)`
- `IncrementalProposalSnapshot(user, manual_decision_status, created_at)`
- `IncrementalProposalSnapshot(user, is_backlog_front, manual_decision_status, created_at)`
- `IncrementalProposalSnapshot(user, is_tracking_baseline, created_at)`

### Riesgo aceptado
Se agrega costo marginal de escritura por mantenimiento de indices, aceptado porque el producto prioriza lectura operativa rapida y los volumnes de escritura siguen siendo moderados.
# Decisions

## 2026-03-22 - Planeacion reutiliza metricas reales de operaciones para futuras compras

Se agrego una lectura compacta de `Huella real de ejecucion reciente` en `Planeacion`.

Decision:

- reutilizar `OperacionIOL` ya persistido
- reutilizar `build_operation_execution_analytics_context()` de `apps/operaciones_iol/selectors.py`
- no abrir una tabla nueva ni un servicio paralelo de slippage

Motivo:

- el repo ya tenia datos reales de fills, aranceles y monto ejecutado
- faltaba exponerlos en la decision de compra futura dentro de `Planeacion`
- el ROI inmediato es mayor que inventar una capa cuantitativa nueva

Limite deliberado:

- la lectura sigue siendo tactica y reciente
- no se modela slippage robusto
- no se persiste una serie propia de calidad de ejecucion por simbolo

## 2026-03-22 - El motor de decision usa huella operativa real como compuerta aparte

Se agrego `operation_execution_signal` al `decision_engine_summary`.

Decision:

- separar la huella operativa real de la senal de liquidez reciente
- bloquear o degradar la recomendacion cuando falte evidencia operativa comparable
- no mezclar esta capa con `parking`

Motivo:

- `parking`, liquidez reciente de mercado y ejecucion real no son el mismo problema
- una propuesta puede tener mercado razonable pero no tener referencia operativa propia suficiente
- la decision mensual necesitaba distinguir esa falta de evidencia antes de ejecutar

Efecto actual:

- `execution_gate` puede pasar a `review_execution`
- la confianza baja si la huella operativa es parcial, ausente o muy fragmentada
- el tracking payload ya persiste esta senal de governance

## 2026-03-22 - La propuesta sugerida expone calidad operativa por simbolo

Se agrego una lectura comparativa por simbolo dentro de la propuesta preferida.

Decision:

- no cambiar el ranking base de propuestas
- agregar una capa de lectura operativa por tramo de compra
- marcar cual simbolo tiene mejor huella operativa visible y cual pide mas validacion

Motivo:

- una propuesta multi-activo puede ser buena en agregado pero muy desigual en ejecutabilidad
- el usuario necesitaba ver rapido que tramo parece mas limpio y cual conviene tratar con mas cautela

Efecto actual:

- la propuesta sugerida puede indicar `Ejecutar primero`
- no cambia el ranking global de propuestas
- solo ordena mejor la lectura operativa dentro de la propuesta ya elegida

- La reaplicacion de propuestas al comparador manual tambien preserva el orden de ejecucion sugerido por simbolo cuando esa metadata ya existe en la propuesta preferida.

- El comparador manual ahora resume la readiness operativa del mejor plan usando la misma senal de ejecucion real que la propuesta sugerida principal.

- Cuando dos planes manuales quedan dentro de una brecha corta de score, el comparador puede desempatar por calidad operativa real y deja esa razon visible en UI.

- El comparador por candidato tambien puede desempatar por calidad operativa real cuando dos activos del mismo bloque quedan muy cerca en score.

- El comparador por split tambien reutiliza la huella real de ejecucion para resumir readiness y desempatar entre concentrar o dividir cuando el score queda muy cerca.

- Los comparadores por candidato, split y manual ahora muestran la readiness operativa por fila para no depender solo del resumen superior.

- El comparador incremental general tambien expone readiness operativa por fila para las variantes automaticas del aporte mensual.

- Los cuatro comparadores incrementales ahora comparten un mismo payload de summary y partials de template para reducir duplicacion de labels, badges y bloques de readiness.
- La unificacion mantiene fallback sobre los contratos previos del contexto para no romper tests de vista ni ramas con payload minimo.
- Los comparadores incremental general, por candidato, por split y manual ahora aceptan filtro por readiness operativa (`all`, `ready`, `review_execution`, `monitor`) sobre el set visible, sin alterar el score base ni la heuristica de ranking.
- Los formularios de comparadores incrementales ahora preservan el estado util de los otros comparadores mediante hidden inputs y reset URLs especificos para evitar perder contexto de trabajo dentro de `Planeacion`.
- `Planeacion` ahora resume arriba del bloque de exploracion que comparadores siguen activos, que bloque se esta evaluando y que filtros de readiness siguen aplicados para reducir friccion de navegacion.

---

## D-007 — Descomposicion modular de `apps/dashboard/selectors.py`

**Fecha:** 2026-03-25
**Estado:** ✅ Implementado

### Por que se refactorizo

`selectors.py` habia crecido hasta ~1600 lineas acumulando funciones de dominio muy distintos: portfolio, distribucion, riesgo, analitica mensual, incrementales de simulacion, backlog, seguimiento y orchestradores de decision. La falta de cohesion interna dificultaba el testing unitario, obligaba a mocks de namespaces globales y acoplaba indirectamente todos los modulos entre si.

### Zonas extraidas

Extraer `selectors.py` en modulos funcionales acotados, en cinco zonas:

| Zona | Modulo destino | Contenido |
| ---- | -------------- | --------- |
| 1 | `selector_cache.py`, `portfolio_analytics.py`, `portfolio_distribution.py`, `portfolio_risk.py` | cache, analytics mensual, distribuciones y riesgo |
| 2 | `portfolio_enrichment.py`, `historical_rebalance.py`, `market_signals.py` | enriquecimiento, rebalanceo historico y senales de mercado |
| 3 | `incremental_simulation.py` | simulacion, comparadores, propuesta preferida, plan mensual, ejecucion |
| 4 | `incremental_backlog.py` | backlog operativo, decision executive, followup, adoption checklist |
| 5 | `incremental_planeacion.py` | `get_decision_engine_summary` y `get_planeacion_incremental_context` |

`selectors.py` quedo como fachada delgada (~570 lineas) que re-exporta los simbolos publicos para compatibilidad con vistas y tests existentes.

Las funciones de Zona 5 que dependian de funciones todavia en `selectors.py` (`get_macro_local_context`, `get_analytics_v2_dashboard_summary`, `get_portfolio_parking_feature_context`, `get_market_snapshot_history_feature_context`) usan lazy imports dentro del cuerpo de la funcion para evitar importaciones circulares.

### Riesgo de lazy imports

Los lazy imports son un patron aceptado en Django para ciclos de importacion. La penalizacion en performance es nula porque Python cachea modulos en `sys.modules` tras la primera carga.

Tests en `test_selectors.py` que antes parchaban `apps.dashboard.selectors.X` fueron actualizados al modulo real donde cada funcion vive, siguiendo la regla de mock "patch-where-it's-used".

---

## D-008 - Refactor transversal de modulos grandes en dashboard y core

**Fecha:** 2026-03-25
**Estado:** Implementado

### Contexto

Despues de la descomposicion inicial de `selectors.py`, todavia quedaban modulos grandes y con mezcla de responsabilidades tanto en `apps/dashboard` como en `apps/core/services`.

En particular, la capa incremental de `Planeacion`, los servicios de asignacion mensual, recomendaciones, contexto macro local y soporte de snapshot de mercado seguian acumulando:

- logica de orquestacion
- reglas de negocio
- builders de payload
- UI/plumbing para tests o wrappers publicos

Eso hacia mas costoso testear piezas chicas y obligaba a tocar archivos grandes para cambios menores.

### Decision

Cerrar una tanda acotada de refactor sobre diez modulos de mayor valor tecnico, extrayendo helpers cohesivos y manteniendo las fachadas publicas para compatibilidad con vistas, tests y puntos de `patch()`.

Modulos intervenidos en esta tanda:

- `apps/dashboard/incremental_simulation.py`
- `apps/dashboard/views.py`
- `apps/dashboard/incremental_comparators.py`
- `apps/dashboard/incremental_planeacion.py`
- `apps/dashboard/incremental_history_enrichment.py`
- `apps/dashboard/selectors.py`
- `apps/core/services/iol_historical_price_service.py`
- `apps/core/services/monthly_allocation_service.py`
- `apps/core/services/local_macro_series_service.py`
- `apps/core/services/recommendation_engine.py`

Modulos soporte creados o consolidados:

- `incremental_simulation_comparison.py`
- `dashboard_incremental_actions.py`
- `incremental_comparator_ui.py`
- `incremental_planeacion_context.py`
- `incremental_history_sources.py`
- `dashboard_overview.py`
- `iol_market_snapshot_support.py`
- `monthly_allocation_rules.py`
- `local_macro_context.py`
- `recommendation_signal_support.py`

### Criterio aplicado

- conservar contratos publicos
- mantener wrappers cuando los tests patchaban sobre la fachada original
- separar orquestacion de reglas o builders puros
- agregar tests directos al modulo extraido antes de considerar cerrado el corte

### Riesgo aceptado

Se acepta mantener algunas fachadas delgadas y re-exportaciones mientras sigan aportando compatibilidad con tests y puntos de integracion existentes.

El objetivo de esta tanda fue bajar acoplamiento y mejorar testabilidad sin introducir un cambio funcional visible ni reescribir consumidores en cascada.

---

## D-009 - Bootstrap local de `ParametroActivo` y market snapshot persistido como contrato operativo

**Fecha:** 2026-03-26
**Estado:** Implementado

### Contexto

En un entorno local nuevo, la app podia arrancar con datos patrimoniales reales pero sin `ParametroActivo`, porque esa metadata vive en la base local y no viaja entre computadoras por si sola.

Eso degradaba `Estrategia`, `Planeacion` y partes de `Analytics v2` a lecturas de `N/A`, porcentajes en cero o taxonomia incompleta aunque el portfolio estuviera correctamente sincronizado.

Ademas, el refresh de `market snapshot IOL` persistia observaciones en `IOLMarketSnapshotObservation`, pero la UI dependia demasiado del cache puntual en memoria. Si el proceso reiniciaba o el cache expiraba, la capa operativa podia volver a mostrar `Snapshot puntual pendiente` pese a tener observaciones ya guardadas en DB.

Finalmente, varias metricas numericas del dashboard (`covarianza`, `VaR`, `CVaR`, `volatilidad`, `tracking error`) seguian expuestas a `NaN` o `inf` en series de retornos, generando `RuntimeWarning` en la carga del home.

### Decision

Consolidar el contrato operativo de estas tres capas:

- `ParametroActivo` se bootstrappea con `python manage.py cargar_metadata`, que ahora soporta `--dry-run`, es idempotente y reporta `Creado`, `Actualizado` o `Sin cambios`
- el `market snapshot` puntual se considera persistencia reutilizable, no solo cache efimero: la UI puede reconstruir el payload desde `IOLMarketSnapshotObservation` cuando no haya cache en memoria
- los servicios cuantitativos principales sanitizan retornos no finitos antes de calcular dispersion o percentiles

### Efecto operativo

- un entorno local nuevo puede recuperar rapidamente taxonomia base sin carga manual fila por fila
- `Estrategia` deja de depender de que exista una DB historica copiada desde otra maquina
- la capa operativa puntual del dashboard sobrevive a reinicios del proceso mientras existan observaciones recientes persistidas
- desaparecen warnings numericos espurios durante la carga del home y la lectura de riesgo queda mas robusta frente a historia parcial

### Riesgo aceptado

El bootstrap de `ParametroActivo` sigue siendo una taxonomia inicial y puede requerir ajustes manuales finos para ciertos activos.

Tambien se acepta que `CotizacionDetalle` pueda devolver precio puntual sin puntas visibles; en ese caso la UI muestra `Sin libro visible` aunque el refresh haya sido correcto.

---

## D-010 - Historicos diarios hibridos: IOL tactico + yfinance para Equity/CEDEAR/ETF

**Fecha:** 2026-03-26
**Estado:** Implementado

### Contexto

El endpoint `seriehistorica` de IOL quedo correctamente integrado en el cliente, pero en pruebas reales mostro comportamiento remoto inestable para consumo productivo como fuente principal de historicos diarios.

Al mismo tiempo:

- `CotizacionDetalleMobile` y `CotizacionDetalle` ya resolvieron bien la capa tactica del momento
- `yfinance` mostro cobertura util para una parte relevante del universo accionario local
- los consumers cuantitativos ya dependen de `IOLHistoricalPriceSnapshot` como almacenamiento comun

### Decision

Adoptar una estrategia hibrida:

- mantener IOL como fuente principal de snapshot puntual, operabilidad y lectura tactica
- usar `yfinance` como fuente complementaria de historicos diarios para `Equity`, `CEDEAR` y `ETF`
- persistir ambos orígenes en `IOLHistoricalPriceSnapshot`, diferenciando con `source`
- hacer que `build_close_series()` pueda leer series historicas aun cuando la data disponible venga de `yfinance`

### Alcance

Cobertura esperada en esta etapa:

- `Equity`
- `CEDEAR`
- `ETF`

Fuera de alcance por ahora:

- bonos locales
- cauciones
- FCI / cash management
- cualquier instrumento cuya cobertura en Yahoo no sea confiable

### Riesgo aceptado

`yfinance` no reemplaza un proveedor oficial con SLA fuerte. Se acepta su uso solo como fuente complementaria para historicos diarios de activos accionarios mientras:

- siga mejorando cobertura real del portfolio
- no reemplace la capa tactica actual basada en IOL
- se mantenga trazabilidad explicita de fuente via `source="yfinance"`
