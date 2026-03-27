# Roadmap de simplicidad UX v2.0

## Objetivo

Este roadmap traduce la auditoria de simplicidad UX en una secuencia operativa concreta para `Portafolio IOL`.

El criterio rector es simple:

1. sacar del flujo principal todo lo que no acelere una decision real
2. reducir friccion cognitiva antes de seguir agregando funcionalidad
3. separar claramente producto principal, modo experto y backoffice
4. endurecer el dominio donde hoy la simplicidad depende solo de disciplina de codigo

## Alcance

Aplica al producto Django server-rendered actual, con foco en:

- arquitectura de pantallas
- navegacion principal
- `Resumen`, `Estrategia`, `Planeacion` y `Ops`
- visibilidad de features `legacy`
- invariantes de dominio que hoy afectan claridad operativa

No intenta redisenar identidad visual completa ni rehacer frontend en SPA.

## Verificaciones base usadas para este roadmap

Se verificaron directamente estos puntos del repositorio:

- `templates/dashboard/planeacion.html` tiene `2289` lineas incluso despues del recorte principal
- `templates/dashboard/estrategia.html` tiene `201` lineas y ya funciona como hoja ejecutiva
- `templates/dashboard/resumen.html` tiene `464` lineas y sigue siendo la hoja diaria mas clara
- `templates/base.html` ya separa flujo principal de superficies tecnicas y usa `dashboard:dashboard` como ruta canonica de `Resumen`
- `apps/dashboard/views.py` ya no usa un solo `DashboardContextMixin`, pero todavia concentra acciones operativas que conviene seguir podando
- `apps/dashboard/urls.py` mezcla pantallas principales, detalles analiticos y acciones internas dentro de la misma familia de rutas
- `PortfolioParameters` ya expone validaciones en `clean()` y constraints de base alineados para rangos y suma de targets
- `OperacionIOL`, `PortfolioSnapshot` y `PositionSnapshot` requerian constraints de dominio explicitos para montos o cantidades invalidas
- `.github/workflows/ci.yml` tiene contenido real y no placeholders
- `Ops` ya fue simplificada con una ruta liviana basada en `build_ops_lite_summary()`
- `apps/dashboard/views.py` ya separa familias de contexto por superficie, con margen adicional para seguir desacoplando acciones internas
- `docs/dashboard_surface_inventory.md` ya distingue flujo principal, experto, staff visible y staff oculto

## Principios rectores

### P0

Corresponde a cambios que:

- eliminan friccion visible en el flujo principal
- reducen decisiones innecesarias
- mejoran directamente la velocidad mental para decidir compras, aportes o rebalanceos

### P1

Corresponde a cambios con alto impacto de claridad, pero que no bloquean el uso principal en el dia a dia.

### P2

Corresponde a mejoras estructurales o de prolijidad que apoyan el producto, pero no destraban valor inmediato.

## Estado actual del track

### Modulo ya implementado

- `A1 - Navbar minimo y separacion de superficies`
  - estado: `implementado`
  - resultado:
    - el navbar principal prioriza `Resumen`, `Planeacion` y `Estrategia`
    - `Análisis`, `Performance`, `Métricas` y superficies de soporte pasaron a un dropdown secundario
    - se retiró el selector visible de `ui_mode` del flujo principal
    - los accesos `legacy` dejaron de competir visualmente con la navegación principal
  - archivos principales:
    - `templates/base.html`
    - `apps/dashboard/tests/test_views.py`

