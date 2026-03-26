from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.risk.cvar_service import CVaRService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


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


@pytest.mark.django_db
def test_cvar_service_uses_iol_proxy_fallback_when_snapshot_history_is_insufficient():
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

    result = CVaRService().calculate_cvar_set(confidence=0.95, lookback_days=252)

    assert result["fallback_source"] == "iol_historical_prices_proxy"
    assert "historical_cvar_95_1d" in result
    assert "historical_cvar_95_10d" in result


def test_cvar_service_sanitizes_non_finite_returns_before_percentile(monkeypatch):
    service = CVaRService()
    monkeypatch.setattr(
        service,
        "_get_returns",
        lambda days=252: service._sanitize_returns(
            __import__("pandas").Series([0.01, float("inf"), float("nan"), -0.02])
        ),
    )

    result = service.historical_cvar(confidence=0.95, lookback_days=252)

    assert result is not None
