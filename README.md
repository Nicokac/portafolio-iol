# 📊 Portafolio IOL - Plataforma Automatizada de Inversiones

Una aplicación web Django completa para gestionar, analizar y optimizar el portafolio de inversiones en InvertirOnline (IOL). **Fase P3 implementada**: Automatización completa con snapshots históricos diarios, sincronización automática cada 30 minutos, sistema de alertas patrimoniales inteligentes, motor de rebalanceo estratégico, métricas temporales avanzadas, API REST interna y scheduler con Celery.

## 🎯 Estado del Proyecto

✅ **Fase P3 Completa** - Plataforma totalmente automatizada con:
- Sincronización automática desde IOL API cada 30 minutos
- Snapshots históricos diarios del portafolio
- Sistema de alertas patrimoniales inteligentes
- Motor de rebalanceo estratégico
- Métricas temporales (retornos diarios/mensuales, volatilidad histórica)
- API REST interna para integración frontend
- Scheduler con Celery para automatización completa
- Tests de regresión completos

## ✨ Funcionalidades Principales

### 🤖 Automatización Completa (P3)
- **Sincronización Automática**: Actualización desde IOL API cada 30 minutos
- **Snapshots Diarios**: Historial completo del portafolio con evolución temporal
- **Scheduler Inteligente**: Celery para tareas programadas (sync, snapshots, alertas)
- **API REST Interna**: Endpoints completos para integración frontend

### 📈 Dashboard Interactivo
- **KPIs en Tiempo Real**: Total IOL, liquidez operativa, cash management, portafolio invertido
- **Porcentajes Estratégicos**: Todos los bloques patrimoniales expresados como % del total
- **Concentración de Riesgo**: Top 5/10 posiciones con alertas automáticas
- **Rendimiento**: Ganancias absolutas y porcentuales con indicadores visuales

### ⚠️ Sistema de Alertas Patrimoniales (P3)
- **Alertas Automáticas**: Concentración excesiva, liquidez elevada, exposición país/sector
- **Severidad Inteligente**: Info, Warning, Critical con mensajes contextuales
- **Monitoreo Continuo**: Generación cada hora con Celery
- **Acciones Recomendadas**: Sugerencias específicas para corrección

### 🎯 Motor de Rebalanceo Inteligente (P3)
- **Análisis Estratégico**: Evaluación automática vs objetivos definidos
- **Sugerencias de Rebalanceo**: Acciones críticas y oportunidades de inversión
- **Tolerancias Configurables**: Bandas estratégicas para señales significativas
- **Optimización Continua**: Análisis programado de posiciones sobre/subponderadas

### 📊 Métricas Temporales Avanzadas (P3)
- **Retornos Históricos**: Diario, semanal, mensual con cálculos precisos
- **Volatilidad**: Anualizada, Sharpe ratio, Sortino ratio con pandas
- **Drawdown Analysis**: Máximo drawdown y ratio Calmar
- **Comparativas**: Performance across múltiples períodos

### 🌍 Análisis de Exposición
- **Exposición Geográfica**: Distribución por países con mapeo inteligente
- **Exposición por Moneda**: Separación clara entre moneda económica (real) vs operativa (cotización)
- **Distribución Sectorial**: Análisis por sectores con agrupación estratégica
- **Tipo Patrimonial**: Clasificación por categorías de inversión

### 🔄 Sincronización y Datos Históricos
- **API IOL Integrada**: Sincronización completa de portafolio y estado de cuenta
- **Snapshots Históricos**: Conservación de datos para análisis temporal
- **Gestión de Tokens**: Persistencia automática de autenticación JWT
- **Actualización Programada**: Comandos para sync manual o automático

## 🏗️ Arquitectura Técnica

### Stack Tecnológico
- **Backend**: Python 3.12 + Django 5.2 + Django REST Framework
- **Frontend**: Django Templates + Bootstrap 5 + Chart.js
- **Base de Datos**: SQLite (desarrollo) / PostgreSQL (producción)
- **Data Processing**: Pandas para métricas temporales y analytics
- **Task Scheduling**: Celery + Redis para automatización completa
- **API Client**: requests con manejo robusto de autenticación JWT persistente
- **Testing**: Django TestCase + pytest para cobertura completa
- **Linting**: Ruff para código limpio y consistente
- **CI/CD**: GitHub Actions con validaciones automáticas

