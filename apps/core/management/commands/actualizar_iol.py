from django.core.management.base import BaseCommand

from apps.core.services.iol_sync_service import IOLSyncService


class Command(BaseCommand):
    help = 'Sincroniza datos desde la API de InvertirOnline'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando sincronización con IOL...')

        service = IOLSyncService()
        results = service.sync_all()

        self.stdout.write('Resultados de sincronización:')
        for key, success in results.items():
            status = 'ÉXITO' if success else 'FALLÓ'
            self.stdout.write(f'  {key}: {status}')

        if all(results.values()):
            self.stdout.write(
                self.style.SUCCESS('Sincronización completada exitosamente')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Algunos procesos de sincronización fallaron')
            )