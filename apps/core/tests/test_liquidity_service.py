import pytest
from django.utils import timezone

from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_liquidity_service_returns_score_and_days():
    fecha = timezone.now()

    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
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
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo="AL30",
        descripcion="Bono",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=900,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="TitulosPublicos",
        moneda="peso_Argentino",
    )

    result = LiquidityService().analyze_portfolio_liquidity()

    assert "portfolio_liquidity_score" in result
    assert "days_to_liquidate" in result
    assert "instruments" in result
    assert result["portfolio_liquidity_score"] > 0
    assert result["days_to_liquidate"] > 0
