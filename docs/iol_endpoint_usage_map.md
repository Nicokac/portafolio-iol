# Mapa de endpoints IOL y uso real en la app

## Objetivo

Tener una referencia unica para responder:

- que endpoint de IOL consume la app
- donde se usa
- que parte del payload se aprovecha hoy
- que parte queda subutilizada

Este documento sirve para evitar dos problemas:

1. asumir que un endpoint "esta integrado" cuando solo se usa una parte minima
2. perder de vista si conviene seguir endureciendo contrato o empezar a explotar mejor la data ya disponible

## Resumen rapido

Hoy existe un consumidor real para estos endpoints IOL:

- `GET /api/v2/estadocuenta`
- `GET /api/v2/portafolio/{pais}`
- `GET /api/v2/operaciones`
- `GET /api/v2/operaciones/{numero}`
- `GET /api/v2/{mercado}/Titulos/{simbolo}`
- `GET /api/v2/Titulos/FCI/{simbolo}`
- `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion`
- `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalle`
- `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalleMobile/{plazo}`
- `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/{fechaDesde}/{fechaHasta}/{ajustada}`

## Estrategia actual de historicos

La app ya no depende de una sola fuente para historicos diarios por activo.

Estado actual:

- `IOL seriehistorica` sigue siendo la fuente legacy para simbolos donde responde bien
- `Yahoo Finance / yfinance` ahora se usa como fuente complementaria para `Equity`, `CEDEAR` y `ETF`
- la persistencia sigue cayendo en `IOLHistoricalPriceSnapshot` para no romper consumers cuantitativos existentes
- el campo `source` distingue la procedencia real (`iol` o `yfinance`)

Objetivo:

- mantener IOL como fuente tactica y operativa del momento
- usar `yfinance` para reforzar cobertura historica diaria del universo accionario
- dejar bonos y otros instrumentos fuera de este fallback hasta definir otra fuente confiable

## Mapa por endpoint