- `B1 - Planeacion minimal para aporte mensual`
  - estado: `implementado`
  - resultado:
    - la hoja abre con un flujo principal centrado en `Aportes`
    - `Diagnóstico`, `Simulación`, `Optimización` y `Config base` quedaron detrás de `Herramientas complementarias`
    - la lectura principal ya no compite visualmente con cinco caminos simultáneos
  - archivos principales:
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`

- `B2 - Extraccion de simulacion y optimizacion a Laboratorio`
  - estado: `implementado`
  - resultado:
    - `Planeacion` ya no muestra simulacion tactica, contraste legacy, optimizacion ni config base dentro de la misma hoja
    - se creo `Laboratorio` como superficie separada para herramientas avanzadas
    - el flujo principal de aportes quedo aislado de herramientas secundarias
  - archivos principales:
    - `apps/dashboard/views.py`
    - `apps/dashboard/urls.py`
    - `templates/dashboard/planeacion.html`
    - `templates/dashboard/laboratorio.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`

- `C1 - Separar lectura estrategica de inventario detallado`
  - estado: `implementado`
  - resultado:
    - `Estrategia` quedo enfocada en lectura ejecutiva, analytics, riesgo y senales
    - el inventario completo y la capa operativa puntual pasaron a `Cartera detallada`
    - se redujo la mezcla entre lectura estrategica y auditoria de posiciones
  - archivos principales:
    - `apps/dashboard/views.py`
    - `apps/dashboard/urls.py`
    - `templates/dashboard/estrategia.html`
    - `templates/dashboard/cartera_detalle.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views_ux_simplicity.py`

- `C2 - Consolidacion de Analytics v2`
  - estado: `implementado`
  - resultado:
    - `Estrategia` paso de multiples tarjetas con CTAs competidores a una sola sintesis ejecutiva
    - se creo `Riesgo avanzado` como entrada unica para modulos analiticos profundos
    - bajo la fragmentacion de lectura dentro de la hoja estrategica
  - archivos principales:
    - `apps/dashboard/views.py`
    - `apps/dashboard/urls.py`
    - `templates/dashboard/estrategia.html`
    - `templates/dashboard/riesgo_avanzado.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views_ux_simplicity.py`

- `C3 - Correccion de labels y microcopy criticos`
  - estado: `implementado`
  - resultado:
    - se corrigieron labels visibles y microcopy confuso en `Estrategia`, `Cartera detallada` y `Riesgo avanzado`
    - la lectura principal usa nombres mas claros y menos jerga innecesaria
    - se eliminaron varios textos tecnicos que agregaban ruido sin aportar decision
  - archivos principales:
    - `templates/dashboard/estrategia.html`
    - `templates/dashboard/cartera_detalle.html`
    - `templates/dashboard/riesgo_avanzado.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views_ux_simplicity.py`

- `D1 - Retirar legacy del primer nivel`
  - estado: `implementado`
  - resultado:
    - los accesos `legacy` salieron del menu visible para usuario final
    - las superficies tecnicas quedaron encapsuladas en el dropdown de usuario para staff
    - `Planeacion` dejo de mencionar explicitamente contraste `legacy`
  - archivos principales:
    - `templates/base.html`
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_views.py`

- `D2 - Renombrado de pantallas ambiguas`
  - estado: `implementado`
  - resultado:
    - las superficies tecnicas quedaron nombradas de forma explicita y menos ambigua
    - `Datos IOL`, `Portafolio base`, `Config técnica` y `Ops / Observabilidad` pasaron a nombres mas claros para soporte tecnico
    - la diferencia entre flujo principal y herramientas de soporte quedo mas marcada
  - archivos principales:
    - `templates/base.html`
    - `templates/resumen_iol/resumen_list.html`
    - `templates/portafolio_iol/portafolio_list.html`
    - `templates/parametros/parametros_list.html`
    - `templates/operaciones_iol/operaciones_list.html`
    - `apps/dashboard/tests/test_views.py`

- `E1 - CheckConstraint para parametros y montos`
  - estado: `implementado`
  - resultado:
    - `PortfolioParameters` quedo alineado entre validacion Python y constraints declarados en el modelo
    - `OperacionIOL` ya rechaza montos y cantidades negativas a nivel base de datos
    - `PortfolioSnapshot` y `PositionSnapshot` ya rechazan montos negativos y pesos fuera de rango
  - archivos principales:
    - `apps/core/models.py`
    - `apps/core/tests/test_model_constraints.py`
    - `apps/operaciones_iol/models.py`
    - `apps/operaciones_iol/tests/test_model_constraints.py`
    - `apps/portafolio_iol/models.py`
    - `apps/portafolio_iol/tests/test_model_constraints.py`
    - `apps/operaciones_iol/migrations/0006_rename_operacione_pais_co_7f9ad6_idx_operaciones_pais_co_640e0d_idx_and_more.py`
    - `apps/portafolio_iol/migrations/0005_portfoliosnapshot_portfolio_snapshot_non_negative_amounts_and_more.py`

