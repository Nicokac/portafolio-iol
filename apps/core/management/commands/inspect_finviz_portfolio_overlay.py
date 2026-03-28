from django.core.management.base import BaseCommand

from apps.core.services.finviz.finviz_portfolio_overlay_service import FinvizPortfolioOverlayService


class Command(BaseCommand):
    help = "Resume overlay Finviz del portafolio actual."

    def handle(self, *args, **options):
        payload = FinvizPortfolioOverlayService().build_current_portfolio_overlay()

        self.stdout.write(self.style.MIGRATE_HEADING("[finviz_portfolio_overlay]"))
        self.stdout.write(payload["summary"])
        coverage = payload.get("coverage") or {}
        self.stdout.write(
            "coverage={coverage_pct}% | mapped_assets={mapped_assets}/{portfolio_assets}".format(**coverage)
        )

        weighted = payload.get("weighted_profiles") or {}
        if weighted:
            self.stdout.write(
                "beta={portfolio_beta} | quality={quality_score} | valuation={valuation_score} | "
                "balance={balance_score} | growth={growth_score}".format(**weighted)
            )

        leaders = (payload.get("leaders") or {}).get("highest_weight") or []
        if leaders:
            self.stdout.write("Lideres por peso:")
            for row in leaders:
                self.stdout.write(
                    "- {symbol} | weight={weight_pct}% | score={composite_buy_score}".format(**row)
                )
