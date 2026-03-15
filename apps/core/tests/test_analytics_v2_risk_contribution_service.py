from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.analytics_v2.risk_contribution_service import RiskContributionService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_asset_snapshot(fecha, simbolo, valorizado, *, tipo="ACCIONES", moneda="peso_Argentino"):
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
        tipo=tipo,
        moneda=moneda,
    )


@pytest.mark.django_db
def test_risk_contribution_returns_empty_payload_for_empty_portfolio():
    result = RiskContributionService().calculate()

    assert result["items"] == []
    assert result["top_contributors"] == []
    assert result["metadata"]["warnings"] == ["empty_portfolio"]


@pytest.mark.django_db
def test_risk_contribution_excludes_liquidity_and_cash_management_from_universe():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="CAU1",
        sector="Liquidez",
        bloque_estrategico="Liquidez",
        pais_exposicion="Argentina",
        tipo_patrimonial="Cash",
    )
    ParametroActivo.objects.create(
        simbolo="ADBAICA",
        sector="Cash Mgmt",
        bloque_estrategico="Liquidez",
        pais_exposicion="Argentina",
        tipo_patrimonial="FCI",
    )

    for i, value in enumerate([1000, 1010, 1020, 1030, 1040]):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "AAPL", value, tipo="ACCIONES", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha, "CAU1", 500, tipo="CAUCIONESPESOS")
        _make_asset_snapshot(fecha, "ADBAICA", 200, tipo="FondoComundeInversion")

    result = RiskContributionService().calculate()

    assert [item["symbol"] for item in result["items"]] == ["AAPL"]
    assert result["items"][0]["contribution_pct"] == 100.0


@pytest.mark.django_db
def test_risk_contribution_uses_historical_volatility_when_available():
    now = timezone.now()

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

    aapl_values = [1000, 1050, 1030, 1090, 1120]
    al30_values = [1000, 1005, 1002, 1007, 1008]

    for i, (aapl, al30) in enumerate(zip(aapl_values, al30_values)):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "AAPL", aapl, tipo="ACCIONES", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha, "AL30", al30, tipo="TitulosPublicos")

    result = RiskContributionService().calculate(top_n=2)

    assert len(result["items"]) == 2
    assert result["metadata"]["confidence"] == "high"
    assert result["items"][0]["used_volatility_fallback"] is False
    assert result["items"][1]["used_volatility_fallback"] is False
    assert round(sum(item["contribution_pct"] for item in result["items"]), 2) == 100.0
    assert result["top_contributors"][0]["symbol"] == "AAPL"


@pytest.mark.django_db
def test_risk_contribution_falls_back_when_history_is_insufficient():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    _make_asset_snapshot(now - timedelta(days=1), "AAPL", 1000, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(now, "AAPL", 1010, tipo="ACCIONES", moneda="dolar_Estadounidense")

    result = RiskContributionService().calculate()

    assert result["items"][0]["used_volatility_fallback"] is True
    assert "used_fallback:AAPL:insufficient_history" in result["metadata"]["warnings"]
    assert result["metadata"]["confidence"] == "low"


@pytest.mark.django_db
def test_risk_contribution_marks_missing_metadata_as_unknown():
    now = timezone.now()

    for i, value in enumerate([1000, 1020, 1010, 1030, 1040]):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "UNKNOWN", value, tipo="ACCIONES", moneda="dolar_Estadounidense")

    result = RiskContributionService().calculate()

    item = result["items"][0]
    assert item["sector"] == "unknown"
    assert item["country"] == "unknown"
    assert item["asset_type"] == "equity"
    assert "missing_metadata:UNKNOWN" in result["metadata"]["warnings"]