| Endpoint IOL | Cliente | Uso real actual | Superficie | Aprovechamiento actual | Brecha principal |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v2/estadocuenta` | `IOLAPIClient.get_estado_cuenta()` | Sync patrimonial base y liquidez por cuenta | snapshots, KPIs, `Resumen`, `Planeacion`, `Estrategia` | Alto | `estadisticas[]` sigue fuera de uso |
| `GET /api/v2/portafolio/{pais}` | `IOLAPIClient.get_portafolio()` | Sync de posiciones por activo | snapshots, portfolio actual, hoja de portafolio, `Resumen` y `Planeacion` con lectura tactica de `parking`, senal visible, compuerta de ejecucion, condicionamiento de prioridad, shortlist sugerida reordenada, promocion de alternativa limpia y degradacion de score/confidence en modo decision | Alto | `parking` ya entra en la decision tactica, pero todavia no tiene capa historica ni senal persistida en recomendaciones |
| `GET /api/v2/operaciones` | `IOLAPIClient.get_operaciones()` | Sync y listado de operaciones con filtros normalizados | `OperacionIOL`, hoja de operaciones con filtros locales y sync remoto filtrado, observabilidad, auditoria operativa visible, `Resumen`, `Estrategia`, `Planeacion` via flujo operativo mensual y analitica operativa historica por subset filtrado | Alto | `pais_consulta` ya se persiste, pero el backfill historico todavia es progresivo |
| `GET /api/v2/operaciones/{numero}` | `IOLAPIClient.get_operacion()` | Enriquecimiento detallado de una operacion | `OperacionIOL` detalle, auditoria, hoja de operaciones con detalle on-demand, timeline, fills, aranceles, batch sobre subset filtrado, drill-down operativo, metricas historicas de ejecucion o costo y `Planeacion` via huella real de ejecucion reciente para propuestas futuras | Alto | no hay serie persistida propia de ejecucion ni slippage robusto |
| `GET /api/v2/{mercado}/Titulos/{simbolo}` | `IOLAPIClient.get_titulo()` | Metadata minima de titulo | elegibilidad de historicos, resolucion de instrumentos | Medio | no expuesto en UI de forma explicita |
| `GET /api/v2/Titulos/FCI/{simbolo}` | `IOLAPIClient.get_fci()` | Confirmacion de FCI y cash management | exclusiones del pipeline de historicos | Medio | no se usa mas alla de clasificacion o confirmacion |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion` | `IOLAPIClient.get_titulo_cotizacion()` | fallback de market data puntual | `get_titulo_market_snapshot()` | Bajo por si solo | hoy se usa solo como fallback |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalleMobile/{plazo}` | `IOLAPIClient.get_titulo_cotizacion_detalle_mobile()` | fuente tactica puntual por plazo | `get_titulo_market_snapshot()` para lectura operativa `t0/t1` | Medio | todavia no se explota como serie intradia ni analitica por plazo |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalle` | `IOLAPIClient.get_titulo_cotizacion_detalle()` | fuente primaria de market data puntual | elegibilidad historicos fallback, `Ops`, `Resumen`, `Estrategia`, `Planeacion` via snapshot cacheado y lectura historica corta de ejecucion reciente | Alto | la persistencia historica sigue acotada al universo refrescado manualmente |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/...` | `IOLAPIClient.get_titulo_historicos()` | sync de precios historicos por simbolo | `IOLHistoricalPriceSnapshot`, riesgo, performance y `Ops` | Alto | ya no es la unica fuente de historicos; cuando falla o no conviene, la app puede reforzar `Equity/CEDEAR/ETF` via `yfinance` |

## Endpoint por endpoint

### 1. `estadocuenta`

Se usa para:

- snapshots de cuentas
- `cash_disponible_broker`
- `cash_a_liquidar_broker`
- `total_broker_en_pesos`
- reconciliacion patrimonial base

Campos hoy bien aprovechados:

- `cuentas[]`
- `saldos[]`
- `totalEnPesos`

Campos todavia no usados:

- `estadisticas[]`

Conclusion:

- esta bien explotado para patrimonio y liquidez
- no parece ser hoy el cuello de botella del producto

### 4. `operaciones/{numero}` en decision de futuras compras

Hoy este endpoint ya no vive solo en la hoja operativa.

Tambien alimenta una lectura tactica en `Planeacion`:

- `Huella real de ejecucion reciente`
- contraste de simbolos sugeridos contra operaciones terminadas reales
- monto ejecutado visible
- aranceles visibles
- fragmentacion por multiples fills
- compuerta de ejecucion cuando la propuesta no tiene huella operativa comparable suficiente
- lectura comparativa por simbolo dentro de la propuesta sugerida para distinguir el tramo mas limpio y el mas fragil
- sugerencia explicita de orden de ejecucion dentro de la propuesta cuando la huella operativa por simbolo es desigual

Esto permite que una propuesta futura no se evalue solo por:

- retorno esperado
- fragilidad
- liquidez reciente de mercado

Sino tambien por evidencia operativa real de ejecucion reciente cuando existe.

Limite actual:

- sigue siendo una lectura tactica de apoyo
- no hay slippage robusto ni serie historica persistida de calidad de ejecucion por simbolo

### 2. `portafolio/{pais}`

Se usa para:

- snapshot de activos
- valuacion actual por posicion
- clasificacion base de instrumentos
- hoja de portafolio con lectura visible de `parking`
- chequeo tactico de `parking` en `Resumen`
- chequeo tactico de `parking` en `Planeacion`
- senal tactica de `parking` dentro del bloque `Modo decision` de `Planeacion`
- compuerta de ejecucion en `Planeacion` cuando hay `parking` visible
- condicionamiento de prioridad de la recomendacion cuando el bloque sugerido coincide con posiciones en `parking`
- shortlist de activos sugeridos condicionada cuando un candidato cae en un bloque con `parking` visible
- reordenamiento de la shortlist para priorizar candidatos no condicionados por `parking`
- propuesta preferida condicionada cuando su `purchase_plan` cae en bloques con `parking`
- promocion de una propuesta alternativa limpia cuando la preferida original queda condicionada y la diferencia de score es acotada
- degradacion de `score` y `confidence` del `Modo decision` cuando `parking` sigue visible

Campos hoy bien aprovechados:

- bloque principal del activo
- `titulo.*`
- precision decimal util
- `parking`

Conclusion:

- el contrato base ya esta bien endurecido
- `parking` ya dejo de ser dato huerfano en persistencia
- `parking` ya impacta la lectura de decision tactica en `Planeacion`
- `parking` ya puede frenar la ejecucion directa y forzar revision tactica antes del despliegue
- `parking` ya puede condicionar la prioridad visible de la recomendacion cuando hay superposicion con el bloque sugerido
- `parking` ya puede degradar la shortlist sugerida cuando el candidato cae en la misma zona restringida
- `parking` ya puede bajar candidatos dentro del orden visible de la shortlist tactica
- `parking` ya puede condicionar la propuesta preferida antes de tomarla como ejecucion directa
- `parking` ya puede promover una alternativa limpia por encima de la preferida original cuando la diferencia de score es razonable
- `parking` ya deteriora la lectura cuantitativa final del `Modo decision`
- la brecha ya no es de ingestion sino de integracion mas profunda en recomendaciones o analitica historica

### 3. `operaciones`

Se usa para:

- listado historico
- sync de operaciones
- filtros por numero, estado, fechas y pais
- sync remoto filtrado desde la hoja de operaciones
- lectura visible de cobertura de `pais_consulta` y pendientes de backfill sobre la pagina actual
- lectura historica del subset filtrado completo para cobertura de detalle y `pais_consulta`
- observabilidad operativa del ultimo sync filtrado, ultimo enriquecimiento y ultimo backfill
- flujo operativo mensual en `Resumen`, `Estrategia` y `Planeacion`
- lectura reciente de compras, ventas, dividendos y suscripciones FCI
- metricas historicas del subset filtrado para volumen con monto visible, cobertura de aranceles visibles, fills visibles y fragmentacion historica
- comparacion operativa entre compras, ventas, dividendos y flujos FCI
- soporte de acciones batch previas al enriquecimiento por numero

Hallazgo operativo importante:

- para compras a mercado, `cantidad` del listado puede actuar como monto objetivo y no como unidades ejecutadas
- la ejecucion real debe leerse desde:
  - `cantidadOperada`
  - `precioOperado`
  - `montoOperado`

Conclusion:

- ya dejo de ser solo trazabilidad base
- ya tiene uso visible y accionable en producto
- ya tiene una capa analitica real sobre el subset filtrado
- la brecha principal ya no es filtrado ni sync, sino backfill historico de `pais_consulta` y metricas contables mas finas

### 4. `operaciones/{numero}`

Se usa para:

- enriquecer una operacion concreta con estados, aranceles, fills y fechas detalladas
- abrir el detalle desde el numero clickable en la hoja de operaciones
- mostrar timeline de estados, fills y aranceles on-demand
- permitir re-sincronizacion manual desde IOL
- enriquecer en batch solo las operaciones sin detalle de la pagina filtrada actual
- alimentar lectura resumida de fallos y resultado via auditoria operativa visible en la hoja
- alimentar metricas historicas agregadas de ejecucion y costo sobre el subset filtrado

Conclusion:

- el contrato ya esta endurecido
- ya tiene un consumidor visible y correcto en producto
- ya alimenta lectura operativa real en la hoja
- ya alimenta metricas historicas comparativas en la hoja
- el siguiente salto es persistir una capa historica de ejecucion mas rica si realmente aporta valor

### 5. `Titulos/{simbolo}` y `Titulos/FCI/{simbolo}`

Se usan para:

- resolver metadata minima
- confirmar si algo es FCI
- distinguir instrumentos elegibles de no elegibles para serie historica de titulos

Conclusion:

- son endpoints de soporte de clasificacion
- agregan mucho valor operativo aunque no sean vistosos

### 6. `Cotizacion`

Se usa hoy como:

- fallback liviano de market data puntual

Conclusion:

- por si solo hoy esta subaprovechado
- sigue siendo util como red de seguridad cuando `CotizacionDetalle` no responde

### 7. `CotizacionDetalle`

Se usa hoy como:

- fuente primaria de market data puntual
- validacion operativa en `Ops`
- fallback de elegibilidad para historicos cuando falla metadata de titulo
- capa tactica compartida para `Resumen`, `Estrategia` y `Planeacion`
- persistencia minima de observaciones puntuales para leer spread, libro y actividad reciente antes de decidir compras futuras
- senal historica corta de ejecucion dentro de `Planeacion`
- recomendacion principal condicionada cuando el bloque sugerido viene con liquidez reciente debil
- recomendacion principal repriorizada hacia un bloque alternativo limpio cuando existe una opcion razonable dentro del mismo plan mensual
- shortlist sugerida condicionada cuando el bloque candidato viene con liquidez reciente debil
- propuesta preferida condicionada cuando su `purchase_plan` cae en una zona con liquidez reciente debil
- propuesta preferida repriorizada hacia una alternativa limpia cuando la original queda condicionada por liquidez reciente y existe una opcion comparable
- degradacion de `score` y `confidence` del `Modo decision` cuando la liquidez reciente del bloque sugerido sigue siendo debil

Valor diferencial real:

- `tipo`
- `pais`
- `mercado`
- `cantidadMinima`
- `puntosVariacion`
- `puntas`
- `cantidadOperaciones`

Conclusion:

- ya dejo de estar aislado en observabilidad
- hoy potencia lectura tactica de producto
- ya no queda solo como foto puntual; ahora tambien deja una huella historica minima para decidir compras futuras con menos friccion operativa
- ya puede degradar la recomendacion principal cuando el bloque sugerido no viene acompanado por una ejecucion reciente limpia
- ya puede promover un bloque alternativo mas limpio cuando la recomendacion original queda demasiado condicionada
- ya puede degradar candidatos y propuesta sugerida cuando la calidad reciente de ejecucion no acompana
- ya puede promover una propuesta incremental alternativa cuando la preferida original no viene con una ejecucion reciente suficientemente limpia
- ya puede deteriorar la firmeza cuantitativa final de la decision cuando el contexto de ejecucion reciente no acompana
- la brecha actual ya no es si conviene persistirlo, sino cuanta automatizacion y cobertura adicional merece ese historial

### 7b. `CotizacionDetalleMobile/{plazo}`

Se usa hoy como:

- primer intento del `market snapshot` puntual cuando queremos lectura tactica por plazo
- captura de `puntas`, `cantidadOperaciones`, `operableCompra` y `operableVenta` sobre `t0/t1`
- etiquetado explicito de fuente `CotizacionDetalleMobile` dentro del snapshot persistido

Conclusion:

- no reemplaza `seriehistorica`
- agrega valor para ejecucion y operabilidad puntual
- abre la puerta a una futura capa intradia o comparativa por plazo si realmente aporta valor

### 8. `seriehistorica`

Se usa para:

- persistir cierres diarios IOL por simbolo
- mejorar volatilidad, tracking error, VaR y cobertura de riesgo
- observabilidad de cobertura en `Ops`

Conclusion:

- esta bien integrado
- pero ya no debe considerarse fuente unica ni contrato suficiente por si solo
- la cobertura efectiva del universo del portfolio ahora depende de una estrategia hibrida
- para `Equity/CEDEAR/ETF`, la app puede persistir historicos desde `yfinance`
- para bonos y otros instrumentos, sigue pendiente definir una fuente complementaria confiable

## Fuente complementaria externa: `yfinance`

Se usa hoy como:

- refuerzo de historicos diarios para `Equity`, `CEDEAR` y `ETF`
- cobertura local BYMA usando sufijo `.BA` cuando el mercado es `BCBA`
- cobertura directa sin sufijo para mercados compatibles como `NASDAQ` o `NYSE`
- persistencia en `IOLHistoricalPriceSnapshot` con `source="yfinance"`

Importante:

- no reemplaza a IOL como fuente tactica actual
- no se usa para `market snapshot`, `puntas`, `parking` ni operabilidad
- no se usa para bonos en el estado actual

Razon de dise�o:

- `CotizacionDetalleMobile` y `CotizacionDetalle` resolvieron bien la capa operativa del momento
- `seriehistorica` de IOL mostro comportamiento remoto inestable en pruebas reales
- `yfinance` mostro cobertura util para `AAPL.BA`, `SPY.BA`, `MELI.BA` y `YPFD.BA`
- `yfinance` no mostro cobertura util para bonos locales como `GD30.BA`, `AL30.BA`, `GD35.BA`, `TZX26.BA`, `TZXM6.BA` o `BPOC7.BA`

## Como probar la integracion nueva en la app

### Prueba tecnica minima

1. Instalar dependencias del entorno si hiciera falta
2. Correr:
   - `python manage.py runserver`
3. Disparar una sincronizacion de historicos desde la UI o por comando
4. Confirmar que aparezcan filas nuevas en `IOLHistoricalPriceSnapshot` con `source="yfinance"` para simbolos elegibles

### Comando sugerido

- `python manage.py sync_iol_historical_prices --simbolo=AAPL --mercado=BCBA`
- repetir con:
  - `SPY`
  - `MELI`
  - `YPFD`

Resultado esperado:

- la sync completa sin depender de `seriehistorica` de IOL para esos simbolos
- las filas persistidas quedan con `source="yfinance"`
- `rows_count` del simbolo sube en cobertura historica

### Validacion funcional en dashboard

Despues de sincronizar:

1. abrir `Ops`
2. revisar cobertura de historicos del simbolo
3. abrir `Estrategia`
4. revisar si mejoran las metricas que dependen de historia:
   - volatilidad
   - tracking error
   - VaR / CVaR
   - risk contribution cuando corresponda

### Casos esperados

- `AAPL`, `SPY`, `MELI`, `YPFD`: deberian poder reforzar historicos via `yfinance`
- `GD30`, `AL30`, `GD35`, `TZX26`, `TZXM6`, `BPOC7`: no deberian cubrirse por este fallback

### Criterio de aceptacion

La integracion se considera validada si:

- la sync no falla para `Equity/CEDEAR/ETF`
- la persistencia deja `source="yfinance"` visible en DB
- `build_close_series()` vuelve a entregar serie util aunque no haya filas `iol`
- el dashboard mejora cobertura historica sin degradar la capa tactica de IOL

## Donde hoy no le estamos sacando el maximo provecho

Los endpoints con mayor potencial todavia no exprimido son:

1. `CotizacionDetalle`
   - ya mejoro mucho, pero la persistencia historica sigue siendo corta y de cobertura acotada
2. `operaciones/{numero}`
   - ya se explota visualmente y en metricas agregadas; falta una capa historica mas robusta si se quiere analitica de slippage o calidad de precio
3. `operaciones`
   - ya se usa bien en hoja, dashboard y analitica operativa; falta backfill historico de `pais_consulta` para cerrar del todo el filtro local
4. `portafolio/{pais}`
   - `parking` ya es visible, condiciona la decision tactica y puede frenar la ejecucion directa en `Planeacion`; falta decidir si merece integracion en recomendaciones persistidas o senales historicas

## Matriz de KPIs de performance

Esta seccion sirve para evitar comparar KPIs que hoy miden cosas distintas.

### 1. Definicion operativa

| KPI | Que mide realmente | Formula base | Base economica | Fuente primaria | Estado actual |
| --- | --- | --- | --- | --- | --- |
| `rendimiento_total_porcentaje` | ganancia acumulada del portafolio invertido | `ganancia_acumulada / costo_estimado_invertido` | costo estimado del portafolio invertido | `portafolio/{pais}` + agregacion local | estable |
| `rendimiento_total_dinero` | ganancia acumulada en pesos del portafolio invertido | `sum(ganancia_dinero)` | PnL absoluto del bloque invertido | `portafolio/{pais}` | estable |
| `total_period_return` | retorno del patrimonio total entre snapshots | `(valor_final - valor_inicial) / valor_inicial` | `PortfolioSnapshot.total_iol` | snapshots locales | estable con historia suficiente |
| `twr_total_return` | retorno time-weighted descontando flujos operativos | `Π(1 + r_t) - 1` | `PortfolioSnapshot.total_iol` ajustado por flujos de `OperacionIOL` | snapshots + operaciones | estable con historia suficiente |

### 2. Cuando conviene usar cada KPI

| KPI | Mejor uso | No conviene usarlo para |
| --- | --- | --- |
| `rendimiento_total_porcentaje` | responder "cuanto rinde lo invertido contra su costo" | comparar performance temporal contra benchmarks o ventanas de tiempo |
| `rendimiento_total_dinero` | mostrar ganancia acumulada absoluta | comparar carteras de distinto tamano sin normalizacion |
| `total_period_return` | mostrar retorno total del patrimonio en una ventana concreta | aislar efecto de aportes y retiros |
| `twr_total_return` | comparar performance temporal descontando flujos | explicar PnL acumulado de costo de compra |

### 3. Endpoint fuente y trazabilidad

| KPI | Endpoint fuente | Capa de app | Observacion |
| --- | --- | --- | --- |
| `rendimiento_total_porcentaje` | `GET /api/v2/portafolio/{pais}` | `dashboard_kpis` | depende de `gananciaPorcentaje` y `gananciaDinero` por activo |
| `rendimiento_total_dinero` | `GET /api/v2/portafolio/{pais}` | `dashboard_kpis` | hoy es el mejor PnL acumulado absoluto disponible |
| `total_period_return` | sin endpoint IOL directo; usa snapshots internos | `metrics_returns` | depende de continuidad de `PortfolioSnapshot.total_iol` |
| `twr_total_return` | sin endpoint IOL directo; usa snapshots y `GET /api/v2/operaciones` | `metrics_returns` | es un KPI calculado por la app, no entregado por IOL |

### 4. Ubicacion sugerida en UI

| KPI | Donde deberia vivir en UI | Copy recomendado |
| --- | --- | --- |
| `rendimiento_total_porcentaje` | `Resumen` y card principal de portfolio actual | `Rendimiento acumulado sobre capital invertido` |
| `rendimiento_total_dinero` | junto al KPI anterior y en detalle de portafolio | `Resultado acumulado en pesos` |
| `total_period_return` | modulo temporal y comparaciones por ventana | `Retorno del patrimonio en el periodo` |
| `twr_total_return` | `Estrategia`, benchmarking y comparador temporal | `Retorno ajustado por flujos (TWR)` |

### Diferencia metodologica observada al 2026-03-26

Con la base local actual:

- `rendimiento_total_porcentaje`: `21.65%`
- `rendimiento_total_dinero`: `ARS 2,342,901.03`
- retorno sobre `total_patrimonio_modelado`: `10.00%`
- retorno sobre `total_iol`: `9.79%`
- `twr_total_return` reciente: `-0.29%`

Diferencias mas relevantes:

- `rendimiento_total_porcentaje` vs retorno sobre `total_patrimonio_modelado`: `11.65 pp`
- `rendimiento_total_porcentaje` vs retorno sobre `total_iol`: `11.86 pp`
- `rendimiento_total_porcentaje` vs `twr_total_return`: `21.94 pp`

Lectura:

- la brecha no indica error por si misma
- indica que se estaban mezclando KPIs de costo acumulado con KPIs de retorno temporal
- para producto conviene exponerlos como familias distintas y no como variantes del mismo numero

## Roadmap de endpoints que pueden empujar la app

El criterio de priorizacion es:

1. impacto visible en producto
2. mejora de cobertura de datos
3. riesgo tecnico razonable
4. esfuerzo incremental sobre lo ya implementado

### Prioridad P1: impacto alto y riesgo bajo/medio

| Endpoint | Oportunidad | Valor producto | Esfuerzo | Riesgo | Proximo paso sugerido |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v2/Titulos/FCI` | catalogo completo de FCI | ranking, filtros, screener y comparador de fondos | Medio | Bajo | persistir catalogo diario de FCI y exponer screener en `Resumen/Estrategia` |
| `GET /api/v2/Titulos/FCI/{simbolo}` | detalle enriquecido de cada fondo | mostrar `variacionMensual`, `variacionAnual`, perfil, rescate y minimo | Bajo | Bajo | ampliar ficha de FCI y clasificacion de liquidez/estrategia |
| `GET /api/v2/Cotizaciones/MEP/{simbolo}` | valuacion MEP implicita por activo | mejor lectura de exposicion USD y comparacion ARS/USD | Medio | Medio | derivar `precio_mep_implicito` para CEDEARs y vista cambiaria |
| `GET /api/v2/Cotizaciones/{Instrumento}/{Pais}/Todos` | market data masiva por instrumento | discovery, cobertura, ranking diario y universo operable | Medio | Medio | crear ingestor batch para bonos/opciones y coverage dashboard |

