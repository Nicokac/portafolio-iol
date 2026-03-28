from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_inspect_finviz_portfolio_overlay_command_prints_summary(monkeypatch):
    class DummyService:
        def build_current_portfolio_overlay(self):
            return {
                "summary": "Cobertura Finviz 82.0% del portafolio invertido. Beta ponderada 1.08, quality 76.0, valuation 68.0.",
                "coverage": {
                    "coverage_pct": 82.0,
                    "mapped_assets": 4,
                    "portfolio_assets": 5,
                },
                "weighted_profiles": {
                    "portfolio_beta": 1.08,
                    "quality_score": 76.0,
                    "valuation_score": 68.0,
                    "balance_score": 70.0,
                    "growth_score": 74.0,
                },
                "leaders": {
                    "highest_weight": [
                        {"symbol": "MSFT", "weight_pct": 22.5, "composite_buy_score": 81.0}
                    ]
                },
            }

    monkeypatch.setattr(
        "apps.core.management.commands.inspect_finviz_portfolio_overlay.FinvizPortfolioOverlayService",
        lambda: DummyService(),
    )
    stdout = StringIO()

    call_command("inspect_finviz_portfolio_overlay", stdout=stdout)

    output = stdout.getvalue()
    assert "[finviz_portfolio_overlay]" in output
    assert "coverage=82.0%" in output
    assert "MSFT" in output