### Estructura de Apps (P3)
```
portafolio_iol/
├── apps/
│   ├── core/           # Servicios core: IOL API, tokens persistentes, alerts, rebalance
│   │   ├── services/   # IOLTokenManager, PortfolioSnapshotService, AlertsEngine, RebalanceEngine, TemporalMetricsService
│   │   └── tasks/      # Tareas Celery para automatización
│   ├── api/            # API REST interna para dashboard y frontend
│   ├── resumen_iol/    # Snapshots de estado de cuenta (cash disponible)
│   ├── portafolio_iol/ # Snapshots históricos de tenencias por activo
│   ├── operaciones_iol/# Historial de órdenes y operaciones
│   ├── parametros/     # Metadatos manuales de activos (sector, país, etc.)
│   ├── dashboard/      # Panel principal con KPIs y gráficos
│   └── users/          # Autenticación básica
├── portafolio_iol/     # Configuración Celery y tasks programadas
├── config/             # Configuración Django por entorno
├── requirements/       # Dependencias organizadas por entorno
├── scripts/            # Utilidades de setup, testing y P3 features
├── static/             # CSS, JS, imágenes
├── templates/          # Plantillas HTML con componentes reutilizables
└── README_P3.md        # Documentación detallada de Fase P3
```

### Servicios Core (P3)
- **IOLTokenManager**: Gestión persistente de tokens JWT en BD
- **PortfolioSnapshotService**: Generación y sincronización de snapshots diarios
- **AlertsEngine**: Motor de alertas con reglas configurables
- **RebalanceEngine**: Análisis estratégico de rebalanceo
- **TemporalMetricsService**: Cálculos avanzados de retornos y volatilidad

### API REST Endpoints (P3)
```
/api/dashboard/kpis/              # KPIs principales
/api/alerts/active/               # Alertas activas
/api/rebalance/suggestions/       # Sugerencias de rebalanceo
/api/metrics/returns/             # Retornos del portafolio
/api/metrics/volatility/          # Volatilidad histórica
/api/historical/evolution/        # Evolución histórica
```

