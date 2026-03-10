from django.core.management.base import BaseCommand

from apps.core.services.iol_sync_service import IOLSyncService


class Command(BaseCommand):
    help = 'Sincroniza datos desde la API de InvertirOnline'

    def add_arguments(self, parser):
        parser.add_argument(
            '--estado-cuenta',
            action='store_true',
            help='Sincroniza solo estado de cuenta.',
        )
        parser.add_argument(
            '--portafolio',
            action='store_true',
            help='Sincroniza solo portafolio de Argentina.',
        )
        parser.add_argument(
            '--operaciones',
            action='store_true',
            help='Sincroniza solo operaciones.',
        )

    def handle(self, *args, **options):
        self.stdout.write('Iniciando sincronización con IOL...')

        service = IOLSyncService()
        sync_specific = any(
            [
                options['estado_cuenta'],
                options['portafolio'],
                options['operaciones'],
            ]
        )

        if sync_specific:
            results = {}
            if options['estado_cuenta']:
                results['estado_cuenta'] = service.sync_estado_cuenta()
            if options['portafolio']:
                results['portafolio_argentina'] = service.sync_portafolio('argentina')
            if options['operaciones']:
                results['operaciones'] = service.sync_operaciones()
        else:
            results = service.sync_all()

        self.stdout.write('Resultados de sincronización:')
        for key, success in results.items():
            status = 'ÉXITO' if success else 'FALLÓ'
            self.stdout.write(f'  {key}: {status}')

        if results and all(results.values()):
            self.stdout.write(
                self.style.SUCCESS('Sincronización completada exitosamente')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Algunos procesos de sincronización fallaron')
            )
