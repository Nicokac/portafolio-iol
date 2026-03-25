# Roadmap de hardening y evolucion del producto

## Objetivo

Este roadmap traduce un diagnostico tecnico amplio en una secuencia operativa realista para `Portafolio IOL`.

El criterio principal no es solo bajar deuda tecnica. El foco es:

1. proteger integridad y seguridad de la base operativa
2. reducir friccion y costo de lectura en superficies criticas
3. mejorar la calidad de decision sobre futuras compras
4. descomprimir puntos de mantenimiento con mayor concentracion real

## Alcance

Aplica al producto actual server-rendered con Django, Celery, PostgreSQL y servicios analiticos en `apps/core/services/`.

Este documento reemplaza cualquier priorizacion apoyada en supuestos no verificados sobre tamanio o complejidad de archivos concretos.

## Verificaciones base usadas para este roadmap

Se verificaron directamente estos puntos del repositorio:

- `apps/core/services/iol_api_client.py` tiene 443 lineas, no ~19k
- `apps/api/views.py` tiene 1057 lineas
- `apps/dashboard/views.py` tiene 750 lineas
- `apps/dashboard/selectors.py` tenia 5848 lineas (D3 implementado 2026-03-25: reducido a ~569 lineas como fachada, ver D-007)
- `PortfolioParameters` no tiene `CheckConstraint` para suma de targets ni rangos
- `Alert` no tiene indices orientados a las consultas operativas principales
- `config/settings/base.py` define SQLite por default
- `config/settings/prod.py` usa `os.getenv()` directamente para email
- `IOLToken.save_token()` hace `delete()` + `create()` sin transaccion explicita
- `apps/core/utils/token_crypto.py` deriva el secreto desde `SECRET_KEY`
- no se detecto evidencia directa de `select_related` o `prefetch_related` en `dashboard/selectors.py`, `api/views.py` ni servicios inspeccionados

## Principios de priorizacion

### P0

Corresponde a puntos que pueden:

- comprometer integridad de datos
- romper operacion critica
- degradar directamente la calidad de decision de compra

### P1

Corresponde a puntos con alto impacto tecnico u operativo, pero sin riesgo inmediato de corrupcion funcional.

### P2

Corresponde a mejoras de ergonomia, escalabilidad futura o refactors de conveniencia que hoy no bloquean valor.

## Track A - Confiabilidad operativa

### Modulo A1 - Blindaje de integridad en `PortfolioParameters`

- Prioridad: `P0`
- Problema: la suma de targets y los rangos de parametros dependen hoy de validacion en Python, no de la base
- Evidencia:
  - `apps/core/models.py`
  - existe `is_valid_allocation()` pero no `CheckConstraint`
- Cambio esperado:
  - agregar `CheckConstraint` para suma de targets = 100
  - agregar constraints de rango para porcentajes y umbrales relevantes
- Impacto esperado:
  - evita configuraciones invalidas que distorsionen rebalanceo, planeacion y optimizacion
- Riesgo:
  - bajo, con migracion y saneamiento previo si hubiera registros inconsistentes
- Criterio de aceptacion:
  - migracion aplicada
  - tests de modelo y edge cases
  - documentacion actualizada en `README` o doc canonico que corresponda

### Modulo A2 - Atomicidad y endurecimiento de `IOLToken`

- Prioridad: `P0`
- Problema: `save_token()` elimina y recrea sin transaccion explicita
- Evidencia:
  - `apps/core/models.py`, metodo `IOLToken.save_token`
- Cambio esperado:
  - reemplazar `delete() + create()` por estrategia atomica
  - evaluar `transaction.atomic()` + `update_or_create()` o equivalente robusto
- Impacto esperado:
  - reduce ventana de inconsistencia en autenticacion IOL
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - tests de persistencia y regresion
  - no romper compatibilidad con `IOLTokenManager`
  - documentacion breve del comportamiento final

### Modulo A3 - Estrategia de rotacion para tokens cifrados

- Prioridad: `P1`
- Problema: el cifrado depende de `SECRET_KEY` sin versionado de clave
- Evidencia:
  - `apps/core/utils/token_crypto.py`
- Cambio esperado:
  - definir estrategia de versionado o migracion de claves
  - documentar explicitamente rotacion y recuperacion
- Impacto esperado:
  - evita bloqueo operativo ante rotaciones futuras de secretos
- Riesgo:
  - medio
- Criterio de aceptacion:
  - decision tecnica documentada
  - implementacion minima o plan de transicion aprobado

### Modulo A4 - Endurecimiento de configuracion de entornos

- Prioridad: `P1`
- Problema:
  - SQLite por default fuera de `dev`
  - lectura inconsistente de variables en `prod.py`
- Evidencia:
  - `config/settings/base.py`
  - `config/settings/prod.py`
