from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_volatility_service_returns_annualized_volatility():
    today = timezone.now().date()
    values = [1000, 1050, 1020, 1100]

    for offset, value in enumerate(values[::-1]):
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

    result = VolatilityService().calculate_volatility(days=30)

    assert "daily_volatility" in result
    assert "annualized_volatility" in result
    assert result["annualized_volatility"] > 0
