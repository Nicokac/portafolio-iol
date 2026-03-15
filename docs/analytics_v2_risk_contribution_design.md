# Analytics v2 - Risk Contribution MVP - Diseno del Algoritmo

## Objetivo del modulo

Definir el algoritmo MVP de `risk contribution` para responder:

> que posiciones explican la mayor parte del riesgo relativo del portafolio

El objetivo del MVP no es estimar contribucion marginal exacta de varianza con covarianza completa.
El objetivo es construir una lectura explicativa, auditable y util para producto usando los datos reales hoy disponibles.

## Fuentes existentes reutilizables

### Posiciones y metadata

- `ActivoPortafolioSnapshot`
- `ParametroActivo`
- selectores actuales de composicion y clasificacion

### Riesgo e historia

- `VolatilityService`
- `TWRService`
- `PortfolioSnapshot`
- `PositionSnapshot`

### Agrupacion y trazabilidad

- `AttributionService`
- metadata sectorial, geografica y patrimonial ya vigente

### Helpers y contratos ya creados en v2

- `apps/core/services/analytics_v2/schemas.py`
- `apps/core/services/analytics_v2/helpers.py`

## Que se reutiliza y que no

### Reutilizacion explicita

Se debe reutilizar:

- taxonomia de `ParametroActivo`
- criterio de liquidez ya usado por dashboard
- warnings por historia insuficiente ya coherentes con `VolatilityService`
- helpers de agrupacion y calidad de datos de `analytics_v2/helpers.py`

### Lo que NO se reutiliza en esta etapa

No se debe reutilizar para el MVP:

- `CovarianceService` como base del algoritmo principal
- `RiskParityService`
- Markowitz
- matrices de covarianza como condicion necesaria

Razon:

- el gap analysis ya determino que hoy no hay base suficiente para un modelo covariance-aware robusto por activo para toda la cartera

## Universo economico del calculo

La base del modulo debe ser:

- `portafolio invertido`

No debe incluir como riesgo economico equivalente:

- cash disponible
- liquidez operativa pura

Tratamiento especial:

- caucion: contribucion muy baja o cero segun regla de liquidez
- cash management: contribucion baja via proxy monetario, nunca comparable a equity

## Definicion del algoritmo MVP

### Formula central

Para cada activo elegible:

```text
risk_score_i = weight_i * volatility_proxy_i
```

Donde:

- `weight_i` = `market_value_i / invested_portfolio_total`
- `volatility_proxy_i` = proxy de volatilidad asignado segun prioridad definida abajo

Luego:

```text
contribution_pct_i = risk_score_i / sum(risk_score_all)
```

Resultado esperado:

- suma de `contribution_pct_i` aproximadamente 100%

## Prioridad de volatilidad proxy

Orden obligatorio de prioridad:

### 1. Volatilidad historica propia del activo

Usar si se puede construir una serie por activo con observaciones suficientes y calidad razonable.

Fuente posible:

- `ActivoPortafolioSnapshot` por simbolo en multiples fechas

Condicion minima MVP sugerida:

- al menos 5 observaciones utiles
- sin saltos absurdos que invaliden la serie

### 2. Volatilidad derivada de snapshots/serie instrumental simple

Usar si la serie existe pero no alcanza para una version robusta completa.

Salida esperada:

- valor proxy con `used_volatility_fallback=True`
- `confidence=medium` o `low` segun cobertura

### 3. Proxy por tipo de activo o bucket

Si el activo no tiene serie util:

- CEDEAR / equity / ETF equity: proxy equity internacional
- bonos argentinos: proxy renta fija AR / emergentes
- cash management: proxy monetario bajo
- liquidez operativa / caucion: proxy cercano a cero

### 4. Fallback final documentado

Si no existe ninguna clasificacion suficientemente confiable:

- usar un proxy conservador bajo
- marcar warning explicito
- degradar confidence

## Regla de liquidez

La liquidez no debe distorsionar la lectura de riesgo.

### Liquidez operativa

Tratamiento MVP:

