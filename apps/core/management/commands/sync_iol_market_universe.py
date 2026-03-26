from django.core.management.base import BaseCommand

from apps.core.services.iol_market_universe_service import IOLMarketUniverseService


class Command(BaseCommand):
    help = "Sincroniza el catalogo diario de instrumentos y paneles de cotizacion desde IOL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pais",
            action="append",
            dest="paises",
            help="Pais a sincronizar. Puede repetirse. Default: argentina",
        )

    def handle(self, *args, **options):
        paises = options.get("paises") or None
        self.stdout.write("Sincronizando universo de instrumentos IOL...")
        result = IOLMarketUniverseService().sync_universe(paises=paises)

        if result.get("success"):
            self.stdout.write(
                self.style.SUCCESS(
                    "Universo IOL sincronizado: "
                    f"created={result.get('created', 0)} "
                    f"updated={result.get('updated', 0)} "
                    f"rows={result.get('rows_received', 0)} "
                    f"countries={result.get('countries_processed', 0)} "
                    f"captured_date={result.get('captured_date')}"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Universo IOL con fallo: "
                f"rows={result.get('rows_received', 0)} "
                f"countries={result.get('countries_processed', 0)} "
                f"error={result.get('error', 'unknown')}"
            )
        )
