from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_opportunity_watchlist_service import FinvizOpportunityWatchlistService


class Command(BaseCommand):
    help = "Resume el radar de oportunidades Finviz."

    def handle(self, *args, **options):
        payload = FinvizOpportunityWatchlistService().build_watchlist()

        self.stdout.write(self.style.MIGRATE_HEADING("[finviz_opportunity_watchlist]"))
        self.stdout.write(payload["summary"])
        coverage = payload.get("coverage") or {}
        self.stdout.write(
            "shortlist={shortlist_count} | held={current_holdings_considered} | external={external_candidates} | "
            "reinforce={reinforce_candidates}".format(**coverage)
        )

        external = payload.get("external_candidates") or []
        if external:
            self.stdout.write("Ideas externas:")
            for row in external[:3]:
                self.stdout.write(
                    "- {internal_symbol} | score={composite_buy_score} | consenso={analyst_signal_label_text}".format(
                        **row
                    )
                )