- `risk_score = 0` o valor casi nulo explicitamente documentado

Justificacion:

- patrimonialmente pesa mucho, pero su fragilidad de mercado es baja
- sin esta regla, el modulo confundiria peso patrimonial con riesgo economico

### Caucion

Tratamiento MVP:

- misma familia que liquidez monetaria productiva
- `risk_score` nulo o casi nulo
- no se trata como equity ni como bono volatil

### Cash management

Tratamiento MVP:

- riesgo bajo
- volatilidad proxy monetaria, nunca comparable a acciones o CEDEARs

## Activos sin metadata

Si un activo no tiene metadata suficiente:

- mantenerlo en el detalle
- asignar `sector`, `country` o `asset_type` como `unknown`
- permitir calculo si existe market value y un fallback razonable de volatilidad
- marcar warning y degradar confidence

No se debe:

- excluir silenciosamente activos sin metadata
- imputar sectores o paises inventados

## Agregaciones requeridas

A partir del detalle por activo, el modulo debe agregar contribucion al riesgo por:

- sector
- pais
- tipo de activo

Regla de consistencia:

- la suma de agregados debe ser consistente con el detalle

## Calidad de datos y confidence

El resultado del modulo debe incluir metadata de calidad.

Senales minimas:

- `has_missing_metadata`
- `has_insufficient_history`
- `used_fallback`
- `confidence`
- `warnings`

Convencion sugerida:

- `high`: la mayoria de activos relevantes tienen metadata y proxy directo razonable
- `medium`: mezcla de proxy directo y fallback por bucket
- `low`: historia insuficiente general o demasiados activos relevantes con fallback pobre

## Outputs minimos del modulo

El servicio final de `risk contribution` debe devolver:

- `items`
- `by_sector`
- `by_country`
- `by_asset_type`
- `top_contributors`
- `metadata`

Contrato objetivo:

- el ya definido en `docs/analytics_v2_data_contracts.md`

## Reglas de interpretacion

El modulo debe dejar claro que:

- mide contribucion proxy al riesgo
- no es una contribucion marginal exacta de varianza
- sirve para detectar concentraciones de fragilidad relativas
- puede diferir de la simple concentracion patrimonial

## Casos que el algoritmo debe soportar

### 1. Portafolio vacio

Debe devolver resultado vacio serializable con warning.

### 2. Una sola posicion

Debe devolver 100% de contribucion para ese activo si es elegible.

### 3. Alta liquidez

La liquidez no debe dominar el modulo por peso patrimonial.

### 4. Activo sin historico suficiente

Debe usar fallback controlado, no fallar silenciosamente.

### 5. Activo sin metadata

Debe quedar como `unknown` y degradar confidence.

### 6. Mezcla de activos locales y globales

Debe poder agregar por sector y pais sin romper consistencia.

## Riesgos metodologicos del MVP

### 1. Confundir peso con riesgo

Mitigacion:

- usar volatilidad proxy
- tratar liquidez por separado

### 2. Falso nivel de precision

Mitigacion:

- metadata explicita
- `confidence`
- warnings por fallback

### 3. Uso excesivo de proxies pobres

Mitigacion:

- priorizacion estricta de fuentes
- no ocultar `used_volatility_fallback`

## Decision final de diseno

El algoritmo MVP de `risk contribution` queda definido asi:

1. tomar posiciones actuales sobre `portafolio invertido`
2. calcular peso relativo por activo
3. resolver volatilidad proxy por orden de prioridad
4. calcular `risk_score = peso * volatilidad_proxy`
5. normalizar a `contribution_pct`
6. agregar por sector, pais y tipo
7. emitir metadata de calidad y warnings

Este diseno es suficientemente util para MVP y compatible con la arquitectura actual.
No pretende reemplazar una version futura con covarianza real.

## Siguiente paso natural

El siguiente modulo tecnico correcto es:

- `2.2 — Implementacion por activo`

Eso ya deberia crear el servicio real del modulo sobre las bases definidas aqui.
