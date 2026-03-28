# Finviz Buy Intelligence Roadmap

## Objetivo

Definir como incorporar `finvizfinance` como capa de enriquecimiento para:

- entender mejor la composicion y calidad del portafolio
- mejorar la decision de compra de CEDEARs, acciones USA y ETFs
- sumar señales externas sin reemplazar las fuentes core de IOL

## Decision de producto

`finvizfinance` no se adopta como fuente principal de portfolio ni de ejecucion.

Se adopta como:

- capa de enriquecimiento analitico
- capa de comparacion entre candidatos
- capa de scoring complementario para decision de compra

## Principios rectores

1. no reemplazar IOL para valuacion, holdings ni operativa
2. no volcar columnas crudas masivamente en la UI principal
3. convertir datos de Finviz en:
   - scores
   - comparadores
   - explicaciones
   - shortlists
4. priorizar universo:
   - CEDEARs
   - ETFs
   - subyacentes USA
5. tolerar fallos de scraping o cambios de contrato sin romper la app

## Que señales de Finviz si aportan valor

### 1. Valuation

- `P/E`
- `Fwd P/E`
- `PEG`
- `P/S`
- `P/B`
- `P/C`
- `P/FCF`
- `Market Cap`

Uso:

- saber si un activo esta caro o barato relativo a su crecimiento y calidad
- comparar candidatos del mismo bucket
- identificar negocios de calidad con valuacion exigente

### 2. Growth

- `EPS This Y`
- `EPS Next Y`
- `EPS Past 5Y`
- `EPS Next 5Y`
- `Sales Past 5Y`

Uso:

- distinguir crecimiento historico de crecimiento esperado
- validar si la tesis de compra tiene fundamento operativo

### 3. Quality y profitability

- `ROA`
- `ROE`
- `ROIC`
- `Gross M`
- `Oper M`
- `Profit M`

Uso:

- entender si la empresa convierte ventas en retorno real
- priorizar calidad estructural dentro del portafolio

### 4. Solidez financiera

- `Curr R`
- `Quick R`
- `LTDebt/Eq`
- `Debt/Eq`

Uso:

- detectar fragilidad de balance
- penalizar negocios demasiado apalancados

### 5. Income y shareholder return

- `Dividend`

Uso:

- distinguir activos defensivos o con sesgo income

### 6. Timing y contexto de mercado

- `Price`
- `Change`
- `Volume`
- `Beta`
- `52W High`
- `52W Low`

Uso:

- evaluar riesgo tactico
- entender sensibilidad del portafolio
- medir cercania a extremos del rango anual
- identificar flujo o interes reciente

### 7. Analyst overlay

- `ticker_outer_ratings()`

Uso:

- captar revisiones de consenso
- agregar una señal externa de conviccion o deterioro

### 8. News overlay

- `ticker_news()`

Uso:

- dar contexto de compra
- explicar cambios de prioridad

### 9. Insider overlay

- `ticker_inside_trader()`

Uso:

- señal secundaria de conviccion
- no usar como trigger principal

### 10. Trading signals

- `ticker_signal()`

Uso:

- capa tactica ligera para priorizar o postergar compras

## Donde encaja en la app

### Planeacion

Uso principal:

- enriquecer candidatos de compra
- construir un score complementario por activo
- explicar por que conviene mirar, esperar o evitar

Salida sugerida:

- `Alta conviccion`
- `Interesante pero exigente`
- `Calidad alta, precio exigente`
- `Barato pero debil`
- `Evitar por deterioro`

### Estrategia / Centro analitico

Uso principal:

- mostrar composicion de calidad, valuation y riesgo externo del portafolio
- detectar sesgos excesivos

Ejemplos:

- beta agregado del portafolio
- dispersion de multiplos
- exposicion a negocios de baja calidad

### Watchlist y sourcing

Uso principal:

- ranking de oportunidades del universo CEDEAR/USA
- filtro de candidatos por calidad, growth y valuation

## Casos de uso concretos

### A. Entender mejor el portafolio actual

Contribuciones posibles:

- beta promedio ponderado
- distribucion por rangos de valuation
- calidad media del portafolio
- apalancamiento agregado de la cartera
- exposicion a activos con deterioro de margenes o crecimiento

