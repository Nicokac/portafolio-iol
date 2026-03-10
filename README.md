# Portafolio IOL — Plataforma de Gestión de Inversiones

Aplicación web Django para gestionar, analizar y optimizar el portafolio de inversiones en InvertirOnline (IOL). Incluye sincronización automática con la API de IOL, snapshots históricos, sistema de alertas patrimoniales, motor de rebalanceo estratégico y API REST interna.

## Estado del Proyecto

| Métrica | Valor |
|---|---|
| Cobertura de tests | 80% |
| Tests | ~200 |
| Deploy | Render (Free Tier) |
| CI/CD | GitHub Actions |
| Branch principal | `main` |

## Stack Tecnológico

- **Backend**: Python 3.12 + Django 5.2 + Django REST Framework
- **Frontend**: Django Templates + Bootstrap 5 + Chart.js
- **Base de datos**: SQLite (desarrollo) / PostgreSQL — AWS RDS (producción)
- **Task scheduling**: Celery + Redis + django-celery-beat
- **Data processing**: Pandas para métricas temporales
- **Deploy**: Render + Gunicorn + WhiteNoise
- **Testing**: pytest + pytest-django + pytest-cov
- **Linting**: Ruff
- **CI/CD**: GitHub Actions
- **Seguridad**: detect-secrets, bandit, pip-audit

## Funcionalidades

### Dashboard
- KPIs en tiempo real: Total IOL, liquidez operativa, cash management, portafolio invertido
- Porcentajes estratégicos por bloque patrimonial
- Concentración de riesgo: top 5/10 posiciones con alertas
- Rendimiento: ganancias absolutas y porcentuales
- Evolución histórica con Chart.js

### Sincronización Automática
- Actualización desde IOL API cada 30 minutos via Celery
- Snapshots históricos diarios a las 6:00 AM
- Gestión persistente de tokens JWT en base de datos

### Sistema de Alertas
- Concentración excesiva, liquidez elevada, exposición país/sector
- Severidades: info, warning, critical
- Monitoreo continuo cada hora

### Motor de Rebalanceo
- Análisis estratégico vs objetivos definidos
- Sugerencias de acciones críticas y oportunidades
- Tolerancias configurables por banda estratégica

### API REST Interna
Todos los endpoints requieren autenticación.

```
GET  /api/dashboard/kpis/
GET  /api/dashboard/concentracion-pais/
GET  /api/dashboard/concentracion-sector/
GET  /api/dashboard/senales-rebalanceo/
GET  /api/alerts/active/
GET  /api/alerts/by-severity/?severity=warning
GET  /api/rebalance/suggestions/
GET  /api/rebalance/critical/
GET  /api/rebalance/opportunity/
GET  /api/metrics/returns/?days=30
GET  /api/metrics/volatility/?days=30
GET  /api/metrics/performance/?days=90
GET  /api/metrics/historical-comparison/?periods=7,30,90,180
GET  /api/historical/evolution/?days=90
GET  /api/historical/summary/
POST /api/simulation/purchase/
POST /api/simulation/sale/
POST /api/simulation/rebalance/
POST /api/optimizer/risk-parity/
POST /api/optimizer/markowitz/
POST /api/optimizer/target-allocation/
POST /api/monthly-plan/basic/
POST /api/monthly-plan/custom/
GET  /api/portfolio-parameters/
POST /api/portfolio-parameters/update/
GET  /health/
```

### Health Check
`GET /health/` retorna `{"status": "ok", "db": "ok"}` con HTTP 200, o HTTP 503 si la base de datos no responde.

## Instalación

### Prerrequisitos
- Python 3.12+
- Redis (para Celery)
- Cuenta activa en InvertirOnline

### Setup

```bash
git clone https://github.com/tu-usuario/portafolio-iol.git
cd portafolio-iol

python -m venv venv
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements/dev.txt
cp .env.example .env
# Editar .env con credenciales

python manage.py migrate
python manage.py createsuperuser
pre-commit install
```

### Variables de Entorno

```env
# Django
SECRET_KEY=tu-clave-secreta
DEBUG=True
DJANGO_SETTINGS_MODULE=config.settings.dev
ALLOWED_HOSTS=localhost,127.0.0.1

# IOL API
IOL_USERNAME=tu-usuario-iol
IOL_PASSWORD=tu-password-iol
IOL_BASE_URL=https://api.invertironline.com

# Base de datos (producción)
DB_NAME=portafolio_iol
DB_USER=tu-usuario-db
DB_PASSWORD=tu-password-db
DB_HOST=localhost
DB_PORT=5432

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Sentry (opcional)
SENTRY_DSN=https://tu-sentry-dsn@sentry.io/project-id
```

## Ejecución

```bash
# Terminal 1: Servidor Django
python manage.py runserver

# Terminal 2: Worker Celery
celery -A portafolio_iol worker --loglevel=info

# Terminal 3: Scheduler Celery Beat
celery -A portafolio_iol beat --loglevel=info
```

