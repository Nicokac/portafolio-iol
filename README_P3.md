# Portafolio IOL - Fase P3: Automatización Completa

## Descripción
Fase P3 del proyecto Portafolio IOL implementa una plataforma completamente automatizada con:
- Sincronización automática desde IOL API cada 30 minutos
- Snapshots históricos diarios del portafolio
- Sistema de alertas patrimoniales inteligentes
- Motor de rebalanceo estratégico
- Métricas temporales (retornos, volatilidad histórica)
- API REST interna para integración frontend
- Scheduler con Celery para automatización completa

## Componentes Implementados

### 1. Modelos de Datos Históricos
- **PortfolioSnapshot**: Snapshots diarios del portafolio completo
- **PositionSnapshot**: Detalle histórico de posiciones por activo
- **IOLToken**: Gestión persistente de tokens JWT

### 2. Servicios Core
- **IOLTokenManager**: Gestión automática de autenticación JWT
- **PortfolioSnapshotService**: Generación y sincronización de snapshots
- **AlertsEngine**: Motor de alertas patrimoniales
- **RebalanceEngine**: Motor de rebalanceo inteligente
- **TemporalMetricsService**: Cálculo de métricas temporales con pandas

### 3. API REST Interna
Endpoints disponibles en `/api/`:
- `/api/dashboard/kpis/` - KPIs principales
- `/api/alerts/active/` - Alertas activas
- `/api/rebalance/suggestions/` - Sugerencias de rebalanceo
- `/api/metrics/returns/` - Retornos del portafolio
- `/api/metrics/volatility/` - Volatilidad histórica
- `/api/historical/evolution/` - Evolución histórica

### 4. Automatización con Celery
Tareas programadas:
- Sincronización cada 30 minutos
- Snapshots diarios a las 6:00 AM
- Alertas cada hora
- Métricas temporales cada 4 horas

## Instalación y Configuración

### Dependencias
```bash
pip install celery[redis] django-celery-beat django-celery-results pandas
```

### Variables de Entorno
```bash
# IOL API
IOL_USERNAME=tu_usuario
IOL_PASSWORD=tu_password
IOL_ACCESS_TOKEN=token_opcional

# Celery (Redis como broker)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

## Uso

### Ejecutar Servidor Django
```bash
python manage.py runserver
```

### Ejecutar Worker de Celery
```bash
celery -A portafolio_iol worker --loglevel=info
```

### Ejecutar Scheduler de Celery (en otra terminal)
```bash
celery -A portafolio_iol beat --loglevel=info
```

### Ejecutar Tareas Manualmente
```python
from apps.core.tasks.portfolio_tasks import sync_portfolio_data, generate_daily_snapshot

# Sincronizar datos manualmente
result = sync_portfolio_data.delay()
print(result.get())

# Generar snapshot manualmente
result = generate_daily_snapshot.delay()
print(result.get())
```

## API Endpoints

### Dashboard
```bash
# KPIs principales
GET /api/dashboard/kpis/

# Concentración por país
GET /api/dashboard/concentracion-pais/

# Concentración por sector
GET /api/dashboard/concentracion-sector/

# Señales de rebalanceo
GET /api/dashboard/senales-rebalanceo/
```

### Alertas
```bash
# Todas las alertas activas
GET /api/alerts/active/

# Alertas por severidad
GET /api/alerts/by-severity/?severity=warning
```

### Rebalanceo
```bash
# Todas las sugerencias
GET /api/rebalance/suggestions/

# Acciones críticas
GET /api/rebalance/critical/

# Oportunidades
GET /api/rebalance/opportunity/
```

### Métricas Temporales
```bash
# Retornos del portafolio
GET /api/metrics/returns/?days=30

# Volatilidad
GET /api/metrics/volatility/?days=30

# Métricas completas
GET /api/metrics/performance/?days=90

# Comparación histórica
GET /api/metrics/historical-comparison/?periods=7,30,90,180
```

### Datos Históricos
```bash
# Evolución del portafolio
GET /api/historical/evolution/?days=90

# Resumen histórico
GET /api/historical/summary/
```

## Testing

### Ejecutar Tests
```bash
python manage.py test apps.core.tests
python manage.py test apps.api.tests
```

### Tests de Integración
Los tests incluyen:
- Sincronización con IOL API
- Generación de snapshots
- Cálculo de métricas temporales
- Generación de alertas
- Lógica de rebalanceo

## Monitoreo

### Logs
Los servicios generan logs detallados en diferentes niveles:
- INFO: Operaciones normales
- WARNING: Alertas y situaciones de atención
- ERROR: Errores que requieren intervención

### Health Checks
- Verificar estado de Celery workers
- Monitorear sincronización con IOL API
- Validar generación de snapshots diarios

## Próximos Pasos

1. **Frontend Integration**: Conectar dashboard con API REST
2. **Alertas Visuales**: Implementar notificaciones en tiempo real
3. **Cache**: Optimizar performance con Redis caching
4. **Monitoring**: Dashboard de estado del sistema
5. **Backtesting**: Validación histórica de estrategias de rebalanceo

## Arquitectura

```
Portafolio IOL P3/
├── apps/
│   ├── core/
│   │   ├── models.py              # IOLToken
│   │   ├── services/
│   │   │   ├── iol_api_client.py
│   │   │   ├── token_manager.py
│   │   │   ├── portfolio_snapshot_service.py
│   │   │   ├── alerts_engine.py
│   │   │   ├── rebalance_engine.py
│   │   │   └── temporal_metrics_service.py
│   │   └── tasks/
│   │       └── portfolio_tasks.py
│   ├── portafolio_iol/
│   │   └── models.py             # PortfolioSnapshot, PositionSnapshot
│   └── api/
│       ├── views.py
│       └── urls.py
├── portafolio_iol/
│   └── celery.py
└── config/
    └── settings/
        └── base.py               # Configuración Celery
```