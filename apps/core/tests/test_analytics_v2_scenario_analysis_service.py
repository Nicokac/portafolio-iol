from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.analytics_v2.scenario_analysis_service import ScenarioAnalysisService
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
def test_scenario_analysis_returns_empty_payload_for_empty_portfolio():
    result = ScenarioAnalysisService().analyze("spy_down_10")

    assert result["by_asset"] == []
    assert result["metadata"]["warnings"] == ["empty_portfolio"]
    assert result["total_impact_money"] == 0.0


@pytest.mark.django_db
def test_scenario_analysis_invalid_scenario_raises():
    with pytest.raises(ValueError, match="Unknown scenario_key"):
        ScenarioAnalysisService().analyze("invalid")


@pytest.mark.django_db
def test_scenario_analysis_calculates_total_and_group_impacts():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="KO",
        sector="Consumo defensivo",
        bloque_estrategico="Dividendos",
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

    fecha = now
    _make_asset_snapshot(fecha, "AAPL", 1000, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "KO", 500, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "AL30", 500, tipo="TitulosPublicos", moneda="peso_Argentino")

    result = ScenarioAnalysisService().analyze("spy_down_10")

    assert result["scenario"]["scenario_key"] == "spy_down_10"
    assert len(result["by_asset"]) == 3
    assert round(sum(item["estimated_impact_money"] for item in result["by_asset"]), 2) == result["total_impact_money"]
    assert any(group["key"] == "Tecnologia" for group in result["by_sector"])
    assert any(group["key"] == "USA" for group in result["by_country"])


@pytest.mark.django_db
def test_scenario_analysis_top_negative_contributors_are_sorted():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="MSFT",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="KO",
        sector="Consumo defensivo",
        bloque_estrategico="Dividendos",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    fecha = now
    _make_asset_snapshot(fecha, "AAPL", 1500, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "MSFT", 1200, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "KO", 300, tipo="ACCIONES", moneda="dolar_Estadounidense")

    result = ScenarioAnalysisService().analyze("tech_shock")

    top = result["top_negative_contributors"]
    assert top[0]["estimated_impact_money"] <= top[1]["estimated_impact_money"]
    assert top[0]["symbol"] == "AAPL"


@pytest.mark.django_db
def test_scenario_analysis_does_not_over_shock_cash_like_positions():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="ADBAICA",
        sector="Cash Mgmt",
        bloque_estrategico="Liquidez",
        pais_exposicion="Argentina",
        tipo_patrimonial="FCI",
    )
    ParametroActivo.objects.create(
        simbolo="CAU1",
        sector="Liquidez",
        bloque_estrategico="Liquidez",
        pais_exposicion="Argentina",
        tipo_patrimonial="Cash",
    )

    fecha = now
    _make_asset_snapshot(fecha, "ADBAICA", 1000, tipo="FondoComundeInversion", moneda="peso_Argentino")
    _make_asset_snapshot(fecha, "CAU1", 1000, tipo="CAUCIONESPESOS", moneda="peso_Argentino")

    result = ScenarioAnalysisService().analyze("argentina_stress")
    impacts = {item["symbol"]: item for item in result["by_asset"]}

    assert impacts["ADBAICA"]["estimated_impact_money"] == 0.0
    assert impacts["CAU1"]["estimated_impact_money"] == 0.0


@pytest.mark.django_db
def test_scenario_analysis_marks_missing_metadata_warning():
    fecha = timezone.now()
    _make_asset_snapshot(fecha, "UNKNOWN", 1000, tipo="ACCIONES", moneda="dolar_Estadounidense")

    result = ScenarioAnalysisService().analyze("spy_down_10")

    assert "missing_metadata:UNKNOWN" in result["metadata"]["warnings"]
    assert result["metadata"]["confidence"] == "medium"


@pytest.mark.django_db
def test_scenario_analysis_builds_recommendation_signals_for_tech_and_liquidity_buffer():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="MSFT",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="ADBAICA",
        sector="Cash Mgmt",
        bloque_estrategico="Liquidez",
        pais_exposicion="Argentina",
        tipo_patrimonial="FCI",
    )

    fecha = now
    _make_asset_snapshot(fecha, "AAPL", 1000, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "MSFT", 1000, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(fecha, "ADBAICA", 800, tipo="FondoComundeInversion", moneda="peso_Argentino")

    signals = ScenarioAnalysisService().build_recommendation_signals()
    keyed = {signal["signal_key"]: signal for signal in signals}

    assert "scenario_vulnerability_tech" in keyed
    assert keyed["scenario_vulnerability_tech"]["severity"] == "high"
    assert "scenario_liquidity_buffer" in keyed
    assert keyed["scenario_liquidity_buffer"]["evidence"]["cash_like_weight_pct"] == pytest.approx(28.57, abs=0.01)


@pytest.mark.django_db
def test_scenario_analysis_builds_argentina_and_ars_devaluation_signals():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AL30",
        sector="Soberano",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )
    ParametroActivo.objects.create(
        simbolo="YPFD",
        sector="Energia",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Equity",
    )

    fecha = now
    _make_asset_snapshot(fecha, "AL30", 1200, tipo="TitulosPublicos", moneda="peso_Argentino")
    _make_asset_snapshot(fecha, "YPFD", 800, tipo="ACCIONES", moneda="peso_Argentino")

    signals = ScenarioAnalysisService().build_recommendation_signals()
    keyed = {signal["signal_key"]: signal for signal in signals}

    assert keyed["scenario_vulnerability_argentina"]["severity"] == "high"
    assert keyed["scenario_vulnerability_argentina"]["evidence"]["scenario_key"] == "argentina_stress"
    assert keyed["scenario_vulnerability_ars_devaluation"]["severity"] == "high"
    assert keyed["scenario_vulnerability_ars_devaluation"]["evidence"]["scenario_key"] == "ars_devaluation"


@pytest.mark.django_db
def test_scenario_analysis_build_recommendation_signals_returns_empty_for_empty_portfolio():
    assert ScenarioAnalysisService().build_recommendation_signals() == []
