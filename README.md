# Portafolio IOL - Plataforma de Gestion Patrimonial Cuantitativa

Aplicacion Django para sincronizar datos de InvertirOnline, construir snapshots historicos y calcular metricas de riesgo/performance para toma de decisiones patrimoniales.

## Estado actual
- Fase: P7 (Hardening, documentacion y productizacion)
- Stack: Django 5.2, DRF, Bootstrap 5, Chart.js, Celery, Redis
- Entorno objetivo: Render (Free tier) y Docker local

## Arquitectura
- Ingestion: `IOLSyncService` (cuentas, portafolio, operaciones)
- Persistencia: snapshots en `PortfolioSnapshot`, `ActivoPortafolioSnapshot`, `ResumenCuentaSnapshot`
- Analitica: servicios de riesgo, performance, benchmarking, attribution, liquidez y data quality
- Entrega: Dashboard Django + API interna DRF (`/api/...`)

Ver diagrama: `docs/architecture_diagram.md`

## Funcionalidades principales
- Dashboard consolidado de patrimonio y riesgo
- VaR/CVaR, volatilidad, stress testing
- Attribution por activo/sector/pais/tipo patrimonial
- Benchmarking (Tracking Error, Information Ratio)
- Liquidez operativa y dias estimados de liquidacion
- Auditoria de metadata de activos
- Integridad de snapshots y auditoria de sincronizacion IOL
- Simulador, optimizacion (Markowitz, Risk Parity) y plan mensual

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

## Ejecucion local (sin Docker)
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

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
- Proxima fase: automatizacion de decisiones y playbooks operativos

## Capturas
Agregar capturas en `docs/screenshots/`:
- `dashboard-overview.png`
- `risk-panel.png`
- `data-quality-panel.png`

## Disclaimer
Herramienta de analisis y soporte de decision. No constituye asesoramiento financiero.
