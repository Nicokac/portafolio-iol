from django.core.management.base import BaseCommand

from apps.core.services.benchmark_series_service import BenchmarkSeriesService


class Command(BaseCommand):
    help = "Sincroniza benchmarks historicos externos configurados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--outputsize",
            default="compact",
            choices=["compact", "full"],
            help="Tamano de serie solicitado al proveedor externo.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Sincronizando benchmarks historicos...")
        result = BenchmarkSeriesService().sync_all(outputsize=options["outputsize"])
        for benchmark_key, payload in result.items():
            self.stdout.write(
                f"  {benchmark_key}: created={payload['created']} updated={payload['updated']} rows={payload['rows_received']}"
            )
        self.stdout.write(self.style.SUCCESS("Sincronizacion de benchmarks completada"))
