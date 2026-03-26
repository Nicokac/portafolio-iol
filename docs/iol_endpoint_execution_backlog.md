# Backlog de ejecucion de endpoints IOL

## Objetivo

Traducir el mapa de endpoints IOL a una secuencia de implementacion concreta, modular y trazable.

Este backlog no reemplaza [iol_endpoint_usage_map.md](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/docs/iol_endpoint_usage_map.md).

Su funcion es otra:

- decidir que modulo conviene ejecutar primero
- explicitar problema, dependencias, riesgos y criterios de aceptacion
- dejar claro que archivos y capas deberian tocarse
- facilitar cierres por modulo compatibles con `AGENTS.md`

## Verificaciones base usadas para este backlog

Se reutilizan y toman como base verificada:

- [iol_endpoint_usage_map.md](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/docs/iol_endpoint_usage_map.md)
- [repo_hardening_and_decision_roadmap.md](/c:/Users/kachu/Documents/portafolio_iol_notebook/portafolio-iol/docs/repo_hardening_and_decision_roadmap.md)
- `apps/core/services/iol_api_client.py`
- `apps/dashboard/portfolio_enrichment.py`
- `apps/core/services/temporal_metrics_service.py`
- `apps/api/views.py`

Hallazgos de partida ya confirmados:

- no hay un endpoint IOL verificado que entregue performance acumulada total de la cuenta lista para usar
- `portafolio/{pais}` ya entrega buen material para PnL acumulado por posicion
- la app calcula localmente retornos temporales y `TWR`
- `seriehistorica` no debe tomarse como unica fuente confiable
- `Titulos/FCI` y `Cotizaciones/{Instrumento}/{Pais}/Todos` son hoy las mejores oportunidades de expansion

## Principios de priorizacion

### P1

Corresponde a modulos con:

- valor visible rapido en producto
- bajo o medio riesgo tecnico
- reutilizacion alta de infraestructura existente

### P2

Corresponde a modulos con:

- valor alto, pero con mas incertidumbre de contrato o acoplamiento
- necesidad de validacion previa o feature flag

### P3

Corresponde a exploraciones utiles, pero no aptas todavia como base productiva.

## Track A - Claridad de performance

### Modulo A1 - Separacion de familias de KPIs

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - hoy es facil comparar KPIs que miden cosas distintas
  - `rendimiento_total_porcentaje` convive con retornos temporales sin suficiente separacion semantica
- Oportunidad:
  - reducir confusion metodologica en `Resumen`, `Estrategia` y API
- Cambio esperado:
  - separar explicitamente la familia `acumulado sobre costo`
  - separar explicitamente la familia `retorno temporal sobre patrimonio`
  - exponer labels y ayudas metodologicas consistentes
- Dependencias:
  - `apps/dashboard/portfolio_enrichment.py`
  - `apps/api/views.py`
  - templates o partials que hoy muestran KPIs
- Archivos probables a tocar:
  - `apps/dashboard/portfolio_enrichment.py`
  - `apps/api/views.py`
  - `apps/dashboard/views.py`
  - templates de `Resumen` o helpers de overview
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - UI muestra separacion clara entre acumulado y temporal
  - API devuelve metadata de base metodologica consistente
  - no se rompe compatibilidad con consumers actuales

### Modulo A2 - Guardrails de historia parcial

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - con historia corta, los retornos temporales son tecnicamente validos pero semanticamente fragiles
- Oportunidad:
  - evitar sobrelectura del usuario cuando hay solo uno o pocos subperiodos utiles
- Cambio esperado:
  - mostrar warnings de historia parcial
  - marcar ventanas no robustas de forma visible
- Dependencias:
  - `apps/core/services/temporal_metrics_service.py`
  - `apps/api/views.py`
- Archivos probables a tocar:
  - `apps/core/services/temporal_metrics_service.py`
  - `apps/api/views.py`
  - templates que renderizan `metrics_returns`
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - la UI muestra estado parcial si no hay historia robusta
  - el contrato API deja visible `robust_history_available`

## Track B - Expansion FCI

### Modulo B1 - Catalogo persistido de FCI

- Estado: `Implementado`
- Prioridad: `P1`
- Problema:
  - hoy `Titulos/FCI/{simbolo}` solo se usa como soporte y no existe un catalogo de fondos realmente explotado
