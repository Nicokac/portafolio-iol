from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.risk.var_service import VaRService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_var_service_returns_historical_and_parametric_values():
    today = timezone.now().date()
    values = [1000, 980, 1010, 970, 1030, 990]

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

    result = VaRService().calculate_var_set(confidence=0.95, lookback_days=252)

    assert "historical_var_95_1d" in result
    assert "historical_var_95_10d" in result
    assert "parametric_var_95_1d" in result
    assert "parametric_var_95_10d" in result
