# Esto asegura que la aplicación se inicie cuando se importe Django
from .celery import app as celery_app

__all__ = ('celery_app',)