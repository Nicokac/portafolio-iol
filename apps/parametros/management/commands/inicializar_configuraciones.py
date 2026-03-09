from django.core.management.base import BaseCommand
from apps.parametros.models import ConfiguracionDashboard


class Command(BaseCommand):
    help = 'Inicializa configuraciones por defecto del dashboard'

    def handle(self, *args, **options):
        # Configuraciones por defecto
        defaults = [
            {
                'clave': 'contribucion_mensual',
                'valor': '50000',
                'descripcion': 'Contribución mensual objetivo en pesos argentinos'
            },
            {
                'clave': 'moneda_base',
                'valor': 'ARS',
                'descripcion': 'Moneda base del portafolio'
            }
        ]

        for config in defaults:
            ConfiguracionDashboard.objects.get_or_create(
                clave=config['clave'],
                defaults={
                    'valor': config['valor'],
                    'descripcion': config['descripcion']
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f'Configuración "{config["clave"]}" inicializada')
            )