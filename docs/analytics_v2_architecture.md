# Analytics v2 - Arquitectura Tecnica

## Objetivo

Definir como se integra Analytics v2 al proyecto actual sin romper v1 y sin duplicar la capa de servicios ya existente.

## Problema arquitectonico

La aplicacion ya tiene:

- servicios de riesgo
- servicios de performance
- benchmark compuesto
- snapshots historicos
- metadata por activo
- motor de recomendaciones
- dashboard server-rendered
- API interna para metricas

Analytics v2 no debe crear otra arquitectura paralela.
Debe ubicarse como una extension modular dentro de `apps/core/services`, con contratos serializables y consumo limpio desde dashboard y API.

## Arquitectura actual reutilizable

### Capa de datos existente

Fuentes actuales:

- `ActivoPortafolioSnapshot`
- `ResumenCuentaSnapshot`
- `PortfolioSnapshot`
- `PositionSnapshot`
- `ParametroActivo`
- `BenchmarkSnapshot`
- `MacroSeriesSnapshot`

### Capa de servicios existente

Namespaces actuales en `apps/core/services`:

- `risk/`
- `performance/`
- `liquidity/`
- `portfolio/`
- `market_data/`
- `data_quality/`
- servicios top-level como:
  - `temporal_metrics_service.py`
  - `benchmark_series_service.py`
  - `local_macro_series_service.py`
  - `recommendation_engine.py`
  - `rebalance_engine.py`

### Capa de consumo actual

- `apps/dashboard/views.py`
  - consume selectores y renderiza templates
- `apps/api/views.py`
  - expone endpoints JSON para metricas y planeacion
- `apps/dashboard/selectors.py`
  - arma KPIs y estructuras para vistas server-rendered

## Decision de arquitectura para v2

Analytics v2 se integrara como una nueva subcarpeta dentro de `apps/core/services`:

```text
apps/core/services/analytics_v2/
```

No debe reemplazar servicios existentes de v1.
Debe convivir con ellos y reutilizar sus salidas cuando sea razonable.

## Estructura propuesta

```text
apps/core/services/analytics_v2/
    __init__.py
    schemas.py
    helpers.py
    adapters.py
    risk_contribution_service.py
    scenario_analysis_service.py
    factor_exposure_service.py
    stress_fragility_service.py
    expected_return_service.py
```

## Rol de cada archivo

### `schemas.py`

Define estructuras de salida serializables y estables para v2.

Contenido esperado:

- payloads por activo
- payloads agregados por sector/pais/tipo
- metadata metodologica
- flags de calidad de datos
- resultados por escenario
- resultados por factor

### `helpers.py`

Contendra helpers puros y reutilizables.

Contenido esperado:

- normalizacion de pesos
- agregacion por buckets
- ordenamiento de top contributors
- manejo de faltantes y proxys
- banderas de confianza

### `adapters.py`

Contendra adaptadores desde modelos/servicios actuales hacia inputs de v2.

Contenido esperado:

- adaptar posiciones actuales a formato normalizado
- adaptar snapshots a series consumibles
- adaptar metadata de `ParametroActivo`
- adaptar benchmark y macro cuando un modulo lo requiera

Regla:
- los modulos v2 no deben leer templates ni depender de vistas
- deben consumir adaptadores o servicios existentes

### `risk_contribution_service.py`

Responsable del modulo MVP 1.

### `scenario_analysis_service.py`

Responsable del modulo MVP 2.

### `factor_exposure_service.py`

Responsable del modulo MVP 3.

### `stress_fragility_service.py`

Responsable del modulo MVP 4.

### `expected_return_service.py`

Responsable del modulo MVP 5.

## Contratos de integracion

### Integracion con dashboard

Analytics v2 no se consumira directamente desde templates.

Patron esperado:

1. servicio v2 produce payload serializable
2. API o selector lo adapta si hace falta para presentacion
3. template solo renderiza

### Integracion con API

Los endpoints nuevos de v2 deben ubicarse en `apps/api/views.py` y seguir la convencion actual:

- validacion simple de query params
- llamada a servicio
- metadata metodologica
- respuesta serializable

Ejemplos futuros:

- `/api/analytics-v2/risk-contribution/`
- `/api/analytics-v2/scenario-analysis/`
- `/api/analytics-v2/factor-exposure/`
- `/api/analytics-v2/stress-fragility/`
- `/api/analytics-v2/expected-return/`

### Integracion con recomendaciones

`RecommendationEngine` no debe absorber calculos complejos de v2.

Patron esperado:

- v2 produce senales o outputs estructurados
- `RecommendationEngine` solo consume esas senales
- la priorizacion final sigue viviendo en el motor de recomendaciones

### Integracion con rebalanceo

`RebalanceEngine` puede consumir salidas de v2 solo como insumo adicional.
No debe duplicar algoritmos de v2.

## Regla de compatibilidad con v1

Analytics v2 debe ser aditivo.

Esto implica:

- no cambiar contratos de v1 sin necesidad real
- no mover servicios actuales fuera de sus ubicaciones actuales
- no acoplar v2 a templates
- no reemplazar selectores existentes hasta que haya una necesidad concreta
- preferir endpoints y consumidores nuevos o claramente aislados

## Flujo tecnico recomendado por modulo

Para cada modulo de v2:

1. adaptar datos actuales con `adapters.py`
2. calcular con helpers/servicio del modulo
3. devolver schema serializable
4. agregar tests unitarios propios
5. exponer integracion via API o capa consumidora especifica

## Dependencias permitidas

Los modulos de `analytics_v2` pueden depender de:

- modelos existentes
- `ParametroActivo`
- snapshots
- `VolatilityService`
- `TWRService`
- `TrackingErrorService`
- `BenchmarkSeriesService`
- `LocalMacroSeriesService`
- helpers de pandas ya usados por el proyecto

No deben depender de:

- templates
- clases de vista
- `request`
- objetos HTTP
- renderizado UI

## Manejo de faltantes de datos

Cada modulo v2 debe soportar explicitamente:

- portafolio vacio
- activos sin metadata
- historia insuficiente
- benchmark faltante
- volatilidad faltante
- clasificacion desconocida

Regla:
- no fallar silenciosamente
- devolver flags o metadata de calidad
- usar fallback solo si esta documentado

## Riesgos arquitectonicos a evitar

- duplicar logica ya existente en `selectors.py`
- duplicar logica de riesgo ya resuelta por servicios de v1
- mezclar logica de calculo con presentacion
- crear clases demasiado generales sin uso real
- meter toda la logica v2 en `RecommendationEngine`
- usar modelos nuevos sin necesidad demostrada

## Criterios de aceptacion de la arquitectura v2

La arquitectura tecnica de v2 sera valida si:

- reutiliza servicios y modelos actuales
- define una ubicacion clara para modulos nuevos
- mantiene contratos serializables
- mantiene bajo acoplamiento con dashboard y API
- permite agregar modulos sin tocar toda la arquitectura
- conserva compatibilidad con v1

## Estado

Documento base de arquitectura tecnica.
Listo para servir como referencia del siguiente modulo: contratos de datos de Analytics v2.
