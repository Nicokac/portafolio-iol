from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_signal_overlay_service import FinvizSignalOverlayService


class Command(BaseCommand):
    help = "Sincroniza ratings, news e insiders Finviz para el universo mapeable."

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
        self.stdout.write(f"Sincronizando overlays secundarios Finviz (scope={scope})...")
        result = FinvizSignalOverlayService().sync_signals(scope=scope, symbols=symbols or None)
        self.stdout.write(
            self.style.SUCCESS(
                "Overlays Finviz sincronizados: "
                f"mapped={result['mapped_assets']} "
                f"created={result['created']} "
                f"updated={result['updated']} "
                f"ok={result['ok']} "
                f"errors={result['errors']} "
                f"captured_date={result['captured_date']}"
            )
        )
