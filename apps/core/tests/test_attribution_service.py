from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.performance.attribution_service import AttributionService
from apps.operaciones_iol.models import OperacionIOL
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


def _make_asset_snapshot(fecha, simbolo, valorizado):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo=simbolo,
        descripcion=f"Activo {simbolo}",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        moneda="peso_Argentino",
    )


@pytest.mark.django_db
def test_attribution_service_asset_and_bucket_attribution():
    now = timezone.now()
    day1 = now - timedelta(days=1)
    day2 = now

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

    _make_asset_snapshot(day1, "AAPL", 1000)
    _make_asset_snapshot(day1, "AL30", 1000)
    _make_asset_snapshot(day2, "AAPL", 1200)
    _make_asset_snapshot(day2, "AL30", 900)

    PortfolioSnapshot.objects.create(
        fecha=day1.date(),
        total_iol=2000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=1700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=day2.date(),
        total_iol=2100,
        liquidez_operativa=220,
        cash_management=100,
        portafolio_invertido=1780,
        rendimiento_total=5.0,
        exposicion_usa=57.0,
        exposicion_argentina=43.0,
    )

    result = AttributionService().calculate_attribution(days=30)

    assert "by_asset" in result
    assert "top_contributors" in result
    assert "bottom_contributors" in result
    assert "by_sector" in result
    assert "by_country" in result
    assert "by_patrimonial_type" in result
    assert "flows" in result
    assert "Tecnología" in result["by_sector"]
    assert "Bonos AR" in result["by_sector"]


@pytest.mark.django_db
def test_attribution_service_flow_split():
    now = timezone.now()
    day1 = now - timedelta(days=1)
    day2 = now

    _make_asset_snapshot(day1, "AAPL", 1000)
    _make_asset_snapshot(day2, "AAPL", 1100)

    PortfolioSnapshot.objects.create(
        fecha=day1.date(),
        total_iol=1000,
        liquidez_operativa=100,
        cash_management=50,
        portafolio_invertido=850,
        rendimiento_total=0.0,
        exposicion_usa=60.0,
        exposicion_argentina=40.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=day2.date(),
        total_iol=1150,
        liquidez_operativa=100,
        cash_management=50,
        portafolio_invertido=1000,
        rendimiento_total=15.0,
        exposicion_usa=60.0,
        exposicion_argentina=40.0,
    )

    OperacionIOL.objects.create(
        numero="OP-ATTR-1",
        fecha_orden=day2,
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="AAPL",
        cantidad=1,
        monto=100,
        modalidad="PRECIO_LIMITE",
        monto_operado=100,
    )

    result = AttributionService().calculate_attribution(days=30)
    flows = result["flows"]

    assert "total_period_return_pct" in flows
    assert "market_return_pct" in flows
    assert "flow_effect_pct" in flows