- `E2 - Auditoria de funciones y vistas realmente usadas`
  - estado: `implementado`
  - resultado:
    - se documento el inventario real de superficies del dashboard
    - quedo separada la clasificacion entre flujo principal, experto, staff visible y staff oculto
    - se dejaron identificadas como primera poda futura las acciones ocultas de historicos IOL
  - archivos principales:
    - `docs/dashboard_surface_inventory.md`
    - `docs/ux_simplicity_v2_roadmap.md`
    - `docs/README.md`

- `F1 - Ops Lite`
  - estado: `implementado`
  - resultado:
    - se mantuvo `Resumen unificado del pipeline`
    - se removio el detalle tecnico por simbolo de la vista principal
    - la ruta de backend paso de aproximadamente `5031 ms / 1756 queries` a `102 ms / 19 queries`
  - archivos principales:
    - `apps/core/services/pipeline_observability_service.py`
    - `apps/dashboard/views.py`
    - `templates/dashboard/ops.html`

- `A2 - Desacople de DashboardContextMixin`
  - estado: `implementado`
  - resultado:
    - `Resumen`, `Estrategia`, `Cartera detallada`, `Planeacion`, `Performance` y `Metricas` ya no reciben el mismo paquete grande de contexto
    - cada superficie carga solo las familias de datos que realmente renderiza
    - `Performance` y `Metricas` dejaron de heredar analytics, market snapshot, macro y portfolio completo
    - `Resumen` quedo como ruta canonica en `dashboard:dashboard`, mientras `dashboard:resumen` sigue como redirect de compatibilidad
  - archivos principales:
    - `apps/dashboard/views.py`
    - `apps/dashboard/urls.py`
    - `templates/base.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`
    - `apps/core/tests/test_url_conventions.py`

- `F2 - Historiales IOL fuera del dashboard web`
  - estado: `implementado`
  - resultado:
    - se retiraron del `dashboard` las tres rutas web ocultas de sincronizacion de historicos IOL
    - la operacion tecnica queda cubierta por `python manage.py sync_iol_historical_prices`
    - el command ahora soporta filtros por `--statuses` y `--eligibility-reason-keys`
    - el valor analitico de historicos IOL se conserva sin volver a inflar la superficie web
  - archivos principales:
    - `apps/dashboard/urls.py`
    - `apps/core/management/commands/sync_iol_historical_prices.py`
    - `apps/core/tests/test_sync_iol_historical_prices_command.py`
    - `apps/dashboard/tests/test_views.py`
    - `docs/dashboard_surface_inventory.md`

### Reevaluacion post-iteracion

La auditoria posterior a `G1` y `G2` muestra una mejora material del flujo principal, pero todavia quedan dos focos reales de friccion:

1. `Planeacion` sigue siendo la superficie mas pesada del producto con `2353` lineas, aunque ya oculto mas contexto secundario detras de detalles.
2. `Centro analitico` ya absorbio `Performance` y `Metricas`, pero ahora conviene vigilar que no vuelva a inflarse con nueva densidad visual o fetches innecesarios.

### Decisiones cerradas para fase 2

- Los historicos IOL si ayudan a mejorar la decision de compra, pero como soporte de calidad de senal, contexto de ejecucion y robustez analitica.
- Por simplicidad UX no deben volver al flujo principal como acciones visibles del dashboard.
- La ruta canonica de `Resumen` pasa a ser `dashboard:dashboard`.
- `dashboard:resumen` queda solo como alias de compatibilidad.
- `Analisis`, `Performance` y `Metricas` pueden converger en una fase posterior si el recorte mantiene claridad y no vuelve a inflar la hoja resultante.

### Proxima ola sugerida

