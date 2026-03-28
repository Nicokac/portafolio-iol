import pytest
from django.utils import timezone

from apps.core.services.finviz.finviz_mapping_service import FinvizMappingService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_resolve_from_metadata_uses_manual_overrides():
    parametro = ParametroActivo.objects.create(
        simbolo="BRKB",
        sector="Finanzas",
        bloque_estrategico="Defensivo",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    result = FinvizMappingService().resolve_from_metadata(parametro)

    assert result.status == "mapped"
    assert result.finviz_symbol == "BRK-B"
    assert result.reason == "manual_override"


@pytest.mark.django_db
def test_build_metadata_universe_summary_marks_out_of_scope_assets():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
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

    summary = FinvizMappingService().build_metadata_universe_summary()

    assert summary["total"] == 2
    assert summary["mapped"] == 1
    assert summary["out_of_scope"] == 1
    assert any(row["internal_symbol"] == "AL30" and row["status"] == "out_of_scope" for row in summary["rows"])


@pytest.mark.django_db
def test_build_current_portfolio_summary_marks_missing_metadata():
    now = timezone.now()
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo="AAPL",
        descripcion="Cedear Apple Inc.",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=1,
        ppc=1,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=100,
        pais_titulo="argentina",
        mercado="bcba",
        tipo="CEDEARS",
        plazo="t1",
        moneda="peso_Argentino",
    )

    summary = FinvizMappingService().build_current_portfolio_summary()

    assert summary["total"] == 1
    assert summary["missing_metadata"] == 1
    assert summary["rows"][0]["internal_symbol"] == "AAPL"
    assert summary["rows"][0]["source"] == "portfolio"
