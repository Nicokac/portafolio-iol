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
- `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/{fechaDesde}/{fechaHasta}/{ajustada}`

## Mapa por endpoint

| Endpoint IOL | Cliente | Uso real actual | Superficie | Aprovechamiento actual | Brecha principal |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v2/estadocuenta` | `IOLAPIClient.get_estado_cuenta()` | Sync patrimonial base y liquidez por cuenta | snapshots, KPIs, `Resumen`, `Planeacion`, `Estrategia` | Alto | `estadisticas[]` sigue fuera de uso |
| `GET /api/v2/portafolio/{pais}` | `IOLAPIClient.get_portafolio()` | Sync de posiciones por activo | snapshots, portfolio actual, dashboard | Alto | `parking` se persiste pero no se consume |
| `GET /api/v2/operaciones` | `IOLAPIClient.get_operaciones()` | Sync/listado de operaciones con filtros normalizados | `OperacionIOL`, vistas legacy, observabilidad, `Resumen`, `Estrategia`, `Planeacion` via flujo operativo mensual | Alto | no enriquece automatico con detalle por numero |
| `GET /api/v2/operaciones/{numero}` | `IOLAPIClient.get_operacion()` | Enriquecimiento detallado de una operacion | `OperacionIOL` detalle, auditoria | Medio | no hay consumo fuerte en UI |
| `GET /api/v2/{mercado}/Titulos/{simbolo}` | `IOLAPIClient.get_titulo()` | Metadata minima de titulo | elegibilidad de historicos, resolucion de instrumentos | Medio | no expuesto en UI de forma explicita |
| `GET /api/v2/Titulos/FCI/{simbolo}` | `IOLAPIClient.get_fci()` | Confirmacion de FCI y cash management | exclusiones del pipeline de historicos | Medio | no se usa mas alla de clasificacion/confirmacion |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion` | `IOLAPIClient.get_titulo_cotizacion()` | fallback de market data puntual | `get_titulo_market_snapshot()` | Bajo por si solo | hoy se usa solo como fallback |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalle` | `IOLAPIClient.get_titulo_cotizacion_detalle()` | fuente primaria de market data puntual | elegibilidad historicos fallback, `Ops`, `Resumen`, `Estrategia`, `Planeacion` via snapshot cacheado | Alto | no se persiste; la capa principal depende de refresh puntual cacheado |
| `GET /api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/...` | `IOLAPIClient.get_titulo_historicos()` | sync de precios historicos por simbolo | `IOLHistoricalPriceSnapshot`, riesgo/performance, `Ops` | Alto | sigue siendo opt-in via sync, no cobertura total garantizada |

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

### 2. `portafolio/{pais}`

Se usa para:

- snapshot de activos
- valuacion actual por posicion
- clasificacion base de instrumentos

Campos hoy bien aprovechados:

- bloque principal del activo
- `titulo.*`
- precision decimal util
- `parking`

Conclusion:

- el contrato base ya esta bien endurecido
- la brecha no es de ingestion sino de explotacion analitica posterior

### 3. `operaciones`

Se usa para:

- listado historico
- sync de operaciones
- filtros por numero, estado, fechas y pais
- flujo operativo mensual en `Resumen`, `Estrategia` y `Planeacion`
- lectura reciente de compras, ventas, dividendos y suscripciones FCI

Hallazgo operativo importante:

- para compras a mercado, `cantidad` del listado puede actuar como monto objetivo y no como unidades ejecutadas
- la ejecucion real debe leerse desde:
  - `cantidadOperada`
  - `precioOperado`
  - `montoOperado`

Conclusion:

- ya dejó de ser solo trazabilidad base
- sigue faltando explotar mejor fills, aranceles y detalle por número en producto

### 4. `operaciones/{numero}`

Se usa para:

- enriquecer una operacion concreta con:
  - estados
  - aranceles
  - fills
  - fechas detalladas

Conclusion:

- el contrato ya esta endurecido
- todavia esta subutilizado en producto

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
- capa táctica compartida para `Resumen`, `Estrategia` y `Planeacion`

Valor diferencial real:

- `tipo`
- `pais`
- `mercado`
- `cantidadMinima`
- `puntosVariacion`
- `puntas`
- `cantidadOperaciones`

Conclusion:

- ya dejó de estar aislado en observabilidad
- hoy potencia lectura táctica de producto, aunque todavía no se persiste como snapshot histórico puntual

### 8. `seriehistorica`

Se usa para:

- persistir cierres diarios IOL por simbolo
- mejorar volatilidad, tracking error, VaR y cobertura de riesgo
- observabilidad de cobertura en `Ops`

Conclusion:

- esta bien integrado
- la brecha principal no es el endpoint sino la cobertura efectiva del universo del portfolio

## Donde hoy no le estamos sacando el maximo provecho

Los endpoints con mayor potencial todavia no exprimido son:

1. `CotizacionDetalle`
   - hoy ya sirve en `Ops`, pero todavia no alimenta mas decisiones operativas o surfaces de producto
2. `operaciones/{numero}`
   - tiene detalle util de fills y aranceles que no se explota visualmente
3. `operaciones`
   - podria usarse mejor para lectura de flujos, dividendos y actividad reciente
4. `portafolio/{pais}`
   - `parking` ya entra, pero sigue sin valor de negocio visible

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