### Prioridad P2: impacto alto pero con incertidumbre o acoplamiento mayor

| Endpoint | Oportunidad | Valor producto | Esfuerzo | Riesgo | Proximo paso sugerido |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v2/{pais}/Titulos/Cotizacion/Instrumentos` | discovery formal del universo por pais | evita hardcode de instrumentos y simplifica onboarding de paneles | Bajo | Bajo | usarlo para bootstrap de universo de cotizaciones |
| `GET /api/v2/{pais}/Titulos/Cotizacion/Paneles/{instrumento}` | discovery formal de paneles | habilita navegacion dinamica por panel y expansion futura | Bajo | Medio | probar cobertura real y persistir catalogo de paneles |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalleMobile/{plazo}` | comparativa `t0/t1` persistida | mejora ejecucion tactica, spread por plazo y readiness | Medio | Medio | guardar snapshots por plazo y mostrar comparador `t0 vs t1` |
| `GET /api/v2/{Mercado}/Titulos/{Simbolo}/Cotizacion` | endpoint de cotizacion parametrico por plazo | fallback mas explicito para capas ligeras | Bajo | Medio | validar si aporta algo distinto a la combinacion actual |

### Prioridad P3: exploracion util, pero no base productiva todavia

| Endpoint | Oportunidad | Valor producto | Esfuerzo | Riesgo | Proximo paso sugerido |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v2/Titulos/FCI/Administradoras/{administradora}/TipoFondos` | taxonomia por administradora | ordena catalogo FCI y comparadores por family grouping | Medio | Medio | probar permisos reales y crear feature flag |
| `GET /api/v2/Titulos/FCI/Administradoras/{administradora}/TipoFondos/{tipoFondo}` | screener filtrado remoto de FCI | menor trabajo de filtrado local | Medio | Medio/Alto | evaluar solo si `Administradoras` deja de responder `403` |
| `GET /api/v2/cotizaciones-orleans/...` | posible universo operable alternativo | podria mejorar cobertura de operables o paneles | Medio | Alto | spike tecnico aislado antes de integracion |

### Endpoint que hoy no conviene tomar como eje

| Endpoint | Motivo |
| --- | --- |
| `seriehistorica` como unica fuente | ya mostro inestabilidad remota y errores `500` |
| `FCI/Administradoras` sin validacion adicional | en pruebas reales devolvio `403` |
| `Cotizaciones/{Instrumento}/{Panel}/{Pais}` como base primaria | en la muestra compartida devolvio `401`, por lo que necesita validacion antes de comprometer producto |

## Roadmap por fase

### Fase 1. Claridad de performance y UX

- separar en UI la familia `acumulado sobre costo` de la familia `retorno temporal`
- mostrar `rendimiento_total_dinero` junto a `rendimiento_total_porcentaje`
- etiquetar `TWR` como retorno ajustado por flujos
- mostrar warnings de historia parcial cuando haya menos de `60` dias robustos

### Fase 2. Expansion FCI

- persistir catalogo completo de `Titulos/FCI`
- enriquecer ficha de fondos con `variacionMensual`, `variacionAnual`, `rescate`, `montoMinimo` y `perfilInversor`
- crear comparador/screener de FCI por `tipoFondo`, moneda, rescate y horizonte
- distinguir mejor `cash management` vs fondos de retorno real

### Fase 3. Cobertura de mercado y discovery

- usar `Titulos/Cotizacion/Instrumentos` y `Paneles/{instrumento}` para bootstrap de universo
- crear jobs batch con `Cotizaciones/{Instrumento}/{Pais}/Todos`
- mejorar cobertura de bonos, opciones y universos operables
- exponer un tablero de cobertura y freshness por instrumento

### Fase 4. Capa cambiaria y ejecucion tactica

- integrar `Cotizaciones/MEP/{simbolo}` para lectura implicita en USD
- persistir `CotizacionDetalleMobile/{plazo}` por `t0/t1`
- construir comparadores de spread, operabilidad y profundidad por plazo
- usar esa senal en `Planeacion` y recomendaciones

## Recomendacion concreta de implementacion

Orden sugerido:

1. separar y renombrar KPIs en UI
2. explotar `Titulos/FCI` y `Titulos/FCI/{simbolo}`
3. integrar `Titulos/Cotizacion/Instrumentos` + `Cotizaciones/{Instrumento}/{Pais}/Todos`
4. sumar `Cotizaciones/MEP/{simbolo}`
5. explorar `Paneles/{instrumento}` y familia `orleans`

Si hubiera que elegir solo dos frentes con mejor retorno hoy:

- `FCI` para valor visible rapido en producto
- `Cotizaciones/{Instrumento}/{Pais}/Todos` para ampliar cobertura de mercado y analytics

## Recomendacion de lectura

Si la pregunta es:

- "que entra al sistema y donde se persiste"
  - ver `docs/data_pipeline.md`
- "que endpoint IOL conviene seguir endureciendo o explotar mejor"
  - ver este documento
- "que se ve hoy en Ops"
  - ver `docs/pipeline_observability_ops.md`

## Estado

Documento vigente para el estado actual de integracion IOL del proyecto.

- El reapply hacia `Planeacion` puede arrastrar metadata opcional de orden de ejecucion (`plan_a_execution_order_label`, `plan_a_execution_order_summary`) para conservar la recomendacion operativa del plan reaplicado sin alterar la simulacion.

- La lectura de `Planeacion` sobre el comparador manual ahora reutiliza la huella real de `OperacionIOL` para clasificar el mejor plan como listo, a validar o a observar antes de ejecutar.

- La huella de `OperacionIOL` tambien puede actuar como desempate visible entre planes manuales casi empatados en score dentro de `Planeacion`.

- La huella de `OperacionIOL` ahora tambien alimenta el comparador por candidato para resumir readiness y desempates operativos dentro del mismo bloque.

- La capa de `OperacionIOL` ahora tambien informa el comparador por split para leer si conviene concentrar o dividir con mejor ejecutabilidad real.

- La huella de `OperacionIOL` ya no solo decide el lider de cada comparador: tambien se expone por fila en candidato, split y manual dentro de `Planeacion`.

- La huella de `OperacionIOL` ya tambien informa el comparador incremental general, no solo los comparadores por candidato, split y manual.

- La lectura operativa de comparadores incrementales en `Planeacion` ahora se renderiza bajo partials comunes y un payload `display_summary` consistente entre comparadores.
- Esa unificacion de render mantiene compatibilidad hacia atras con contextos minimos del dashboard para no acoplar la vista a una sola forma de payload.
- `Planeacion` ahora permite filtrar los comparadores incrementales por readiness operativa visible (`Listo`, `Validar ejecucion`, `Seguir observando`) usando la misma huella derivada desde `OperacionIOL`.
- Ese flujo de comparadores ahora tambien preserva sus query params utiles entre submits y resets para no perder el contexto operativo mientras se alterna entre general, candidato, split y manual.
- `Planeacion` ahora expone tambien un resumen superior de comparadores activos y filtros vigentes para hacer mas legible el estado operativo derivado de esa misma capa de query params.
