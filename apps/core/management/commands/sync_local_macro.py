from django.core.management.base import BaseCommand

from apps.core.services.local_macro_series_service import LocalMacroSeriesService


class Command(BaseCommand):
    help = "Sincroniza series macro locales oficiales para analitica del portafolio"

    def handle(self, *args, **options):
        self.stdout.write("Sincronizando series macro locales...")
        result = LocalMacroSeriesService().sync_all()
        for series_key, payload in result.items():
            self.stdout.write(
                f"  {series_key}: created={payload['created']} updated={payload['updated']} rows={payload['rows_received']}"
            )
        self.stdout.write(self.style.SUCCESS("Sincronizacion macro local completada"))