### B. Mejorar decision de compra

Contribuciones posibles:

- comparar candidatos del mismo bloque estrategico
- penalizar activos con mala calidad aunque suban
- evitar compras en nombres con balance fragil
- priorizar activos con growth razonable y valuacion no excesiva

### C. Mejorar rebalanceo

Contribuciones posibles:

- detectar exceso de beta
- detectar exceso de valuacion
- detectar falta de quality o defensividad

## Modelo de scoring sugerido

## Capa 1 - subscores

Cada activo recibe:

- `valuation_score`
- `growth_score`
- `quality_score`
- `balance_score`
- `market_signal_score`
- `analyst_score`

Todos normalizados en escala `0-100`.

## Capa 2 - score compuesto

### Propuesta inicial

- `valuation_score`: 20%
- `growth_score`: 20%
- `quality_score`: 25%
- `balance_score`: 15%
- `market_signal_score`: 10%
- `analyst_score`: 10%

### Ajustes por perfil

- perfil conservador:
  - mas peso en `quality`, `balance`, `dividend`, menor peso en `market_signal`
- perfil moderado:
  - pesos balanceados
- perfil agresivo:
  - mas peso en `growth` y `market_signal`

## Metricas prioritarias para MVP

### MVP P1

- `Fwd P/E`
- `PEG`
- `EPS Next Y`
- `EPS Next 5Y`
- `Sales Past 5Y`
- `ROIC`
- `Oper M`
- `Profit M`
- `Debt/Eq`
- `Quick R`
- `Beta`
- `Change`
- `Volume`

### MVP P2

- `P/E`
- `P/S`
- `P/B`
- `P/C`
- `P/FCF`
- `ROA`
- `ROE`
- `Dividend`
- `52W High`
- `52W Low`
- ratings de analistas

### MVP P3

- insiders
- news
- signals mas tacticos

## Arquitectura sugerida

## Servicio nuevo

```text
apps/core/services/finviz/
```

### Archivos propuestos

- `finviz_client.py`
- `finviz_mapping_service.py`
- `finviz_fundamentals_service.py`
- `finviz_scoring_service.py`
- `finviz_cache_service.py`
- `finviz_portfolio_overlay_service.py`

## Contratos sugeridos

### `FinvizEnrichedAsset`

- ticker fuente
- ticker interno
- metrics crudas relevantes
- subscores
- score compuesto
- labels interpretables
- calidad de datos

### `FinvizPortfolioOverlay`

- beta promedio ponderado
- valuation profile
- quality profile
- leverage profile
- concentration by style

## Persistencia sugerida

No usar requests live en cada render.

Persistir snapshots o cache por ticker con:

- `fetched_at`
- `source_status`
- payload normalizado
- TTL sugerido:
  - fundamentals: diario
  - ratings: diario o intradiario
  - news: intradiario
  - insiders: diario

## Riesgos y limites

### Riesgos tecnicos

- scraping fragil
- cambios de HTML o headers en Finviz
- rate limits
- simbolos con mapeo distinto

### Riesgos de producto

- sobrecargar la UI con columnas crudas
- inducir falsa precision
- mezclar señal externa con señal core sin separar familias

## Decision de adopcion por modulo

### Adoptar

- fundamentals
- beta
- valuation multiples
- growth
- quality
- balance metrics
- ratings
- signals tacticos

### Mantener en observacion

- insiders
- news como señal cuantificable

### No adoptar como core

- charts de Finviz como pieza principal de producto
- HTML standalone como experiencia final
- precios de Finviz para operativa o valuacion oficial

## Roadmap por fases

### Fase A - Descubrimiento y mapping

- mapear CEDEAR -> ticker USA
- definir universo soportado
- documentar simbolos no mapeables

Criterio de aceptacion:

- tabla de mapping confiable
- cobertura del universo objetivo conocida
- estado: `implementado`
- resultado:
  - se agrego un `FinvizMappingService` con overrides explicitos para simbolos internos que no coinciden 1 a 1 con Finviz
  - se definio fuera de alcance inicial a `Bond`, `FCI` y equivalentes no soportados
  - se agrego el command `audit_finviz_mapping` para auditar `metadata` y `portfolio` actual
