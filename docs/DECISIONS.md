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
