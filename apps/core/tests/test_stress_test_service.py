import pytest
from django.utils import timezone

from apps.core.services.risk.stress_test_service import StressTestService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


@pytest.mark.django_db
def test_stress_test_service_returns_scenarios():
    fecha = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnología",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="AL30",
        sector="Soberano",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )

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
        valorizado=1000,
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
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="TitulosPublicos",
        moneda="peso_Argentino",
    )
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=fecha,
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda="ARS",
        disponible=500,
        comprometido=0,
        saldo=500,
        titulos_valorizados=0,
        total=500,
        estado="activa",
    )

    result = StressTestService().run_all()

    assert "usd_plus_20" in result
    assert "usa_rates_up_200bps" in result
    assert "equity_drop_15" in result
    assert "argentina_crisis" in result
    assert "impact_portfolio_pct" in result["argentina_crisis"]
