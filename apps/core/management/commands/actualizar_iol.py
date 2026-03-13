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
            self._print_failure_diagnostics(service, results)
            self.stdout.write(
                self.style.ERROR('Algunos procesos de sincronización fallaron')
            )

    def _print_failure_diagnostics(self, service, results):
        failed_keys = [key for key, ok in results.items() if not ok]
        if not failed_keys:
            return

        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Diagnostico rapido de fallas:'))

        diagnostics = getattr(service, 'last_diagnostics', {}) or {}
        for key in failed_keys:
            detail = diagnostics.get(key) or {}
            self.stdout.write(f'  - {key}:')
            if not detail:
                self.stdout.write('      sin detalle tecnico disponible')
                continue

            self.stdout.write(f"      operacion: {detail.get('operation', 'n/a')}")
            self.stdout.write(f"      tipo_error: {detail.get('error_type', 'n/a')}")
            self.stdout.write(f"      status_code: {detail.get('status_code', 'n/a')}")
            self.stdout.write(f"      mensaje: {detail.get('message', 'n/a')}")

            auth = detail.get('auth_context') or {}
            self.stdout.write(
                "      auth_context: "
                f"has_username={auth.get('has_username')} "
                f"has_password={auth.get('has_password')} "
                f"has_saved_token={auth.get('has_saved_token')} "
                f"token_expired={auth.get('token_expired')} "
                f"has_refresh_token={auth.get('has_refresh_token')}"
            )

        self.stdout.write('')
        self.stdout.write('Checklist sugerido:')
        self.stdout.write('  1) Verifica IOL_USERNAME e IOL_PASSWORD en tu .env')
        self.stdout.write('  2) Si cambiaste credenciales, elimina tokens guardados y reintenta')
        self.stdout.write('  3) Revisa IOL_BASE_URL (debe ser https://api.invertironline.com)')