- `H1 - Limpieza fina de aliases y documentacion residual`
- `H2 - Planeacion por bloques con carga diferida adicional`

### Fase 3 sugerida

La siguiente iteracion ya no deberia perseguir grandes movimientos de arquitectura. El foco pasa a ser:

1. cerrar residuos de transicion
2. vigilar que `Planeacion` no vuelva a inflarse
3. decidir si hace falta una `v3` de simplificacion o si conviene pasar a optimizacion puntual de producto

### Roadmap de fase 2

#### Modulo F2 - Historiales IOL fuera del dashboard web

- Prioridad: `P1`
- Problema:
  - las acciones de historicos IOL siguen vivas en routing, pero ya no tienen entrada visible ni deben competir con UX principal
- Cambio esperado:
  - mover esas acciones a admin, command o consola tecnica
  - mantener los historicos como pipeline de soporte para decisiones de compra, no como CTA de interfaz principal
- Criterio de aceptacion:
  - no quedan acciones de historicos IOL dentro de la familia web del dashboard principal
  - estado: `implementado`

#### Modulo F3 - Centro unificado de analisis

- Prioridad: `P1`
- Problema:
  - `Analisis`, `Performance` y `Metricas` ya se leen como una misma familia, pero siguen separados en tres pantallas
- Cambio esperado:
  - explorar una convergencia en una sola superficie analitica con subsecciones claras
  - preservar profundidad sin reintroducir una pantalla sobredimensionada
- Criterio de aceptacion:
  - propuesta de arquitectura unica o decision documentada de no converger
  - estado: `implementado`
  - resultado:
    - `Analisis` paso a ser el centro unico visible para composicion, performance y metricas
    - `dashboard:performance` y `dashboard:metricas` quedaron como redirects de compatibilidad a anclas internas
    - la navegacion dejo de mostrar tres accesos distintos para la misma familia analitica
  - archivos principales:
    - `apps/dashboard/views.py`
    - `templates/dashboard/analisis.html`
    - `templates/base.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`

#### Modulo F4 - Planeacion todavia mas liviana

- Prioridad: `P1`
- Problema:
  - `Planeacion` sigue siendo la superficie mas pesada del producto
- Cambio esperado:
  - lazy load de bloques secundarios
  - menos fetch iniciales
  - menor longitud visible antes de llegar a `Aportes`
- Criterio de aceptacion:
  - evidencia de menor carga inicial y menor ruido visual
  - estado: `implementado`
  - resultado:
    - el bloque de diagnostico previo ya no dispara fetch inicial al renderizar la hoja
    - `recommendations`, `alerts` y `rebalance` se cargan solo al abrir `Diagnostico previo`
    - el contexto operativo puntual quedo plegado detras de `Abrir contexto operativo opcional`
    - el flujo principal llega mas rapido a `Aportes` sin perder herramientas secundarias
  - archivos principales:
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_feature_flows.py`

#### Modulo G1 - Poda de vistas y templates ya absorbidos

- Prioridad: `P1`
- Problema:
  - la convergencia del centro analitico dejo artefactos de UI y documentacion que ya no sostienen una superficie propia
- Cambio esperado:
  - retirar templates absorbidos
  - alinear labels y rutas residuales con el nuevo centro analitico
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - los templates dedicados de `Performance` y `Metricas` fueron retirados
    - la familia analitica ya no conserva restos visuales de la separacion previa
    - el inventario del dashboard distingue mejor entre superficie visible y aliases de compatibilidad
  - archivos principales:
    - `templates/dashboard/performance.html`
    - `templates/dashboard/metricas.html`
    - `apps/dashboard/portfolio_enrichment.py`
    - `docs/dashboard_surface_inventory.md`

#### Modulo G2 - Reduccion adicional de densidad en Planeacion

- Prioridad: `P1`
- Problema:
  - aunque el flujo principal mejoro, la hoja sigue mostrando demasiado contexto antes y despues de la decision principal
- Cambio esperado:
  - plegar contexto patrimonial y bloques secundarios para que la decision aparezca antes
  - compactar accesos a laboratorio y soporte
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - `Laboratorio de apoyo` paso de card completa a alerta compacta
    - `Universo patrimonial` quedo plegado bajo demanda
    - la longitud visible inicial de la hoja baja sin perder informacion
  - archivos principales:
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_feature_flows.py`

