from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.temporal_metrics_service import TemporalMetricsService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
class TestTemporalMetricsService:
    def test_returns_empty_without_snapshots(self):
        service = TemporalMetricsService()
        assert service.get_portfolio_returns(days=30) == {}

    def test_portfolio_returns_with_snapshots(self):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=1),
            total_iol=1000,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=1100,
            liquidez_operativa=220,
            cash_management=110,
            portafolio_invertido=770,
            rendimiento_total=10.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

        service = TemporalMetricsService()
        returns = service.get_portfolio_returns(days=30)

        assert returns["total_period_return"] == 10.0
        assert returns["daily_return"] == 10.0
        assert "max_drawdown" in returns

    def test_portfolio_volatility_with_snapshots(self):
        today = timezone.now().date()
        for offset, value in [(2, 1000), (1, 1100), (0, 1050)]:
            PortfolioSnapshot.objects.create(
                fecha=today - timedelta(days=offset),
                total_iol=value,
                liquidez_operativa=200,
                cash_management=100,
                portafolio_invertido=700,
                rendimiento_total=0.0,
                exposicion_usa=50.0,
                exposicion_argentina=50.0,
            )

        service = TemporalMetricsService()
        volatility = service.get_portfolio_volatility(days=30)

        assert "daily_volatility" in volatility
        assert "annualized_volatility" in volatility
        assert volatility["daily_volatility"] > 0
