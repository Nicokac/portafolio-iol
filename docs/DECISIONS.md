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