- Oportunidad:
  - crear screener y comparador de FCI con valor visible rapido
- Endpoint:
  - `GET /api/v2/Titulos/FCI`
- Cambio esperado:
  - persistir catalogo diario de FCI
  - normalizar campos utiles para filtros y ranking
- Dependencias:
  - `apps/core/services/iol_api_client.py`
  - pipeline de sync o management command nuevo/reutilizado
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - nuevo servicio puro de catalogo FCI
  - modelo persistente o snapshot de catalogo
  - vista/API para screener
- Riesgo:
  - medio
- Criterio de aceptacion:
  - existe persistencia del catalogo
  - se puede filtrar por `tipoFondo`, moneda, rescate y perfil
  - tests de parsing y persistencia

### Modulo B2 - Ficha enriquecida de FCI

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - la app todavia no capitaliza `variacionMensual`, `variacionAnual`, `horizonteInversion` ni `montoMinimo`
- Oportunidad:
  - mejorar lectura de fondos y distinguir cash management de retorno real
- Endpoint:
  - `GET /api/v2/Titulos/FCI/{simbolo}`
- Cambio esperado:
  - exponer ficha de FCI con metricas y metadata relevante
  - enriquecer clasificacion de liquidez y estrategia
- Dependencias:
  - catalogo o lookup por simbolo
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - builders/selectors de dashboard
  - templates o cards de detalle
- Riesgo:
  - bajo
- Criterio de aceptacion:
  - cada FCI relevante muestra ficha enriquecida
  - los cash management quedan mejor distinguidos de fondos de riesgo

## Track C - Cobertura de mercado y discovery

### Modulo C1 - Bootstrap de universo por instrumento

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - parte del universo potencial sigue implícito o hardcodeado
- Oportunidad:
  - formalizar discovery de instrumentos y preparar expansion futura
- Endpoints:
  - `GET /api/v2/{pais}/Titulos/Cotizacion/Instrumentos`
  - `GET /api/v2/{pais}/Titulos/Cotizacion/Paneles/{instrumento}`
- Cambio esperado:
  - persistir catalogo de instrumentos y paneles
  - usarlo como base de navegacion y jobs batch
- Dependencias:
  - cliente IOL y estructuras de metadata
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - servicio de discovery de universo
  - persistencia de catalogo
- Riesgo:
  - bajo/medio
- Criterio de aceptacion:
  - existe bootstrap reproducible de instrumentos y paneles
  - no se depende de strings hardcodeados para discovery basico

### Modulo C2 - Ingesta masiva de cotizaciones por instrumento

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - faltan cobertura amplia y visibilidad de freshness para bonos, opciones y otros instrumentos
- Oportunidad:
  - ampliar analytics y monitoring del universo operable
- Endpoint:
  - `GET /api/v2/Cotizaciones/{Instrumento}/{Pais}/Todos`
- Cambio esperado:
  - crear ingestor batch por instrumento
  - persistir observaciones resumidas de cobertura y freshness
- Dependencias:
  - bootstrap de universo
  - storage para observaciones de mercado
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - servicio batch nuevo o extensible
  - modelo/snapshot de cobertura
  - `Ops` o dashboard de observabilidad
- Riesgo:
  - medio
- Criterio de aceptacion:
  - se puede correr batch por instrumento/pais
  - quedan visibles cobertura y frescura por familia de activo
  - tests de parsing y reduccion de payload

## Track D - Capa cambiaria y ejecucion tactica

### Modulo D1 - Valuacion MEP implicita

- Prioridad: `P1`
- Estado: `Implementado`
- Problema:
  - hoy falta una lectura cambiaria implicita por activo integrada al portfolio
- Oportunidad:
  - mejorar exposicion USD, lectura de CEDEARs y comparacion ARS/USD
- Endpoint:
  - `GET /api/v2/Cotizaciones/MEP/{simbolo}`
- Cambio esperado:
  - derivar `precio_mep_implicito`
  - construir indicadores de exposicion cambiaria util para producto
- Dependencias:
  - metadata de titulos y clasificacion de instrumentos
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - servicio de enriquecimiento cambiario
  - selectors y UI de distribucion/exposicion
- Riesgo:
  - medio