- archivos principales:
  - `apps/core/services/finviz/finviz_mapping_service.py`
  - `apps/core/management/commands/audit_finviz_mapping.py`
  - `apps/core/tests/test_finviz_mapping_service.py`
  - `apps/core/tests/test_audit_finviz_mapping_command.py`

### Fase B - Fundamentals MVP

- traer fundamentals prioritarios
- normalizar tipos
- persistir snapshots diarios

Criterio de aceptacion:

- payload estable por activo
- cache o persistencia local
- estado: `implementado`
- resultado:
  - se agrego `FinvizFundamentalsSnapshot` como persistencia diaria normalizada por simbolo interno
  - se agrego `FinvizClient` para encapsular `finvizfinance` y aislar errores de dependencia o fetch
  - se agrego `FinvizFundamentalsService` para sincronizar `Market Cap`, `Fwd P/E`, `PEG`, `EPS`, `ROIC`, margenes, `Debt/Eq`, `Quick R`, `Beta`, `Change`, `Volume` y metricas relacionadas
  - se agrego el command `sync_finviz_fundamentals` para correr la sincronizacion sobre `metadata` completa o sobre el `portfolio` actual
  - la data quality queda clasificada como `full`, `partial`, `sparse` o `missing`
- archivos principales:
  - `apps/core/models.py`
  - `apps/core/migrations/0022_finvizfundamentalssnapshot.py`
  - `apps/core/services/finviz/finviz_client.py`
  - `apps/core/services/finviz/finviz_fundamentals_service.py`
  - `apps/core/management/commands/sync_finviz_fundamentals.py`
  - `apps/core/tests/test_finviz_fundamentals_service.py`
  - `apps/core/tests/test_sync_finviz_fundamentals_command.py`

### Fase C - Buy score MVP

- implementar subscores
- implementar `composite_buy_score`
- agregar explicaciones legibles

Criterio de aceptacion:

- shortlist de compra ordenable
- comparador entre candidatos
- estado: `implementado`
- resultado:
  - se agrego `FinvizScoringService` para calcular `valuation_score`, `growth_score`, `quality_score`, `balance_score` y `market_signal_score`
  - se agrego `composite_buy_score` como promedio ponderado sobre los subscores disponibles del snapshot mas reciente
  - cada activo ahora expone interpretacion legible, fortalezas, cautelas y `main_reason`
  - se agrego el command `score_finviz_candidates` para construir una shortlist o comparar simbolos puntuales desde consola
  - el scoring sigue siendo heuristico y deliberadamente explicable; todavia no incorpora ratings, news ni insiders
- archivos principales:
  - `apps/core/services/finviz/finviz_scoring_service.py`
  - `apps/core/management/commands/score_finviz_candidates.py`
  - `apps/core/tests/test_finviz_scoring_service.py`
  - `apps/core/tests/test_score_finviz_candidates_command.py`

### Fase D - Portfolio overlay

- beta agregado
- profile de valuation
- profile de quality
- profile de leverage

Criterio de aceptacion:

- lectura del portafolio enriquecida sin ruido excesivo
- estado: `implementado`
- resultado:
  - se agrego `FinvizPortfolioOverlayService` para resumir el portafolio actual usando el snapshot Finviz mas reciente
  - el overlay calcula `portfolio_beta`, `composite_buy_score` ponderado, perfiles ponderados de `valuation`, `quality`, `balance`, `growth` y `market_signal`
  - se agregan cobertura del portafolio mapeado, lideres por peso, lideres por beta y quality, y alertas de nombres caros o de balance fragil
  - se agrego el command `inspect_finviz_portfolio_overlay` para inspeccion tecnica sin ensuciar la UX principal
- archivos principales:
  - `apps/core/services/finviz/finviz_portfolio_overlay_service.py`
  - `apps/core/management/commands/inspect_finviz_portfolio_overlay.py`
  - `apps/core/tests/test_finviz_portfolio_overlay_service.py`
  - `apps/core/tests/test_inspect_finviz_portfolio_overlay_command.py`

### Fase E - Integracion UI

- `Planeacion`: shortlist enriquecido
- `Centro analitico`: comparador y lectura agregada
- opcional: watchlist

Criterio de aceptacion:

