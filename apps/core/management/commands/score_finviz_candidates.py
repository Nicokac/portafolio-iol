from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_scoring_service import FinvizScoringService


class Command(BaseCommand):
    help = "Construye shortlist de compra Finviz a partir del snapshot diario mas reciente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbols",
            default="",
            help="Lista opcional de simbolos internos separados por coma para comparar.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Cantidad maxima de items a mostrar.",
        )

    def handle(self, *args, **options):
        symbols = [
            symbol.strip().upper()
            for symbol in str(options["symbols"]).split(",")
            if symbol.strip()
        ]
        limit = max(int(options.get("limit") or 10), 1)
        service = FinvizScoringService()

        if symbols:
            payload = service.compare_candidates(symbols)
            self.stdout.write(self.style.MIGRATE_HEADING("[finviz_compare]"))
            self.stdout.write(payload["summary"])
            for item in payload.get("items", []):
                self.stdout.write(
                    "- {internal_symbol} | score={composite_buy_score} | quality={quality_score} | "
                    "valuation={valuation_score} | label={label}".format(
                        internal_symbol=item["internal_symbol"],
                        composite_buy_score=item.get("composite_buy_score"),
                        quality_score=item.get("quality_score"),
                        valuation_score=item.get("valuation_score"),
                        label=(item.get("interpretation") or {}).get("label"),
                    )
                )
            return

        payload = service.build_latest_shortlist(limit=limit)
        self.stdout.write(self.style.MIGRATE_HEADING("[finviz_shortlist]"))
        self.stdout.write(
            f"captured_date={payload.get('captured_date')} | count={payload.get('count', 0)}"
        )
        for item in payload.get("items", []):
            self.stdout.write(
                "- #{rank} {internal_symbol} | score={composite_buy_score} | "
                "{label} | main_reason={main_reason}".format(
                    rank=item["rank"],
                    internal_symbol=item["internal_symbol"],
                    composite_buy_score=item.get("composite_buy_score"),
                    label=(item.get("interpretation") or {}).get("label"),
                    main_reason=item.get("main_reason"),
                )
            )
