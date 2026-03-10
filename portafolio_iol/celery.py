import os
from celery import Celery

# Establecer el módulo de configuración de Django para el programa 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('portafolio_iol')

# Usar configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas de todas las apps registradas
app.autodiscover_tasks()

app.conf.timezone = 'America/Argentina/Buenos_Aires'