### Sincronización Manual

```bash
python manage.py actualizar_iol
python manage.py actualizar_iol --estado-cuenta
python manage.py actualizar_iol --portafolio
python manage.py actualizar_iol -v 2
```

## Testing

```bash
# Suite completa con cobertura
pytest --ignore=apps/core/tests/test_p4.py --ignore=scripts/

# Sin cobertura (más rápido)
pytest --ignore=apps/core/tests/test_p4.py --ignore=scripts/ --no-cov

# Módulo específico
pytest apps/dashboard/tests/ --tb=short -q --no-cov

# Reporte HTML de cobertura
pytest --cov=apps --cov-report=html
```

### Estado de Cobertura por Módulo

| Módulo | Cobertura |
|---|---|
| `apps/dashboard/` | 88%+ |
| `apps/core/services/token_manager.py` | 100% |
| `apps/core/services/alerts_engine.py` | 75%+ |
| `apps/core/services/rebalance_engine.py` | 75%+ |
| `apps/core/services/portfolio_simulator.py` | 79%+ |
| `apps/api/` | 65%+ |
| **Total** | **80%** |

## Linting y Calidad

```bash
# Linting
ruff check .

# Formateo
ruff format .

# Seguridad
bandit -r apps/ -ll -q
pip-audit -r requirements/base.txt
detect-secrets scan
```

## CI/CD

GitHub Actions ejecuta en cada push/PR a `develop` y `main`:

1. **lint**: Ruff check y format
2. **django-checks**: `manage.py check --deploy`, migraciones, collectstatic
3. **test**: pytest con cobertura mínima 80%
4. **security**: bandit + pip-audit

## Deploy en Render

Configurado via `render.yaml`. Variables de entorno requeridas en el dashboard de Render:

- `SECRET_KEY`, `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `IOL_USERNAME`, `IOL_PASSWORD`, `IOL_BASE_URL`
- `SENTRY_DSN` (opcional)

```bash
# Verificar configuración de producción
python manage.py check --deploy

# Recopilar estáticos
python manage.py collectstatic --noinput
```

## Estructura del Proyecto

```
portafolio_iol/
├── .github/workflows/ci.yml
├── apps/
│   ├── api/                        # API REST interna
│   ├── core/
│   │   ├── services/
│   │   │   ├── iol_api_client.py
│   │   │   ├── token_manager.py
│   │   │   ├── portfolio_snapshot_service.py
│   │   │   ├── alerts_engine.py
│   │   │   ├── rebalance_engine.py
│   │   │   └── temporal_metrics_service.py
│   │   ├── tasks/portfolio_tasks.py
│   │   ├── management/commands/actualizar_iol.py
│   │   └── views.py                # /health/ endpoint
│   ├── dashboard/
│   │   ├── selectors.py            # Lógica de negocio
│   │   └── views.py
│   ├── parametros/                 # Metadatos de activos
│   ├── portafolio_iol/             # Snapshots históricos
│   ├── resumen_iol/                # Estado de cuenta
│   ├── operaciones_iol/            # Historial de órdenes
│   └── users/
├── config/settings/
│   ├── base.py
│   ├── dev.py
│   └── prod.py
├── docs/DECISIONS.md               # Registro de decisiones técnicas
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── Procfile
├── render.yaml
└── pyproject.toml
```

## Decisiones Técnicas

Ver `docs/DECISIONS.md` para el registro completo. Decisiones principales:

- **D-001**: `beat_schedule` removido de `celery.py` — usar `DatabaseScheduler` para evitar conflictos
- **D-002**: Celery/Redis pendiente de configurar en Render (Free Tier no incluye Redis)

## Métricas Patrimoniales

### Bloques Estratégicos
- **Total IOL**: Patrimonio total (activos + cash)
- **Liquidez Operativa**: Cash + caución + FCI disponibles (objetivo: 25%)
- **FCI Cash Management**: Fondos de liquidez (objetivo: 7.5%)
- **Portafolio Invertido**: Activos de inversión (objetivo: 67.5%)

### Objetivos por Sector
- Tecnología: 17.5%
- ETF Core: 22.5%
- Argentina: 12.5%
- Bonos: 12.5%
- Defensivos: 12.5%

### Señales de Rebalanceo
- Sobreponderado: > objetivo + 5%
- Subponderado: < objetivo − 3%
- Sin objetivo: < 2% del portafolio

## Roadmap

- [ ] Alertas visuales en tiempo real en el dashboard
- [ ] Cache con Redis para optimizar performance
- [ ] Backtesting de estrategias de rebalanceo
- [ ] Reportes PDF automatizados
- [ ] Configurar Redis en Render para Celery en producción

## Licencia

MIT. Ver archivo `LICENSE` para detalles.

---

> Este software es una herramienta de análisis personal. No constituye asesoramiento financiero. Toda decisión de inversión es responsabilidad del usuario.