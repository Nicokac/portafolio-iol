from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.risk.cvar_service import CVaRService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_cvar_service_returns_expected_shortfall_values():
    today = timezone.now().date()
    values = [1000, 920, 930, 940, 960, 980, 1000]

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

    result = CVaRService().calculate_cvar_set(confidence=0.95, lookback_days=252)

    assert "historical_cvar_95_1d" in result
    assert "historical_cvar_95_10d" in result
