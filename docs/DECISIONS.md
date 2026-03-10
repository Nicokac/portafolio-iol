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