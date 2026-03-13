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
            if payload.get("success", True):
                self.stdout.write(
                    f"  {benchmark_key}: created={payload['created']} updated={payload['updated']} rows={payload['rows_received']}"
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {benchmark_key}: error={payload.get('error', 'unknown')} rows=0"
                    )
                )

        if all(payload.get("success", True) for payload in result.values()):
            self.stdout.write(self.style.SUCCESS("Sincronizacion de benchmarks completada"))
        else:
            self.stdout.write(self.style.WARNING("Sincronizacion de benchmarks completada con fallos parciales"))