- Cambio esperado:
  - dejar mas explicito el rol de `base`, `dev` y `prod`
  - unificar criterio de lectura de variables
- Impacto esperado:
  - reduce riesgo de misconfiguracion silenciosa
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - settings consistentes
  - chequeos de arranque o validacion mas claros
  - documentacion operativa actualizada

## Track B - Performance y observabilidad de lectura

### Modulo B1 - Auditoria de queries en dashboard

- Prioridad: `P1`
- Problema: posible costo oculto en selectores y vistas criticas
- Evidencia:
  - `apps/dashboard/selectors.py` tiene alta concentracion funcional
  - no se encontro evidencia directa de `select_related` / `prefetch_related`
- Cambio esperado:
  - medir queries y tiempo en:
    - `Resumen`
    - `Planeacion`
    - historial incremental
  - introducir optimizaciones ORM donde corresponda
- Impacto esperado:
  - menor latencia y menor costo por request
- Riesgo:
  - medio
- Criterio de aceptacion:
  - evidencia antes/despues
  - tests o assertions donde aplique
  - documentacion breve en pipeline/ops si cambia observabilidad

### Modulo B2 - Indices operativos faltantes

- Prioridad: `P1`
- Problema: algunas consultas frecuentes no tienen apoyo explicito de indices
- Evidencia:
  - `Alert` no muestra indice compuesto para `is_active`, `severidad`, `created_at`
- Cambio esperado:
  - agregar indices orientados a consultas reales
  - revisar tambien tablas de historial usadas por dashboard
- Impacto esperado:
  - mejora lectura de alertas, historial y paneles de seguimiento
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - migracion aplicada
  - queries criticas identificadas

### Modulo B3 - Cache selectivo de analytics costosos

- Prioridad: `P1`
- Problema: varios calculos con Pandas siguen en ciclo sincrono de request
- Cambio esperado:
  - cachear bloques de solo lectura con invalidador claro
  - priorizar analitica que se recalcula con alta frecuencia y baja variacion
- Impacto esperado:
  - reduce latencia percibida en `Estrategia` y `Planeacion`
- Riesgo:
  - medio
- Criterio de aceptacion:
  - politica de invalidacion documentada
  - sin degradar consistencia de datos sensibles

## Track C - Mejor decision para futuras compras

### Modulo C1 - Profundizacion de ejecucion y costos reales

- Prioridad: `P0 funcional`
- Problema: hoy la app ayuda mucho a decidir compras, pero todavia falta una capa mas fuerte de calidad real de ejecucion
- Oportunidad:
  - aprovechar mejor `operaciones/{numero}` y el historial operativo
- Cambio esperado:
  - enriquecer lectura de ejecucion con:
    - precio efectivo
    - costos y friccion observada
    - calidad de ejecucion por tipo de activo o contexto
- Impacto esperado:
  - mejora directa sobre decisiones futuras y rentabilidad neta
- Riesgo:
  - medio
- Dependencias:
  - mapa de endpoints IOL vigente
  - servicios de operaciones ya existentes
- Criterio de aceptacion:
  - nueva senal o resumen reutilizable en `Planeacion`
  - tests de integracion de servicio
  - docs de endpoint y flujo actualizados

### Modulo C2 - Senales nuevas orientadas a compra futura

- Prioridad: `P0 funcional`
- Problema: la capa actual ya usa `parking`, liquidez reciente y backlog incremental, pero aun puede profundizar mejor el criterio de compra
- Cambio esperado:
  - incorporar senales que afecten:
    - propuesta recomendada
    - costo esperado
    - ejecutabilidad
    - conveniencia entre backlog nuevo y reactivadas
- Impacto esperado:
  - mejor priorizacion de futuras compras
- Riesgo:
  - medio
- Criterio de aceptacion:
  - senales visibles y trazables en `Planeacion`
  - tests de selector y vista
  - docs del simulador incremental y pipeline actualizados

### Modulo C3 - Aprendizaje operacional del backlog incremental

- Prioridad: `P1 funcional`
- Problema: existe trazabilidad del workflow, pero todavia falta medir sistematicamente si las decisiones recomendadas convergen en mejores resultados
- Cambio esperado:
  - backtesting liviano del flujo incremental
  - comparacion entre propuestas recomendadas, baseline y decisiones tomadas
- Impacto esperado:
  - mejora el criterio futuro sin sobredisenio cuantitativo
- Riesgo:
  - medio
- Criterio de aceptacion:
  - resumen agregado interpretable
  - sin introducir complejidad tipo Monte Carlo

## Track D - Descompresion estructural

### Modulo D1 - Particion de `apps/api/views.py`

- Prioridad: `P1`
- Problema: concentracion de endpoints en un archivo de 1057 lineas
- Cambio esperado:
  - separar por dominio o recurso
  - mantener contratos actuales
- Impacto esperado:
  - menor costo de mantenimiento y mejor trazabilidad API
