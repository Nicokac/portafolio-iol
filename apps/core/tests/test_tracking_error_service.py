from datetime import timedelta
from unittest.mock import Mock

import pytest
import pandas as pd
from django.utils import timezone

from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


@pytest.mark.django_db
def test_tracking_error_service_returns_tracking_and_information_ratio():
    now = timezone.now()
    today = now.date()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnología",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="AL30",
        sector="Bonos AR",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )

    for offset, total in enumerate([1000, 1030, 1010, 1060][::-1]):
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=offset),
            total_iol=total,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo="AAPL",
        descripcion="Apple",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1200,
        pais_titulo="USA",
        mercado="NASDAQ",
        tipo="CEDEARS",
        moneda="dolar_Estadounidense",
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo="AL30",
        descripcion="Bono AR",
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
        tipo="TitulosPublicos",
        moneda="peso_Argentino",
    )
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=now,
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda="ARS",
        disponible=300,
        comprometido=0,
        saldo=300,
        titulos_valorizados=0,
        total=300,
        estado="activa",
    )

    result = TrackingErrorService().calculate(days=90)

    assert "tracking_error_annualized" in result
    assert "portfolio_return_period" in result
    assert "benchmark_return_period" in result
    assert "excess_return_period" in result


@pytest.mark.django_db
def test_tracking_error_service_returns_warning_for_insufficient_history():
    now = timezone.now()
    today = now.date()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="TecnologÃ­a",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
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
        total_iol=980,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=680,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo="AAPL",
        descripcion="Apple",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1200,
        pais_titulo="USA",
        mercado="NASDAQ",
        tipo="CEDEARS",
        moneda="dolar_Estadounidense",
    )
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=now,
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda="ARS",
        disponible=300,
        comprometido=0,
        saldo=300,
        titulos_valorizados=0,
        total=300,
        estado="activa",
    )

    result = TrackingErrorService().calculate(days=365)

    assert result["warning"] == "insufficient_history"
    assert result["observations"] == 1
    assert "tracking_error_annualized" not in result


@pytest.mark.django_db
def test_tracking_error_service_uses_historical_benchmark_when_available():
    now = timezone.now()
    today = now.date()

    for offset, total in enumerate([1000, 1010, 1030, 1020][::-1]):
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=offset),
            total_iol=total,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

    benchmark_service = Mock()
    benchmark_service.build_daily_returns.side_effect = lambda key, index: (
        pd.Series([0.01, 0.015, -0.005], index=index, dtype=float)
        if key == "cedear_usa"
        else pd.Series(dtype=float)
    )

    result = TrackingErrorService(benchmark_service=benchmark_service).calculate(days=90)

    assert "benchmark_return_period" in result
    assert benchmark_service.build_daily_returns.called
