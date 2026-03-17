# Portafolio IOL - Plataforma de Gestion Patrimonial Cuantitativa

Aplicacion Django para sincronizar datos de InvertirOnline, construir snapshots historicos, calcular metricas de riesgo/performance y operar una capa analitica patrimonial desde dashboard y API interna.

## Estado actual
- Fase actual: P8 base completada + hardening de seguridad/testing
- Stack: Django 5.2, DRF, Bootstrap 5, Chart.js, Celery, Redis
- Entorno objetivo: Render (Free tier) y Docker local
- Cobertura de tests actual: ~97%

## Arquitectura
- Ingestion: `IOLSyncService` (cuentas, portafolio, operaciones)
- Persistencia: snapshots en `PortfolioSnapshot`, `ActivoPortafolioSnapshot`, `ResumenCuentaSnapshot`
- Analitica: servicios de riesgo, performance, benchmarking, attribution, liquidez, data quality y optimizacion
- Entrega: Dashboard Django + API interna DRF (`/api/...`)

Ver diagrama: `docs/architecture_diagram.md`

## Funcionalidades principales
- Dashboard consolidado de patrimonio y riesgo
- Centro de Performance
- Centro de Metricas Analiticas
- VaR/CVaR, volatilidad, stress testing
- Attribution por activo/sector/pais/tipo patrimonial
- Benchmarking (Tracking Error, Information Ratio)
- Liquidez operativa y dias estimados de liquidacion
- Auditoria de metadata de activos
- Integridad de snapshots y auditoria de sincronizacion IOL
- Simulador, optimizacion (Markowitz, Risk Parity) y plan mensual
- Acciones manuales desde UI para `Actualizar IOL` y `Generar Snapshot`
- Dashboard Ops restringido a `staff`

## Operacion diaria
- `Actualizar IOL`: sincroniza estado de cuenta, portafolio y operaciones.
- `Generar Snapshot`: fuerza una foto agregada diaria del portafolio.
- Si el sync de IOL termina correctamente, el snapshot diario se intenta generar automaticamente.
- Si faltan migraciones de seguridad/auditoria, ejecutar `python manage.py migrate` antes de usar acciones manuales.

## Endpoints clave
- `GET /api/metrics/performance/`
- `GET /api/metrics/var/`
- `GET /api/metrics/cvar/`
- `GET /api/metrics/benchmarking/`
- `GET /api/metrics/liquidity/`
- `GET /api/metrics/data-quality/`
- `GET /api/metrics/snapshot-integrity/`
- `GET /api/metrics/sync-audit/`
- `GET /api/metrics/internal-observability/`
- `POST /api/monthly-plan/custom/`
- `POST /api/simulation/purchase/`
- `POST /api/simulation/sale/`
- `POST /api/simulation/rebalance/`

## Metodologia financiera
Documento tecnico: `docs/financial_methodology.md`

## Variables de entorno
Copiar `.env.example` y completar al menos:
- `SECRET_KEY`
- `IOL_API_KEY` (si aplica)
- `IOL_USERNAME`
- `IOL_PASSWORD`
- `DATABASE_URL` (recomendado en prod)
- `REDIS_URL`

Variables opcionales para FX local / `USDARS MEP`:
- `USDARS_MEP_API_URL` recomendado:
  - `https://dolarapi.com/v1/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH` recomendado:
  - `venta`
- `USDARS_MEP_API_DATE_PATH` recomendado:
  - `fechaActualizacion`

Si no se configuran:
- el sync macro local sigue funcionando
- `usdars_mep` queda en estado `Sin configurar` / `skipped`
- la brecha FX no se calcula

## Ejecucion local (sin Docker)
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

Credenciales y variables minimas:
- `SECRET_KEY`
- `IOL_USERNAME`
- `IOL_PASSWORD`
- `IOL_BASE_URL=https://api.invertironline.com`

Opcional para señales locales FX:
- `USDARS_MEP_API_URL=https://dolarapi.com/v1/dolares/bolsa`
- `USDARS_MEP_API_VALUE_PATH=venta`
- `USDARS_MEP_API_DATE_PATH=fechaActualizacion`

## Ejecucion con Docker
```bash
docker compose up --build
```
Servicios: `django`, `postgres`, `redis`, `celery`, `celery-beat`.

## Testing y calidad
```bash
python -m pytest --ignore=scripts/
ruff check .
ruff format --check .
```
Meta de cobertura: `>= 80%`.

Notas:
- Los scripts manuales bajo `scripts/` no forman parte de la suite automatica.
- La suite actual cubre seguridad, API, comandos, snapshots, riesgo, performance y dashboard.

## CI/CD
GitHub Actions ejecuta:
- lint
- tests + coverage
- django checks
- security checks
- docker build

## Roadmap
- P0-P6: base analitica, riesgo cuantitativo, attribution, benchmarking, liquidez, gobierno de datos, estrategia cuantitativa
- P7: hardening + observabilidad + productizacion
- P8: integracion analitica en dashboard y centros de performance/metricas
- Proximo paso inmediato: integracion de benchmarks historicos externos para reemplazar proxies estaticos

## Capturas
Agregar capturas en `docs/screenshots/`:
- `dashboard-overview.png`
- `risk-panel.png`
- `data-quality-panel.png`

## Disclaimer
Herramienta de analisis y soporte de decision. No constituye asesoramiento financiero.
