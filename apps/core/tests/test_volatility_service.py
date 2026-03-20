from datetime import timedelta

import pytest
from unittest.mock import patch
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


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
def test_volatility_service_returns_warning_when_history_is_insufficient(mock_evolution):
    mock_evolution.return_value = {
        "tiene_datos": True,
        "fechas": ["2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"],
        "total_iol": [1000, 1100, 1210, 1180, 1250],
    }

    result = VolatilityService().calculate_volatility(days=30)

    assert result["warning"] == "insufficient_history"
    assert result["required_min_observations"] == VolatilityService.MIN_OBSERVATIONS


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
def test_volatility_service_filters_extreme_daily_jumps():
    today = timezone.now().date()
    values = [1000, 1020, 5000, 1030, 1040, 1050]

    for offset, value in enumerate(values[::-1]):
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=offset),
            total_iol=value,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=max(value - 300, 0),
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

    result = VolatilityService().calculate_volatility(days=30)

    assert "annualized_volatility" in result
    assert result["annualized_volatility"] < 500
    assert result["outlier_returns_filtered"] >= 1


@pytest.mark.django_db
def test_volatility_service_uses_iol_historical_proxy_when_snapshot_history_is_insufficient():
    today = timezone.now().date()
    extraction = timezone.make_aware(timezone.datetime(2026, 3, 20, 10, 0, 0))

    PortfolioSnapshot.objects.create(
        fecha=today,
        total_iol=1000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=extraction,
        pais_consulta="argentina",
        simbolo="GGAL",
        descripcion="GGAL",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        plazo="T0",
        moneda="ARS",
    )
    for offset, close in enumerate([100, 101, 103, 102, 104, 106]):
        IOLHistoricalPriceSnapshot.objects.create(
            simbolo="GGAL",
            mercado="BCBA",
            source="iol",
            fecha=today - timedelta(days=5 - offset),
            close=close,
        )

    result = VolatilityService().calculate_volatility(days=30)

    assert result["fallback_source"] == "iol_historical_prices_proxy"
    assert result["returns_basis"] == "current_weights_proxy"
    assert "annualized_volatility" in result
    assert result["proxy_observations"] >= 5
    assert result["proxy_coverage_pct"] == 100.0
    assert result["proxy_total_positions"] == 1
    assert result["proxy_covered_positions"] == 1


@pytest.mark.django_db
def test_volatility_service_reports_partial_iol_proxy_coverage():
    today = timezone.now().date()
    extraction = timezone.make_aware(timezone.datetime(2026, 3, 20, 10, 0, 0))

    PortfolioSnapshot.objects.create(
        fecha=today,
        total_iol=1000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=extraction,
        pais_consulta="argentina",
        simbolo="GGAL",
        descripcion="GGAL",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=800,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        plazo="T0",
        moneda="ARS",
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=extraction,
        pais_consulta="argentina",
        simbolo="PAMP",
        descripcion="PAMP",
        cantidad=5,
        comprometido=0,
        disponible_inmediato=5,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=40,
        ppc=35,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=200,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        plazo="T0",
        moneda="ARS",
    )
    for offset, close in enumerate([100, 101, 103, 102, 104, 106]):
        IOLHistoricalPriceSnapshot.objects.create(
            simbolo="GGAL",
            mercado="BCBA",
            source="iol",
            fecha=today - timedelta(days=5 - offset),
            close=close,
        )

    result = VolatilityService().calculate_volatility(days=30)

    assert result["fallback_source"] == "iol_historical_prices_proxy"
    assert result["proxy_total_positions"] == 2
    assert result["proxy_covered_positions"] == 1
    assert result["proxy_coverage_pct"] == 80.0