- Riesgo:
  - medio
- Criterio de aceptacion:
  - imports y urls estables
  - tests API sin regresion

### Modulo D2 - Particion de `apps/dashboard/views.py`

- Prioridad: `P1`
- Problema: la capa de vistas sigue creciendo con cada superficie nueva
- Cambio esperado:
  - separar vistas por seccion funcional conservando mixins compartidos
- Impacto esperado:
  - menor acoplamiento en presentacion
- Riesgo:
  - medio
- Criterio de aceptacion:
  - urls y templates estables
  - tests de vistas verdes

### Modulo D3 - Particion de `apps/dashboard/selectors.py`

- Prioridad: `P1`
- Estado: ✅ Implementado (2026-03-25) — ver D-007 en DECISIONS.md
- Problema: era el archivo mas concentrado del flujo de lectura del dashboard
- Evidencia original:
  - 5848 lineas verificadas
- Solucion aplicada:
  - extraido en 5 zonas funcionales:
    - `selector_cache.py`, `portfolio_analytics.py`, `portfolio_distribution.py`, `portfolio_risk.py`
    - `portfolio_enrichment.py`, `historical_rebalance.py`, `market_signals.py`
    - `incremental_simulation.py`
    - `incremental_backlog.py`
    - `incremental_planeacion.py`
  - `selectors.py` quedo como fachada delgada (~569 lineas) que re-exporta simbolos publicos
- Impacto logrado:
  - mejora de mantenibilidad y localizacion de cambios
  - tests actualizados al modulo real donde vive cada funcion
- Criterio de aceptacion cumplido:
  - contratos publicos sin cambios para vistas y tests existentes
  - suite de tests de selector estable

## Track E - UX de alto retorno

### Modulo E1 - Interactividad progresiva en `Planeacion`

- Prioridad: `P2`
- Problema: demasiada recarga completa para una hoja densa en decision operativa
- Cambio esperado:
  - introducir HTMX o Alpine.js solo en interacciones de alto retorno
- Impacto esperado:
  - menor friccion en filtros, shortlist e historial
- Riesgo:
  - medio
- Criterio de aceptacion:
  - mejora perceptible sin reescribir frontend completo

### Modulo E2 - Persistencia de estado de navegacion

- Prioridad: `P2`
- Problema: filtros, tabs y contexto se pierden con facilidad
- Cambio esperado:
  - recordar estado relevante de navegacion y filtros principales
- Impacto esperado:
  - menor costo cognitivo del flujo diario
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - comportamiento consistente y documentado

## Orden recomendado de ejecucion

1. Modulo A1 - Blindaje de integridad en `PortfolioParameters`
2. Modulo A2 - Atomicidad y endurecimiento de `IOLToken`
3. Modulo B1 - Auditoria de queries en dashboard
4. Modulo B2 - Indices operativos faltantes
5. Modulo C1 - Profundizacion de ejecucion y costos reales
6. Modulo C2 - Senales nuevas orientadas a compra futura
7. Modulo A4 - Endurecimiento de configuracion de entornos
8. Modulo D1 - Particion de `apps/api/views.py`
9. Modulo D2 - Particion de `apps/dashboard/views.py`
10. ~~Modulo D3 - Particion de `apps/dashboard/selectors.py`~~ ✅ (2026-03-25)
11. Modulo B3 - Cache selectivo de analytics costosos
12. Modulo E1 - Interactividad progresiva en `Planeacion`
13. Modulo E2 - Persistencia de estado de navegacion
14. Modulo A3 - Estrategia de rotacion para tokens cifrados
15. Modulo C3 - Aprendizaje operacional del backlog incremental

## Primer modulo sugerido

El mejor primer modulo para corregir ahora es `Modulo A1 - Blindaje de integridad en PortfolioParameters`.

Motivos:

- riesgo bajo y retorno alto
- evita configuraciones invalidas en una pieza transversal
- no exige refactor grande ni dependencias externas
- mejora directamente la confiabilidad de `Planeacion`, rebalanceo y optimizacion

## Documentacion a mantener alineada durante la ejecucion

Segun `AGENTS.md`, cada modulo que cambie comportamiento o contratos debe actualizar sus docs canonicos dentro del mismo trabajo.

Para este roadmap, los documentos que mas probablemente deban tocarse durante la ejecucion son:

- `README.md`
- `docs/data_pipeline.md`
- `docs/iol_endpoint_usage_map.md`
- `docs/incremental_portfolio_simulator.md`
- `docs/DECISIONS.md`

## Fuera de alcance inmediato

No se prioriza por ahora:

- migracion a frontend SPA
- soporte multiusuario real
- optimizacion cuantitativa avanzada adicional
- Monte Carlo o modelado de factores sofisticado
- refactor por estetica sin impacto claro en valor o riesgo