- decision de compra mejora sin ensuciar la UX principal
- estado: `implementado`
- resultado:
  - `Planeacion` ahora muestra una `Shortlist externa de compra` con score compuesto, quality, valuation e interpretacion breve
  - `Centro analitico` ahora muestra `Overlay Finviz del portafolio` con beta agregada y perfiles ponderados de quality, valuation y leverage
  - la integracion sigue siendo secundaria y legible: no reemplaza el flujo principal ni expone columnas crudas masivamente
- archivos principales:
  - `apps/dashboard/selectors.py`
  - `apps/dashboard/views.py`
  - `templates/dashboard/planeacion.html`
  - `templates/dashboard/analisis.html`
  - `apps/dashboard/tests/test_feature_flows.py`

### Fase F - Ratings, news e insiders

- sumar overlays secundarios
- medir si explican o mejoran decisiones

Criterio de aceptacion:

- evidencia de valor real y no solo mas datos
- estado: `implementado`
- resultado:
  - se agrego persistencia diaria de overlays secundarios en `FinvizSignalSnapshot`
  - el scoring ahora incorpora `analyst_score` y una lectura sintetica de consenso
  - `Planeacion` muestra contexto complementario de `Consenso` para enriquecer la shortlist sin invadir la UX principal
  - news e insiders quedan disponibles como capa persistida para una fase posterior de mayor explotacion
- archivos principales:
  - `apps/core/models.py`
  - `apps/core/migrations/0023_finvizsignalsnapshot.py`
  - `apps/core/services/finviz/finviz_client.py`
  - `apps/core/services/finviz/finviz_signal_overlay_service.py`
  - `apps/core/services/finviz/finviz_scoring_service.py`
  - `apps/core/management/commands/sync_finviz_signal_overlays.py`
  - `apps/core/tests/test_finviz_signal_overlay_service.py`
  - `apps/core/tests/test_sync_finviz_signal_overlays_command.py`
  - `apps/core/tests/test_finviz_scoring_service.py`
  - `templates/dashboard/planeacion.html`

### Fase G - Radar de oportunidades

- separar oportunidades externas de nombres ya tenidos
- usar el score Finviz para sourcing y seguimiento sin meter una watchlist pesada en la UX principal

Criterio de aceptacion:

- se ve claramente que nombres aparecen para mirar afuera y cuales merecen refuerzo dentro de cartera
- estado: `implementado`
- resultado:
  - se agrego `FinvizOpportunityWatchlistService` para construir un radar simple a partir del shortlist Finviz y la cartera actual
  - el radar separa `ideas externas mejor rankeadas` de `nombres para reforzar dentro de cartera`
  - `Centro analitico` ahora muestra esta capa como lectura secundaria, sin reemplazar `Planeacion`
- archivos principales:
  - `apps/core/services/finviz/finviz_opportunity_watchlist_service.py`
  - `apps/core/management/commands/inspect_finviz_opportunity_watchlist.py`
  - `apps/core/tests/test_finviz_opportunity_watchlist_service.py`
  - `apps/core/tests/test_inspect_finviz_opportunity_watchlist_command.py`
  - `apps/dashboard/selectors.py`
  - `apps/dashboard/views.py`
  - `templates/dashboard/analisis.html`
  - `apps/dashboard/tests/test_feature_flows.py`

### Fase H - Explicaciones de catalizadores y fricciones

- explotar `news` e `insiders` como explicacion
- mantener la UX en formato legible y no tabular

Criterio de aceptacion:

- los overlays secundarios ya no son solo conteos: explican mejor por que mirar o frenar un nombre
- estado: `implementado`
- resultado:
  - el scoring ahora agrega `overlay_catalyst_summary` y `overlay_risk_summary`
  - `Planeacion` muestra una lectura corta de catalizadores y fricciones junto al shortlist externo
  - `Centro analitico` reutiliza esas explicaciones en el radar de oportunidades
- archivos principales:
  - `apps/core/services/finviz/finviz_scoring_service.py`
  - `apps/core/tests/test_finviz_scoring_service.py`
  - `templates/dashboard/planeacion.html`
  - `templates/dashboard/analisis.html`
  - `apps/dashboard/tests/test_feature_flows.py`

### Fase I - Integracion con recomendaciones

