from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.performance.twr_service import TWRService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_twr_service_calculates_time_weighted_return():
    today = timezone.now().date()
    values = [1000, 1100, 1210]

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

    result = TWRService().calculate_twr(days=30)

    assert "twr_total_return" in result
    assert "twr_annualized_return" in result
    assert result["twr_total_return"] > 0