#### Modulo H1 - Limpieza fina de aliases y documentacion residual

- Prioridad: `P2`
- Problema:
  - despues de la convergencia del centro analitico quedaron aliases y documentos describiendo superficies que ya no existen como pantallas separadas
- Cambio esperado:
  - alinear labels, inventarios y checklist de exposicion con el estado real del producto
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - la documentacion ya reconoce al `Centro analitico` como superficie unificada
    - `Performance` y `Metricas` quedan descriptos como aliases de compatibilidad
    - se retiraron templates ya absorbidos por la convergencia
  - archivos principales:
    - `docs/dashboard_surface_inventory.md`
    - `docs/analytics_v2_feature_exposure_checklist.md`
    - `apps/dashboard/portfolio_enrichment.py`
    - `templates/dashboard/performance.html`
    - `templates/dashboard/metricas.html`

#### Modulo H2 - Planeacion por bloques con carga diferida adicional

- Prioridad: `P1`
- Problema:
  - `Planeacion` mejoro, pero seguia mostrando demasiado contexto incluso despues de sacar laboratorio y plegar bloques secundarios
- Cambio esperado:
  - seguir compactando el recorrido principal y dejar visibles solo los pasos de decision mas importantes
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - `Validacion before/after` paso a quedar plegada bajo demanda
    - `Laboratorio de apoyo` ya no ocupa una card completa
    - la hoja explicita mejor que seguimiento y comparadores son capas secundarias
  - archivos principales:
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`

## Fase 3 - Simplificacion final y estabilizacion

### Modulo I1 - Roadmap v3 de simplificacion final

- Prioridad: `P2`
- Problema:
  - el track v2 ya hizo los recortes grandes y ahora falta decidir si queda una ronda final o si el producto entra en fase de mantenimiento fino
- Cambio esperado:
  - documentar una fase corta, con pocos modulos y criterios claros de cierre
- Criterio de aceptacion:
  - roadmap v3 documentado
  - decision explicita sobre si continuar simplificando o estabilizar

### Modulo I2 - Planeacion segmentada sin perder continuidad

- Prioridad: `P1`
- Problema:
  - la hoja principal sigue siendo larga aunque ya este mas limpia
- Cambio esperado:
  - evaluar una segmentacion suave por pasos o tabs internos:
    - decision
    - validacion
    - seguimiento
    - comparadores
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - `Planeacion` paso a separar `Validacion`, `Seguimiento` y `Comparadores` en panes internos suaves
    - el flujo principal de `Aportes` sigue primero y el CTA `Explorar alternativas` ahora baja directo a los bloques segmentados
    - la hoja mantiene continuidad visual sin obligar a leer todos los bloques secundarios al mismo tiempo
  - archivos principales:
    - `templates/dashboard/planeacion.html`
    - `apps/dashboard/tests/test_feature_flows.py`
    - `apps/dashboard/tests/test_views.py`

### Modulo I3 - Poda tecnica final del dashboard

- Prioridad: `P2`
- Problema:
  - despues de varias iteraciones pueden quedar aliases, clases o rutas que ya no justifican su costo de mantenimiento
- Cambio esperado:
  - revisar y podar residuos tecnicos del dashboard
- Criterio de aceptacion:
  - estado: `implementado`
  - resultado:
    - se eliminaron de `views.py` las vistas web de sync historico IOL que ya no tenian ruta ni entrada visible
    - se retiraron tests heredados que seguian apuntando a esas rutas obsoletas
    - el inventario tecnico ya refleja que esas capacidades viven solo como management commands
  - archivos principales:
    - `apps/dashboard/views.py`
    - `apps/dashboard/tests/test_views.py`
    - `docs/dashboard_surface_inventory.md`

## Track A - Navegacion y arquitectura de pantallas

### Modulo A1 - Navbar minimo y separacion de superficies

- Prioridad: `P0`
- Problema:
  - el navbar principal mezcla flujo de producto y accesos tecnicos o `legacy`
- Evidencia:
  - `templates/base.html`
  - `Resumen IOL`, `Portafolio`, `Operaciones` y `Parámetros` aparecen al mismo nivel que `Resumen`, `Planeación` y `Estrategia`
  - tambien aparece el selector `Vista rápida / Power user`
- Cambio esperado:
  - dejar en la navegacion principal solo:
    - `Resumen`
    - `Planeacion`
    - `Estrategia`
    - `Ops` solo si sigue siendo una vista minima
  - mover todo acceso `legacy` a menu tecnico, dropdown secundario o staff-only
  - eliminar el selector manual `Power user` si no prueba valor real
- Impacto esperado:
  - menos ruido de entrada
  - menos decisiones improductivas
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - navbar principal reducido
  - accesos tecnicos siguen disponibles fuera del flujo principal
  - smoke test de navegacion estable

### Modulo A2 - Desacople de `DashboardContextMixin`

- Prioridad: `P1`
- Problema:
  - demasiadas pantallas cargan contexto amplio por defecto
- Evidencia:
  - `apps/dashboard/views.py`
  - `DashboardContextMixin` agrega varias piezas compartidas aunque no todas sean necesarias para cada hoja
- Cambio esperado:
  - dividir el mixin en contextos por pantalla o por familia de necesidad
  - dejar a cada vista cargar solo lo que realmente muestra
- Impacto esperado:
  - menos acoplamiento
  - menor costo de request
  - mas claridad sobre el rol real de cada pantalla
- Riesgo:
  - medio
- Criterio de aceptacion:
  - `Resumen`, `Planeacion` y `Estrategia` ya no dependen del mismo paquete grande de contexto
  - evidencia antes/despues de queries o tiempo donde aplique

### Modulo A3 - Reduccion de detail views visibles

- Prioridad: `P1`
- Problema:
  - la arquitectura de urls expone demasiadas vistas analiticas como si fueran parte del flujo normal
- Evidencia:
  - `apps/dashboard/urls.py`
  - `estrategia` convive con varias detail views
- Cambio esperado:
  - consolidar rutas avanzadas bajo una familia tipo `laboratorio/` o `riesgo-avanzado/`
  - dejar solo una entrada clara desde el flujo principal
- Impacto esperado:
  - menor dispersion de la experiencia
- Riesgo:
  - medio
- Criterio de aceptacion:
  - menos rutas visibles desde templates principales
  - acceso avanzado preservado para analisis profundo

## Track B - Planeacion como flujo unico de decision

### Modulo B1 - Planeacion minimal para aporte mensual

- Prioridad: `P0`
- Problema:
  - `Planeacion` declara un flujo principal, pero muestra demasiados caminos al mismo tiempo
- Evidencia:
  - `templates/dashboard/planeacion.html`
  - conviven `Aportes`, `Diagnóstico previo`, `Simulación táctica`, `Optimización teórica` y `Config base`
  - el template supera las `2600` lineas
- Cambio esperado:
  - dejar visible por defecto solo:
    - objetivo de la hoja
    - propuesta de aporte
    - contexto minimo necesario
  - mover el resto a tabs secundarios ocultos o a `Laboratorio`
- Impacto esperado:
  - reduce la mayor fuente actual de sobrecarga cognitiva
- Riesgo:
  - medio
- Criterio de aceptacion:
  - la hoja principal puede leerse de arriba abajo como un solo flujo
  - el usuario no tiene que elegir entre cuatro caminos para hacer un aporte

### Modulo B2 - Extraccion de simulacion y optimizacion a `Laboratorio`

- Prioridad: `P0`
- Problema:
  - simulacion, optimizacion y generador `legacy` compiten con la decision principal
- Evidencia:
  - `templates/dashboard/planeacion.html`
  - el propio template reconoce que el generador `legacy` esta fuera del flujo incremental principal
- Cambio esperado:
  - crear una superficie secundaria:
    - `Laboratorio`
    - o `Modo experto`
  - mover ahi:
    - simulacion tactica
    - optimizacion teorica
    - generador `legacy`
- Impacto esperado:
  - `Planeacion` deja de ser una caja de herramientas y vuelve a ser una hoja de decision
- Riesgo:
  - medio
- Criterio de aceptacion:
  - `Planeacion` ya no muestra modulos avanzados en el flujo inicial
  - herramientas avanzadas siguen existiendo, pero desacopladas

### Modulo B3 - Reduccion de llamadas frontend no esenciales

- Prioridad: `P1`
- Problema:
  - la hoja dispara muchas cargas y acciones JS incluso cuando el usuario quiere solo decidir el aporte
- Evidencia:
  - `templates/dashboard/planeacion.html`
  - multiples fetch a recomendaciones, alertas, rebalanceo, simuladores y parametros
- Cambio esperado:
  - cargar lazy solo los modulos avanzados
  - no ejecutar cargas de laboratorio al entrar al flujo principal
- Impacto esperado:
  - mejor percepcion de velocidad
  - menos ruido tecnico
- Riesgo:
  - medio
- Criterio de aceptacion:
  - menor numero de fetch iniciales
  - evidencia real de mejora en carga inicial de `Planeacion`

## Track C - Estrategia como lectura ejecutiva

### Modulo C1 - Separar lectura estrategica de inventario detallado

- Prioridad: `P0`
- Problema:
  - `Estrategia` hoy intenta ser lectura ejecutiva, auditoria, analitica y tabla completa de posiciones
- Evidencia:
  - `templates/dashboard/estrategia.html`
  - conviven `Analytics v2`, `Resumen Analytics v2`, `Señales de Rebalanceo`, `Evolución Histórica`, `Posiciones completas` y `Capa operativa`
- Cambio esperado:
  - mantener en `Estrategia`:
    - composicion
    - riesgo agregado
    - señales sinteticas
  - mover:
    - posiciones completas
    - capa operativa puntual
    - detalles extensos
    a una vista secundaria de cartera detallada
- Impacto esperado:
  - mas foco y menos fatiga de lectura
- Riesgo:
  - medio
- Criterio de aceptacion:
  - `Estrategia` queda claramente orientada a lectura ejecutiva
  - el inventario completo ya no vive en la misma hoja

### Modulo C2 - Consolidacion de `Analytics v2`

- Prioridad: `P1`
- Problema:
  - hay capas analiticas repetidas o demasiado fragmentadas
- Evidencia:
  - en la misma hoja existe bloque `Analytics v2` y tambien `Resumen Analytics v2`
  - varios botones `Ver detalle` empujan a fragmentar la lectura
- Cambio esperado:
  - una sola sintesis ejecutiva de analytics
  - un solo acceso a riesgo avanzado
- Impacto esperado:
  - lectura mas limpia
  - menor sensacion de sobreingenieria
- Riesgo:
  - bajo a medio
- Criterio de aceptacion:
  - desaparece la duplicacion de resumenes
  - baja la cantidad de CTAs secundarios

### Modulo C3 - Correccion de labels y microcopy criticos

- Prioridad: `P1`
- Problema:
  - existen typos y textos tecnicos que erosionan claridad
- Evidencia:
  - `templates/dashboard/estrategia.html`
  - aparece `ltimo Precio` en columnas de tablas
- Cambio esperado:
  - corregir labels
  - homogeneizar naming
  - reducir texto justificativo largo en cards
- Impacto esperado:
  - mas confianza y menor rozamiento visual
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - sin typos en headers, botones o mensajes clave

## Track D - Reduccion de superficie `legacy`

### Modulo D1 - Retirar `legacy` del primer nivel

- Prioridad: `P0`
- Problema:
  - el producto ya reconoce internamente piezas `legacy`, pero muchas siguen visibles en la experiencia principal
- Evidencia:
  - `Planeacion` menciona explicitamente `Generador legacy`
  - navbar principal mezcla flujo moderno y pantallas heredadas
- Cambio esperado:
  - esconder `legacy` del flujo primario
  - dejarlo solo como soporte tecnico o de contraste temporal
- Impacto esperado:
  - menos contradiccion entre discurso de producto y experiencia real
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - el usuario final no ve elementos `legacy` salvo en modo tecnico o experto

### Modulo D2 - Renombrado de pantallas ambiguas

- Prioridad: `P1`
- Problema:
  - existen nombres que se pisan semantica o visualmente
- Evidencia:
  - `Resumen` y `Resumen IOL` coexisten
- Cambio esperado:
  - renombrar superficies heredadas con nombres tecnicos claros
  - ejemplo:
    - `Resumen IOL` -> `Datos IOL`
    - `Parámetros` -> `Config técnica`
- Impacto esperado:
  - menos confusion de navegacion
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - no quedan entradas ambiguas en menu o breadcrumbs

## Track E - Endurecimiento de dominio para simplicidad real

### Modulo E1 - `CheckConstraint` para parametros y montos

- Prioridad: `P1`
- Problema:
  - hoy parte de la simplicidad depende de confiar en formularios o validaciones Python
- Evidencia:
  - `PortfolioParameters` valida en `clean()`
  - modelos financieros operativos no muestran constraints de dominio fuertes
- Cambio esperado:
  - agregar `CheckConstraint` donde tenga sentido para:
    - porcentajes en rango
    - montos no negativos
    - cantidades no negativas
- Impacto esperado:
  - menos estados absurdos
  - menos necesidad de explicar comportamientos raros
- Riesgo:
  - medio
- Criterio de aceptacion:
  - migraciones aplicadas
  - saneamiento previo si hay datos inconsistentes
  - tests de edge cases

### Modulo E2 - Auditoria de funciones y vistas realmente usadas

- Prioridad: `P2`
- Problema:
  - la simplicidad tambien exige podar superficie que ya no aporta
- Cambio esperado:
  - revisar vistas exportadas y acciones disponibles
  - marcar:
    - usadas por frontend principal
    - usadas solo por staff
    - candidatas a retiro
- Impacto esperado:
  - menos feature creep
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - inventario corto de endpoints/vistas activas
  - candidatos a deprecacion documentados

## Orden recomendado de ejecucion

1. `A1 - Navbar minimo y separacion de superficies`
2. `B1 - Planeacion minimal para aporte mensual`
3. `B2 - Extraccion de simulacion y optimizacion a Laboratorio`
4. `C1 - Separar lectura estrategica de inventario detallado`
5. `D1 - Retirar legacy del primer nivel`
6. `C2 - Consolidacion de Analytics v2`
7. `A2 - Desacople de DashboardContextMixin`
8. `B3 - Reduccion de llamadas frontend no esenciales`
9. `E1 - CheckConstraint para parametros y montos`
10. `D2 - Renombrado de pantallas ambiguas`
11. `C3 - Correccion de labels y microcopy criticos`
12. `E2 - Auditoria de funciones y vistas realmente usadas`

## Primer modulo sugerido

### Recomendacion

Arrancar por `A1 - Navbar minimo y separacion de superficies`.

### Justificacion

- es el recorte de mayor impacto con menor riesgo
- cambia la sensacion de producto antes de tocar la logica profunda
- prepara el terreno para simplificar `Planeacion` y `Estrategia` sin seguir exponiendo accesos que compiten entre si

## Documentacion a mantener alineada durante la ejecucion

- `docs/README.md`
- `docs/DECISIONS.md`
- `docs/signals_and_recommendations.md`
- `docs/monthly_allocation_engine.md`
- `docs/pipeline_observability_ops.md`

## Fuera de alcance inmediato

- rediseño visual integral
- migracion a frontend SPA
- reescritura de analytics v2
- rehacer por completo el dominio de portfolio

## Regla de iteracion

Cada modulo que se implemente debe cerrar con:

1. problema que resuelve
2. evidencia concreta del antes
3. archivos tocados
4. tests o validacion ejecutada
5. deuda pendiente
6. mensaje de commit propuesto
