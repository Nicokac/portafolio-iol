# IOL - Plan MVP para `/api/v2/titulos/{mercado}/{simbolo}/historicos`

## Objetivo

Integrar precios historicos por instrumento desde IOL para mejorar la calidad de riesgo y performance del portfolio sin romper contratos actuales ni disparar requests por cada render.

El foco del MVP es:

- mejorar `volatility_proxy` por activo
- reducir fallbacks heurísticos en `RiskContributionService`
- preparar una base reutilizable para `VolatilityService`, `VaRService`, `CVaRService` y `TemporalMetricsService`

No es objetivo de este MVP:

- reemplazar toda la valuacion actual del portafolio
- reescribir analytics v2
- hacer pricing intradia
- construir un data lake de mercado

## Reutilización detectada

### Cliente IOL ya existente

- `apps/core/services/iol_api_client.py`

Ya maneja:

- autenticacion
- refresh de token
- `_request_json(...)`

La integracion nueva debe extender ese cliente, no abrir otro.

### Consumidores actuales que mas valor reciben

- `apps/core/services/analytics_v2/risk_contribution_service.py`
- `apps/core/services/risk/volatility_service.py`
- `apps/core/services/temporal_metrics_service.py`

Hoy esos servicios:

- usan snapshots internos del portafolio
- degradan a fallback cuando falta historia suficiente
- no tienen serie robusta diaria por instrumento para toda la cartera

### Modelos y persistencia reutilizable

No existe hoy un modelo de precios historicos por instrumento.

Eso implica que el MVP debe decidir entre:

1. cache efimero
2. persistencia local dedicada

Para este caso, la recomendacion es persistencia local minima.

## Problema actual

Hoy `RiskContributionService` intenta estimar volatilidad por simbolo usando:

- `ActivoPortafolioSnapshot`
- `valorizado`
- deduplicacion diaria por fecha

Eso tiene dos limites:

1. depende de que el activo haya aparecido en snapshots del portfolio
2. mezcla cambios de posicion con cambios de precio si la cantidad cambia

Como resultado:

- la volatilidad historica por activo puede estar sesgada
- se usan demasiados fallbacks

## Diseño técnico recomendado

### Capa 1 - Cliente

Agregar en `IOLAPIClient`:

- `get_titulo_historicos(mercado: str, simbolo: str, params: dict | None = None)`

Responsabilidad:

- solo hacer request y devolver JSON
- no interpretar series

Endpoint esperado:

- `/api/v2/titulos/{mercado}/{simbolo}/historicos`

### Capa 2 - Persistencia local minima

Agregar un modelo simple de serie historica por simbolo.

Estructura sugerida:

- `simbolo`
- `mercado`
- `fecha`
- `apertura`
- `maximo`
- `minimo`
- `cierre`
- `volumen`
- `source = "iol"`
- timestamps

Reglas:

- una fila por `simbolo + mercado + fecha`
- no guardar intradia
- si el endpoint devuelve mas granularidad, consolidar a diario antes de persistir

### Capa 3 - Sync controlado

Agregar un sync acotado que:

- tome solo simbolos actualmente invertidos
- haga backfill limitado
- refresque ventana reciente

Ventanas sugeridas:

- backfill inicial: `180d`
- refresh operativo diario: `30d`

No debe vivir en render ni selectors.

### Capa 4 - Lectura reusable

Agregar un helper o servicio de lectura que resuelva:

- serie diaria de cierre por simbolo
- `None` si la cobertura es insuficiente

Orden de uso sugerido:

1. serie historica persistida desde IOL
2. fallback actual con `ActivoPortafolioSnapshot`
3. fallback por tipo de activo

## Primer consumidor recomendado

### `RiskContributionService`

Es el mejor primer consumidor porque:

- ya tiene logica de `volatility_proxy`
- ya sabe degradar a fallback
- el valor incremental es inmediato

Cambio recomendado:

- `_get_asset_historical_volatility(...)` debe intentar primero la serie IOL persistida
- si no alcanza `MIN_ASSET_OBSERVATIONS`, mantener comportamiento actual

Esto mantiene compatibilidad y evita romper el MVP vigente.

## Consumidores posteriores

### `VolatilityService`

Valor:

- mejor base para volatilidad y ratios

Restriccion:

- este servicio hoy calcula volatilidad del patrimonio agregado, no por instrumento
- no debe mezclarse con el modulo inicial

### `TemporalMetricsService`

Valor:

- podria usar mejores precios en comparaciones futuras

Restriccion:

- no debe ser el primer consumidor
- primero hay que estabilizar la cobertura por simbolo

## Cache y performance

No hacer requests a IOL:

- desde template
- desde selector
- desde cada llamada analitica

Regla obligatoria:

- el endpoint IOL se consume solo via sync o refresh controlado

Estrategia recomendada:

- persistencia local diaria
- lectura desde DB
- refresh explicitamente operado

## Riesgos principales

### 1. Mapping `simbolo -> mercado`

No todos los simbolos del portfolio tienen el mercado resuelto de forma explicita y estable.

Mitigacion:

- usar metadata actual del snapshot cuando exista
- complementar con `ParametroActivo` si hace falta
- fallback conservador y explicitamente auditado

### 2. Cobertura parcial

No todos los activos van a tener historia suficiente.

Mitigacion:

- mantener `used_volatility_fallback`
- no ocultar warnings

### 3. Rate limit / costo operativo

Pegarle a IOL por cada simbolo y cada render es inviable.

Mitigacion:

- sync batch
- persistencia
- ventana limitada

### 4. OHLCV inconsistente

Si IOL cambia payload o periodicidad, no debe romper analytics.

Mitigacion:

- parser defensivo
- tests de contrato
- fallback actual intacto

## Scope MVP exacto

### Incluido

- cliente IOL para `historicos`
- persistencia diaria minima
- sync para simbolos invertidos actuales
- integracion con `RiskContributionService`
- tests de contrato y fallback

### Excluido

- UI nueva
- endpoints API nuevos
- recalculo de todo `TemporalMetricsService`
- reemplazo total de `VolatilityService`
- uso para simulacion o decision engine

## Criterios de aceptación

Se considera MVP terminado si:

1. se puede sincronizar historia diaria para simbolos actuales
2. `RiskContributionService` usa la serie IOL cuando existe
3. mantiene fallback actual cuando no existe historia suficiente
4. no hay requests a IOL durante render
5. hay tests para:
   - payload valido
   - historia insuficiente
   - fallback conservado
   - simbolo sin mercado claro

## Orden recomendado de implementación

1. cliente IOL `historicos`
2. modelo local de serie historica
3. sync/refresh controlado
4. integracion con `RiskContributionService`
5. tests

## Commit sugerido para la futura implementación

```text
feat(iol): agrega base historica diaria por simbolo para mejorar risk contribution
```