- cruzar Finviz con el motor de recomendaciones actual
- usar la capa externa como contraste operativo, no como reemplazo del engine

Criterio de aceptacion:

- Finviz puede emitir recomendaciones complementarias sin duplicar ni ensuciar las senales core
- estado: `implementado`
- resultado:
  - `RecommendationEngine` ahora incorpora una lectura Finviz acotada desde el radar de oportunidades
  - puede sugerir una `oportunidad externa` y un `nombre para refuerzo` solo cuando la conviccion supera umbrales minimos
  - la integracion queda como origen `finviz`, explicable y subordinado al motor principal
- archivos principales:
  - `apps/core/services/recommendation_engine.py`
  - `apps/core/tests/test_recommendation_engine.py`
  - `docs/signals_and_recommendations.md`

### Fase J - Integracion visible en Planeacion

- proyectar Finviz dentro del workflow mensual sin reemplazar la recomendacion principal
- usarlo como contraste de compra y refuerzo dentro del bloque de decision

Criterio de aceptacion:

- `Planeacion` muestra apoyo Finviz de forma legible dentro de `Modo decision`
- estado: `implementado`
- resultado:
  - `decision_engine_summary` ahora incluye `finviz_support`
  - `Planeacion` muestra una capa `Apoyo Finviz para esta decision` con idea externa y nombre reforzable cuando hay cobertura
  - la integracion no reescribe la recomendacion principal; solo suma contraste visible y explicable
- archivos principales:
  - `apps/dashboard/decision_engine.py`
  - `apps/dashboard/incremental_planeacion.py`
  - `templates/dashboard/planeacion.html`
  - `apps/dashboard/tests/test_feature_flows.py`

### Fase K1 - Diagnostico y hardening de ingesta

- cerrar la cadena real de ingesta Finviz
- distinguir dependencia faltante de bloqueo de red o fetch

Criterio de aceptacion:

- el proyecto expone claramente por que Finviz no carga y no deja al usuario interpretando un silencio ambiguo
- estado: `implementado`
- resultado:
  - `finvizfinance` quedo declarado en `requirements/base.txt`
  - se confirmo por shell que la dependencia ya importa correctamente en el entorno
  - se verifico que la falla actual de fetch no es de codigo sino de conectividad/permisos hacia `finviz.com`
  - los snapshots persistidos guardan ese error tecnico en `metadata.client_error`
- archivos principales:
  - `requirements/base.txt`
  - `apps/core/services/finviz/finviz_client.py`
  - `apps/core/models.py`

### Fase K2 - Fallback honesto de overlay y cobertura

- evitar que snapshots Finviz con `source_status=error` se muestren como cobertura util
- hacer que la UI falle de forma honesta cuando no hay base real

Criterio de aceptacion:

- el overlay ya no muestra 100% de cobertura ni scores `0.0` cuando toda la corrida Finviz fallo
- estado: `implementado`
- resultado:
  - `FinvizPortfolioOverlayService` ahora ignora snapshots no utilizables
  - si la ultima corrida fallo por dependencia o fetch, el resumen lo dice explicitamente
  - `Centro analitico` y `Planeacion` quedan conectados pero sin fingir datos validos
- archivos principales:
  - `apps/core/services/finviz/finviz_fundamentals_service.py`
  - `apps/core/services/finviz/finviz_portfolio_overlay_service.py`
  - `apps/core/tests/test_finviz_portfolio_overlay_service.py`

## Archivos que deberian mantenerse alineados

- `docs/analytics_v2_architecture.md`
- `docs/signals_and_recommendations.md`
- `docs/monthly_allocation_engine.md`
- `docs/analytics_v2_feature_exposure_checklist.md`

## Regla de implementacion

Cada modulo futuro deberia cerrar con:

1. objetivo
2. datos incorporados
3. mapping utilizado
4. scoring afectado
5. riesgos y limites
6. tests o validacion
7. mensaje de commit propuesto

## Recomendacion inicial

Arrancar por:

- `Fase A - Descubrimiento y mapping`
- luego `Fase B - Fundamentals MVP`
- luego `Fase C - Buy score MVP`

Ese orden permite capturar valor rapido sin meter ruido en UI demasiado pronto.
