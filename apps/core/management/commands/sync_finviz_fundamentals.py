from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_fundamentals_service import FinvizFundamentalsService


class Command(BaseCommand):
    help = "Sincroniza snapshots diarios de fundamentals Finviz para el universo mapeable."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=("metadata", "portfolio"),
            default="metadata",
            help="Universo a sincronizar: metadata completa o portfolio actual.",
        )
        parser.add_argument(
            "--symbols",
            default="",
            help="Lista opcional de simbolos internos separados por coma.",
        )

    def handle(self, *args, **options):
        symbols = [
            symbol.strip().upper()
            for symbol in str(options["symbols"]).split(",")
            if symbol.strip()
        ]
        scope = options["scope"]

        self.stdout.write(f"Sincronizando fundamentals Finviz (scope={scope})...")
        result = FinvizFundamentalsService().sync_fundamentals(scope=scope, symbols=symbols or None)

        self.stdout.write(
            self.style.SUCCESS(
                "Fundamentals Finviz sincronizados: "
                f"mapped={result['mapped_assets']} "
                f"created={result['created']} "
                f"updated={result['updated']} "
                f"ok={result['ok']} "
                f"errors={result['errors']} "
                f"captured_date={result['captured_date']}"
            )
        )
