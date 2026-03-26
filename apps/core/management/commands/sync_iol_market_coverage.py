from django.core.management.base import BaseCommand

from apps.core.services.iol_market_coverage_service import IOLMarketCoverageService


class Command(BaseCommand):
    help = "Sincroniza el resumen batch de cobertura y freshness de cotizaciones IOL por instrumento."

    def add_arguments(self, parser):
        parser.add_argument(
            "--pais",
            dest="paises",
            action="append",
            help="Pais a sincronizar. Se puede repetir.",
        )
        parser.add_argument(
            "--instrumento",
            dest="instrumentos",
            action="append",
            help="Instrumento a sincronizar. Se puede repetir.",
        )

    def handle(self, *args, **options):
        result = IOLMarketCoverageService().sync_coverage(
            paises=options.get("paises"),
            instrumentos=options.get("instrumentos"),
        )

        if result.get("success"):
            self.stdout.write(
                self.style.SUCCESS(
                    "C2 coverage sync OK | "
                    f"countries={result['countries_processed']} "
                    f"instruments={result['instruments_processed']} "
                    f"rows={result['rows_received']} "
                    f"created={result['created']} updated={result['updated']}"
                )
            )
            return

        raise SystemExit(
            "C2 coverage sync failed | "
            f"countries={result['countries_processed']} "
            f"instruments={result['instruments_processed']} "
            f"error={result.get('error') or 'unknown'}"
        )