- Criterio de aceptacion:
  - CEDEARs relevantes muestran lectura cambiaria implicita
  - la vista de exposicion USD mejora sin romper valuaciones actuales

### Modulo D2 - Persistencia tactica por plazo

- Prioridad: `P2`
- Estado: `Implementado`
- Problema:
  - `CotizacionDetalleMobile/{plazo}` ya se consulta, pero todavia no se explota como capa comparativa por `t0/t1`
- Oportunidad:
  - mejorar readiness de ejecucion, spread y operabilidad por plazo
- Endpoint:
  - `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalleMobile/{plazo}`
- Cambio esperado:
  - persistir snapshots por plazo
  - construir comparador `t0 vs t1`
- Dependencias:
  - observaciones puntuales de mercado ya existentes
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - `apps/core/services/iol_market_snapshot_support.py`
  - modelos de observacion
  - `Planeacion` / `Ops`
- Riesgo:
  - medio
- Criterio de aceptacion:
  - hay lectura comparativa por plazo
  - la persistencia distingue `t0` y `t1`

## Track E - Exploracion condicionada

### Modulo E1 - Taxonomia remota de administradoras FCI

- Prioridad: `P3`
- Problema:
  - la familia `Administradoras` puede ordenar mejor el catalogo FCI, pero en pruebas reales hubo `403`
- Oportunidad:
  - agrupar fondos por family grouping remoto si el contrato lo permite
- Endpoints:
  - `GET /api/v2/Titulos/FCI/Administradoras/{administradora}/TipoFondos`
  - `GET /api/v2/Titulos/FCI/Administradoras/{administradora}/TipoFondos/{tipoFondo}`
- Cambio esperado:
  - spike tecnico bajo feature flag
- Dependencias:
  - validacion de permisos reales
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - doc de decisiones o feature flag
- Riesgo:
  - medio/alto
- Criterio de aceptacion:
  - solo avanzar si el endpoint responde de forma estable y autenticada

### Modulo E2 - Familia Orleans

- Prioridad: `P3`
- Problema:
  - existe una familia de endpoints `cotizaciones-orleans`, pero no esta validado su valor contractual
- Oportunidad:
  - explorar si mejora cobertura de operables o paneles
- Endpoints:
  - `GET /api/v2/cotizaciones-orleans/{Instrumento}/{Pais}/Todos`
  - `GET /api/v2/cotizaciones-orleans/{Instrumento}/{Pais}/Operables`
  - `GET /api/v2/cotizaciones-orleans-panel/{Instrumento}/{Pais}/Todos`
  - `GET /api/v2/cotizaciones-orleans-panel/{Instrumento}/{Pais}/Operables`
- Cambio esperado:
  - spike aislado
  - decision de adopcion o descarte
- Dependencias:
  - sandbox de pruebas y contrato autenticado valido
- Archivos probables a tocar:
  - `apps/core/services/iol_api_client.py`
  - doc de decisiones
- Riesgo:
  - alto
- Criterio de aceptacion:
  - no avanzar a producto sin evidencia clara de estabilidad y valor diferencial

## Orden de ejecucion sugerido

1. `A1` - Separacion de familias de KPIs
2. `A2` - Guardrails de historia parcial
3. `B1` - Catalogo persistido de FCI
4. `B2` - Ficha enriquecida de FCI
5. `C1` - Bootstrap de universo por instrumento
6. `C2` - Ingesta masiva de cotizaciones por instrumento
7. `D1` - Valuacion MEP implicita
8. `D2` - Persistencia tactica por plazo
9. `E1` / `E2` solo como spikes exploratorios

## Modulo recomendado para arrancar ya

Si el objetivo es maximizar valor visible con bajo riesgo, el mejor siguiente modulo es:

- `B1 - Catalogo persistido de FCI`

Si el objetivo es ordenar primero la semantica del producto antes de abrir mas ingestiones, el mejor siguiente modulo es:

- `A1 - Separacion de familias de KPIs`

## Criterio de cierre por modulo

Cada modulo deberia cerrarse con:

- implementacion acotada al modulo
- tests directos del servicio o contrato tocado
- actualizacion breve de documentacion
- mensaje de commit propuesto en espanol
- espera de confirmacion humana antes del siguiente modulo
