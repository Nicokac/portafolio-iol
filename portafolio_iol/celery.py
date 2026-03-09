import os
from celery import Celery
from celery.schedules import crontab

# Establecer el módulo de configuración de Django para el programa 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('portafolio_iol')

# Usar configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas de todas las apps registradas
app.autodiscover_tasks()

# Configuración de tareas programadas
app.conf.beat_schedule = {
    # Sincronización automática cada 30 minutos
    'sync-portfolio-every-30-minutes': {
        'task': 'apps.core.tasks.sync_portfolio_data',
        'schedule': crontab(minute='*/30'),
    },
    # Generar snapshot diario a las 6:00 AM
    'generate-daily-snapshot': {
        'task': 'apps.core.tasks.generate_daily_snapshot',
        'schedule': crontab(hour=6, minute=0),
    },
    # Generar alertas cada hora
    'generate-alerts-hourly': {
        'task': 'apps.core.tasks.generate_alerts',
        'schedule': crontab(minute=0),
    },
    # Calcular métricas temporales cada 4 horas
    'calculate-temporal-metrics': {
        'task': 'apps.core.tasks.calculate_temporal_metrics',
        'schedule': crontab(minute=0, hour='*/4'),
    },
}

app.conf.timezone = 'America/Argentina/Buenos_Aires'