### Principios de Diseño
- **Clean Architecture**: Separación clara entre dominio, servicios y presentación
- **Single Responsibility**: Una función/clase por responsabilidad
- **DRY (Don't Repeat Yourself)**: Componentes reutilizables
- **Type Hints**: Anotaciones de tipo para mejor mantenibilidad
- **Test-Driven Development**: Cobertura de tests del 85%+
- **Production-Ready**: Configuraciones robustas y validaciones de seguridad

## 🚀 Instalación y Configuración

### Prerrequisitos
- Python 3.12+
- pip
- virtualenv (recomendado)
- Redis (para Celery - automatización P3)
- Cuenta activa en InvertirOnline

### Dependencias P3
```bash
pip install celery[redis] django-celery-beat django-celery-results djangorestframework pandas
```

### Setup Rápido
```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/portafolio-iol.git
cd portafolio-iol

# Ejecutar setup automático
# Linux/Mac
./scripts/setup.sh
# Windows
scripts\setup.bat

# O setup manual:
python -m venv venv
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements/dev.txt
cp .env.example .env
# Editar .env con credenciales IOL y Redis

# Configurar base de datos
python manage.py migrate

# Ejecutar tests P3
python scripts/test_p3_features.py
```

### Configuración de Variables de Entorno (.env)
```bash
# IOL API
IOL_USERNAME=tu_usuario_iol
IOL_PASSWORD=tu_password_iol
IOL_BASE_URL=https://api.invertironline.com

# Celery (Redis)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Django
SECRET_KEY=tu-secret-key-super-segura
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Ejecutar la Plataforma Completa (P3)
```bash
# Terminal 1: Servidor Django
python manage.py runserver

# Terminal 2: Worker de Celery
celery -A portafolio_iol worker --loglevel=info

# Terminal 3: Scheduler de Celery (Beat)
celery -A portafolio_iol beat --loglevel=info
```

### Tareas Programadas P3
- **Sincronización**: Cada 30 minutos desde IOL API
- **Snapshots Diarios**: Generación automática a las 6:00 AM
- **Alertas**: Monitoreo continuo cada hora
- **Métricas**: Cálculo cada 4 horas
- **Rebalanceo**: Análisis estratégico programado

### API REST P3
```bash
# Probar endpoints
curl http://localhost:8000/api/dashboard/kpis/
curl http://localhost:8000/api/alerts/active/
curl http://localhost:8000/api/metrics/returns/?days=30
```

## 🧪 Testing y Validación

### Tests Completos
```bash
# Tests básicos
python manage.py test

# Tests P3 específicos
python scripts/test_p3_features.py

# Cobertura de código
coverage run manage.py test
coverage report
```

### Validación P3
- ✅ Modelos de datos históricos (PortfolioSnapshot, PositionSnapshot, IOLToken)
- ✅ Servicios core (TokenManager, SnapshotService, AlertsEngine, RebalanceEngine, TemporalMetrics)
- ✅ API REST completa con todos los endpoints
- ✅ Tareas Celery programadas y funcionales
- ✅ Sincronización automática con IOL API
- ✅ Tests de integración y validación

## 📚 Documentación

- **README_P3.md**: Documentación completa de Fase P3
- **scripts/test_p3_features.py**: Script de validación de funcionalidades
- **API Endpoints**: Documentación inline en código
- **Modelos**: Comentarios detallados en cada campo

## 🗺️ Roadmap

### P4 - Próximas Funcionalidades
- [ ] **Frontend React/Vue**: Interfaz moderna con componentes reutilizables
- [ ] **Alertas Visuales**: Notificaciones en tiempo real en dashboard
- [ ] **Backtesting**: Validación histórica de estrategias de rebalanceo
- [ ] **Machine Learning**: Predicciones de volatilidad y retornos
- [ ] **Portfolio Optimization**: Algoritmos avanzados de optimización
- [ ] **Multi-Portfolio**: Gestión de múltiples portafolios
- [ ] **Reporting**: Reportes PDF automatizados y exportación de datos

### Mejoras Continuas
- [ ] **Performance**: Optimización de queries y caching con Redis
- [ ] **Monitoring**: Dashboards de estado del sistema y alertas
- [ ] **Security**: Autenticación avanzada y encriptación de datos sensibles
- [ ] **Scalability**: Arquitectura preparada para múltiples usuarios

## 🤝 Contribución

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

## ⚠️ Disclaimer

Este software es una herramienta de análisis y no constituye asesoramiento financiero. Los usuarios deben realizar su propia investigación y asumir la responsabilidad de sus decisiones de inversión.
python manage.py createsuperuser

# Configurar pre-commit hooks
pre-commit install
```

### Variables de Entorno (.env)
```env
# Django Core
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True
DJANGO_SETTINGS_MODULE=config.settings.dev
ALLOWED_HOSTS=localhost,127.0.0.1

# IOL API Credentials
IOL_USERNAME=tu-usuario-iol
IOL_PASSWORD=tu-password-iol
# O usar token directo:
# IOL_ACCESS_TOKEN=tu-jwt-token
IOL_BASE_URL=https://api.invertironline.com

# Database (Production)
DB_NAME=portafolio_iol
DB_USER=tu-usuario-db
DB_PASSWORD=tu-password-db
DB_HOST=localhost
DB_PORT=5432

# Email (Production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-password-email

# Redis (Production)
REDIS_URL=redis://127.0.0.1:6379/1

# Sentry (Optional)
SENTRY_DSN=https://tu-sentry-dsn@sentry.io/project-id
```

## 📋 Uso

### Sincronización de Datos
```bash
# Sincronización completa
python manage.py actualizar_iol

# Solo estado de cuenta
python manage.py actualizar_iol --estado-cuenta

# Solo portafolio
python manage.py actualizar_iol --portafolio

# Con verbose output
python manage.py actualizar_iol -v 2
```

### Servidor de Desarrollo
```bash
python manage.py runserver
# Acceder en http://127.0.0.1:8000
```

### Testing
```bash
# Ejecutar todos los tests
python manage.py test

# Tests con cobertura
pytest --cov=apps --cov-report=html

# Tests específicos
python manage.py test apps.dashboard.tests.test_selectors
```

### Linting y Formateo
```bash
# Verificar código
ruff check .

# Formatear automáticamente
ruff format .

# Verificar tipos (si tienes mypy configurado)
mypy apps/
```

## 📊 Métricas y KPIs

### Bloques Patrimoniales
- **Total IOL**: Patrimonio total (activos + cash)
- **Liquidez Operativa**: Cash + caución + FCI disponibles (25% objetivo)
- **FCI / Cash Management**: Fondos de inversión para liquidez (7.5% objetivo)
- **Portafolio Invertido**: Activos de inversión tradicionales (67.5% objetivo)

### Objetivos Estratégicos por Sector
- **Tecnología**: 17.5% (Apple, Microsoft, etc.)
- **ETF Core**: 22.5% (SPY, QQQ, índices globales)
- **Argentina**: 12.5% (YPF, GGAL, etc.)
- **Bonos**: 12.5% (Soberanos, corporativos)
- **Defensivos**: 12.5% (Consumo, Utilities, Finanzas)

### Señales de Rebalanceo
- **Sobreponderado**: > objetivo + 5%
- **Subponderado**: < objetivo - 3%
- **Sectores sin objetivo**: < 2% del portafolio

### Exposición por Moneda
- **Económica**: Exposición real del activo (CEDEARs = USD)
- **Operativa**: Moneda de cotización (CEDEARs = ARS)

## 🔧 API y Extensibilidad

### Cliente IOL API
```python
from apps.core.services.iol_client import IOLClient

client = IOLClient()
# Autenticación automática
portfolio = client.get_portfolio()
account = client.get_account_status()
```

### Selectors (Lógica de Negocio)
```python
from apps.dashboard.selectors import (
    get_dashboard_kpis,
    get_senales_rebalanceo,
    get_riesgo_portafolio,
    get_analytics_mensual
)

kpis = get_dashboard_kpis()
senales = get_senales_rebalanceo()
riesgo = get_riesgo_portafolio()
analytics = get_analytics_mensual()
```

### Tests de Regresión
Cobertura completa para:
- ✅ Cálculos de KPIs y porcentajes
- ✅ Lógica de rebalanceo estratégico
- ✅ Exposición económica vs operativa
- ✅ Analytics mensual y evolución histórica
- ✅ Concentración por sector/país/tipo
- ✅ Validaciones de riesgo

## 🚀 Deployment

### Producción Checklist
```bash
# Validaciones de producción
python manage.py check --deploy

# Recopilar estáticos
python manage.py collectstatic --noinput

# Backup de datos
python manage.py dumpdata > backup_$(date +%Y%m%d).json

# Configurar variables de entorno de producción
# DEBUG=False
# SECRET_KEY=clave-produccion-segura
# ALLOWED_HOSTS=tu-dominio.com
```

### Docker (Futuro)
```dockerfile
# Dockerfile preparado para contenerización
FROM python:3.12-slim
WORKDIR /app
COPY requirements/prod.txt .
RUN pip install -r prod.txt
COPY . .
RUN python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## 🤝 Contribución

1. Fork el proyecto
2. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -m 'Agrega nueva funcionalidad'`
4. Push a rama: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

### Guías de Contribución
- Seguir PEP 8 y convenciones de Django
- Tests obligatorios para nueva funcionalidad
- Documentación actualizada
- Pre-commit hooks ejecutados

## 📝 Changelog

### v2.0.0 - Dashboard Avanzado
- ✅ **P2.1**: Volatilidad proxy y bases de cálculo mejoradas
- ✅ **P2.2**: Analytics mensual con indicadores de cambio
- ✅ **P2.3**: Chart.js para visualizaciones interactivas
- ✅ **P2.4**: Rebalanceo signals con separación patrimonial/sectorial
- ✅ **P2.5**: Riesgo portfolio con métricas detalladas
- ✅ **P2.6**: Objetivos estratégicos vs umbrales arbitrarios
- ✅ **P2.7**: KPIs en porcentaje para bloques patrimoniales
- ✅ **P2.8**: Exposición económica vs operativa por moneda
- ✅ **P2.9**: Evolución histórica con fallback inteligente
- ✅ **P2.10**: Tests de regresión completos

### v1.0.0 - MVP Inicial
- Sincronización básica con IOL API
- Dashboard simple con KPIs básicos
- Arquitectura modular establecida

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

## 🙏 Agradecimientos

- InvertirOnline por su API robusta
- Comunidad Django por el framework excelente
- Chart.js por las visualizaciones interactivas
- Bootstrap por los componentes UI

---

**Desarrollado con ❤️ para la comunidad de inversores argentinos**
```

## Testing

El proyecto incluye tests automatizados con pytest:

```bash
# Ejecutar todos los tests
pytest

# Ejecutar con cobertura
pytest --cov=apps

# Ejecutar tests específicos
pytest apps/core/tests/test_iol_api_client.py

# Generar reporte HTML de cobertura
pytest --cov=apps --cov-report=html
```

### Cobertura Actual

- ✅ Cliente API IOL (mockeado)
- ✅ Comando actualizar_iol
- ✅ Modelos críticos
- ✅ Selectors del dashboard
- ✅ Vistas principales

## Pipeline de Calidad

### Pre-commit Hooks

- `trailing-whitespace`: Elimina espacios en blanco al final de línea
- `end-of-file-fixer`: Asegura nueva línea al final de archivo
- `ruff`: Linting y formateo automático
- `detect-secrets`: Detecta credenciales hardcodeadas

### CI/CD con GitHub Actions

Jobs automáticos en cada push/PR:

- **Lint**: Ruff linting y formateo
- **Test**: Ejecución de tests con cobertura
- **Django Checks**: Validaciones de configuración Django
- **Build**: Verificación de migraciones

## Estructura del Proyecto

```
portafolio_iol/
├── .github/workflows/ci.yml      # CI/CD pipeline
├── apps/
│   ├── core/
│   │   ├── services/iol_api_client.py    # Cliente API IOL
│   │   ├── services/iol_sync_service.py  # Servicio de sincronización
│   │   ├── management/commands/actualizar_iol.py  # Comando de sync
│   │   └── constants.py                  # Constantes compartidas
│   ├── dashboard/
│   │   ├── selectors.py                  # Lógica de agregación
│   │   └── views.py                      # Vista del dashboard
│   └── [otras apps...]
├── config/settings/
│   ├── base.py                           # Configuración base
│   ├── dev.py                            # Desarrollo
│   └── prod.py                           # Producción
├── requirements/
│   ├── base.txt                          # Dependencias comunes
│   ├── dev.txt                           # Desarrollo + testing
│   └── prod.txt                          # Producción
├── templates/                            # Plantillas HTML
├── static/                               # Archivos estáticos
├── .pre-commit-config.yaml               # Configuración pre-commit
├── pyproject.toml                        # Configuración herramientas
└── pytest.ini                            # Configuración pytest
```

## Roadmap

### MVP (Actual)
- ✅ Autenticación API IOL
- ✅ Sincronización estado de cuenta
- ✅ Sincronización portafolio Argentina
- ✅ Sincronización operaciones
- ✅ Dashboard básico con KPIs
- ✅ Visualización de datos

### Próximas Features
- 🔄 Exportación a Excel
- 🔄 Integración Cocos (criptomonedas)
- 🔄 Integración Binance
- 🔄 Sincronización automática programada
- 🔄 Alertas por concentración/riesgo
- 🔄 Métricas patrimoniales avanzadas
- 🔄 Dashboard de objetivos (casa, auto, etc.)

### Features Futuras
- 📊 Análisis técnico integrado
- 🤖 Recomendaciones automáticas
- 📱 App móvil
- 🔗 Integración con más brokers
- 📈 Reportes automatizados por email

## Contribución

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

### Guías de Contribución

- Seguir PEP 8 y convenciones Django
- Escribir tests para nueva funcionalidad
- Actualizar documentación
- Mantener cobertura > 80%

## Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

## Contacto

Para preguntas o soporte, crear un issue en GitHub o contactar al maintainer.

---

**Nota**: Este proyecto está diseñado para uso personal. No promueve ni facilita trading automatizado o robo-advisory. Toda decisión de inversión es responsabilidad del usuario.