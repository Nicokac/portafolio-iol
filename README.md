# Portafolio IOL - Plataforma de gestion patrimonial cuantitativa

Aplicacion Django para sincronizar datos de InvertirOnline, construir snapshots historicos, calcular metricas de riesgo y performance, y exponer una capa operativa de analitica patrimonial desde UI y API interna.

## Estado actual

- Stack principal: Django 5.2, DRF, Bootstrap 5, Chart.js, Celery, Redis
- Cobertura actual de tests: ~88%
- Entorno local por defecto: SQLite
- Entorno objetivo de despliegue: Docker / Render

El producto hoy ya expone:

- `Resumen` diario
- `Estrategia` con `Analytics v2`
- `Analisis`, `Performance` y `Metricas`
- `Planeacion` con simulacion, optimizacion y capa incremental
- `Ops` para observabilidad staff

## Capacidades principales

### Dashboard y lectura patrimonial

- KPIs diarios de patrimonio, liquidez, concentracion y exposicion
- evolucion historica del portafolio
- alertas activas
- contexto macro local resumido

### Analytics v2

- `Risk Contribution`
- `Scenario Analysis`
- `Factor Exposure`
- `Stress Fragility`
- `Expected Return`
- interpretaciones automaticas y senales combinadas

Drill-downs hoy visibles:

- `/estrategia/risk-contribution/`
- `/estrategia/scenario-analysis/`
- `/estrategia/factor-exposure/`
- `/estrategia/stress-fragility/`
- `/estrategia/expected-return/`

### Planeacion y decision incremental

- tab `Aportes` como punto de entrada recomendado de la hoja
- recomendaciones combinadas
- sugerencias de rebalanceo
- simulacion de compra, venta y rebalanceo
- plan mensual custom
- optimizacion `Risk Parity`, `Markowitz` y `Target Allocation`
- motor MVP de asignacion mensual incremental
- ranking de activos candidatos dentro de bloques recomendados
- simulacion incremental `before/after`
- comparadores incrementales automaticos, por candidato, por split y manuales
- propuesta incremental preferida
- historial reciente de propuestas guardadas y decision manual
- exploracion y seguimiento relegados a secciones secundarias dentro de `Planeacion`

### Observabilidad y gobierno de datos

- dashboard `Ops` para staff
- sync audit de IOL
- integridad de snapshots
- continuidad diaria
- resumen unificado del pipeline
- estado de benchmarks y macro local

## Arquitectura

- Ingestion:
  - `IOLSyncService`
  - clientes de market data externos
- Persistencia:
  - `PortfolioSnapshot`
  - `ActivoPortafolioSnapshot`
  - `ResumenCuentaSnapshot`
  - `BenchmarkSnapshot`
  - `MacroSeriesSnapshot`
  - `IncrementalProposalSnapshot`
- Analitica:
  - riesgo
  - performance
  - benchmarking
  - liquidez
  - recomendaciones
  - `Analytics v2`
- Entrega:
  - dashboard Django server-rendered
  - API interna DRF bajo `/api/...`

Ver tambien:

- `docs/architecture_diagram.md`
- `docs/portfolio_analytics_v2_spec.md`
- `docs/analytics_v2_feature_exposure_checklist.md`

## Macro local

La app ya persiste y expone un contexto macro local reutilizable.

Series principales:

- `usdars_oficial`
- `ipc_nacional`
- `badlar_privada`
- `usdars_mep` opcional
- `fx_gap_pct` derivada cuando hay MEP
- `riesgo_pais_arg`

Integraciones actuales:

- `riesgo_pais_arg` usa por default ArgentinaDatos:
  - `https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais`
- `Resumen` muestra card dedicada de riesgo pais con cambio 30d
- `LocalMacroSignalsService` ya expone senales simples como:
  - `local_country_risk_high`
  - `local_country_risk_deteriorating`
  - `local_fx_gap_high`
  - `local_fx_gap_deteriorating`

## Operacion diaria

Acciones manuales visibles para `staff`:

- `Actualizar IOL`
- `Generar Snapshot`
- `Sincronizar benchmarks`
- `Sincronizar macro local`

Flujo practico:

1. sincronizar IOL
2. generar o validar snapshot
3. revisar `Resumen` y `Estrategia`
4. usar `Planeacion` para simulacion, aportes y decision incremental
5. usar `Ops` si hay dudas de datos o estado del pipeline

Si hay migraciones pendientes, aplicarlas antes de usar acciones manuales o modulos nuevos:

```bash
python manage.py migrate
```

## Endpoints internos utiles

- `GET /api/metrics/returns/`
- `GET /api/metrics/volatility/`
- `GET /api/metrics/benchmarking/`
- `GET /api/metrics/var/`
- `GET /api/metrics/cvar/`
- `GET /api/metrics/liquidity/`
- `GET /api/metrics/data-quality/`
- `GET /api/metrics/snapshot-integrity/`
- `GET /api/metrics/sync-audit/`
- `GET /api/metrics/internal-observability/`
- `POST /api/monthly-plan/custom/`
- `POST /api/simulation/purchase/`
- `POST /api/simulation/sale/`
- `POST /api/simulation/rebalance/`
- `POST /api/optimizer/risk-parity/`
- `POST /api/optimizer/markowitz/`
- `POST /api/optimizer/target-allocation/`

## Variables de entorno

Minimas para uso local:

- `SECRET_KEY`
- `IOL_USERNAME`
- `IOL_PASSWORD`
- `IOL_BASE_URL=https://api.invertironline.com`

Opcionales para macro local:

- `USDARS_MEP_API_URL`
- `USDARS_MEP_API_VALUE_PATH`
- `USDARS_MEP_API_DATE_PATH`
- `RIESGO_PAIS_API_URL`
- `RIESGO_PAIS_API_VALUE_PATH`
- `RIESGO_PAIS_API_DATE_PATH`
- `RIESGO_PAIS_API_KEY`
- `RIESGO_PAIS_API_KEY_HEADER`

Defaults relevantes:

- `RIESGO_PAIS_API_URL` ya apunta por default a ArgentinaDatos
- `RIESGO_PAIS_API_VALUE_PATH=valor`
- `RIESGO_PAIS_API_DATE_PATH=fecha`

Si no se configura `USDARS_MEP_API_URL`:

- el sync macro local sigue funcionando
- `usdars_mep` queda como fuente opcional no disponible
- la brecha FX no se calcula

## Ejecucion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

## Docker

```bash
docker compose up --build
```

Servicios esperados:

- `django`
- `postgres`
- `redis`
- `celery`
- `celery-beat`

## Testing y calidad

```bash
python -m pytest --ignore=scripts/
ruff check .
ruff format --check .
python manage.py check
```

Meta de cobertura exigida por el repo:

- `>= 80%`

## Roadmap corto

Estado funcional actual:

- `Analytics v2` base expuesto en `Estrategia`
- macro local con riesgo pais y brecha FX
- stack incremental visible en `Planeacion`

Siguiente trabajo recomendado:

- racionalizar dependencias internas del stack incremental
- abrir nuevos modulos solo si agregan valor real a la decision de inversion
- evitar volver a sobrecargar `Planeacion` con capas operativas redundantes

## Disclaimer

Herramienta de analisis y soporte de decision. No constituye asesoramiento financiero.
