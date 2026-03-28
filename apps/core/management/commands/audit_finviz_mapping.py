from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_mapping_service import FinvizMappingService


class Command(BaseCommand):
    help = "Audita el mapping entre simbolos internos y tickers compatibles con Finviz."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=("metadata", "portfolio", "all"),
            default="all",
            help="Universo a auditar: metadata, portfolio actual o ambos.",
        )

    def handle(self, *args, **options):
        scope = options["scope"]
        service = FinvizMappingService()

        summaries = []
        if scope in {"metadata", "all"}:
            summaries.append(service.build_metadata_universe_summary())
        if scope in {"portfolio", "all"}:
            summaries.append(service.build_current_portfolio_summary())

        for summary in summaries:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"[{summary['scope']}]"))
            self.stdout.write(
                "total={total} | mapped={mapped} | out_of_scope={out_of_scope} | "
                "missing_metadata={missing_metadata} | missing_symbol={missing_symbol}".format(**summary)
            )

            problematic = [
                row for row in summary["rows"]
                if row["status"] != "mapped"
            ]
            if not problematic:
                self.stdout.write(self.style.SUCCESS("Sin problemas de mapping en este scope."))
                continue

            self.stdout.write(self.style.WARNING("Rows no mapeadas o fuera de alcance:"))
            for row in problematic[:20]:
                self.stdout.write(
                    "- {internal_symbol} | status={status} | reason={reason} | tipo={tipo_patrimonial}".format(**row)
                )
