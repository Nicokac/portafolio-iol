from datetime import timedelta

import pytest
from unittest.mock import patch
from django.utils import timezone

from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_volatility_service_returns_annualized_volatility():
    today = timezone.now().date()
    values = [1000, 1050, 1020, 1100, 1080]

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


@pytest.mark.django_db
@patch("apps.dashboard.selectors.get_evolucion_historica")
def test_volatility_service_fallbacks_to_evolution(mock_evolution):
    mock_evolution.return_value = {
        "tiene_datos": True,
        "fechas": ["2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"],
        "total_iol": [1000, 1100, 1210, 1180, 1250],
        "liquidez_operativa": [200, 210, 220, 225, 230],
        "portafolio_invertido": [700, 780, 860, 840, 900],
        "cash_management": [100, 110, 130, 115, 120],
    }

    result = VolatilityService().calculate_volatility(days=30)

    assert result["fallback_source"] == "evolucion_historica"
    assert result["annualized_volatility"] > 0


@pytest.mark.django_db
@patch("apps.dashboard.selectors.get_evolucion_historica")
def test_volatility_service_returns_warning_when_history_is_insufficient(mock_evolution):
    mock_evolution.return_value = {"tiene_datos": False}

    result = VolatilityService().calculate_volatility(days=30)

    assert result["warning"] == "insufficient_history"
    assert result["required_min_observations"] == VolatilityService.MIN_OBSERVATIONS


@pytest.mark.django_db
@patch("apps.dashboard.selectors.get_evolucion_historica")
def test_volatility_service_returns_warning_when_fallback_also_lacks_points(mock_evolution):
    mock_evolution.return_value = {
        "tiene_datos": True,
        "fechas": ["2026-03-10", "2026-03-11"],
        "total_iol": [1000, 1100],
    }

    result = VolatilityService().calculate_volatility(days=30)

    assert result["warning"] == "insufficient_history"


def test_build_volatility_result_without_downside_sortino():
    import pandas as pd

    data = pd.DataFrame(
        {"total_iol": [100, 105, 110, 116, 120]},
        index=pd.to_datetime(
            ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"]
        ),
    )

    result = VolatilityService()._build_volatility_result(data)

    assert "sharpe_ratio" in result
    assert "sortino_ratio" not in result


@pytest.mark.django_db
@patch("apps.dashboard.selectors.get_evolucion_historica", side_effect=RuntimeError("boom"))
def test_volatility_service_handles_fallback_exception(mock_evolution):
    result = VolatilityService().calculate_volatility(days=30)

    assert result["warning"] == "insufficient_history"
