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
def test_risk_contribution_ignores_intraday_duplicates_for_asset_history():
    now = timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)

    ParametroActivo.objects.create(
        simbolo="SPY",
        sector="Indice",
        bloque_estrategico="Core",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    daily_values = [1000, 1010, 1020]
    for i, value in enumerate(daily_values):
        fecha = now - timedelta(days=2 - i)
        _make_asset_snapshot(fecha, "SPY", value, tipo="CEDEARS", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha + timedelta(hours=2), "SPY", value, tipo="CEDEARS", moneda="dolar_Estadounidense")

    result = RiskContributionService().calculate()

    assert result["items"][0]["used_volatility_fallback"] is True
    assert "used_fallback:SPY:insufficient_history" in result["metadata"]["warnings"]


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


@pytest.mark.django_db
def test_risk_contribution_populates_group_aggregations_consistently():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="Estados Unidos",
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
        simbolo="AL30",
        sector="Soberano",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )

    aapl_values = [1000, 1040, 1020, 1060, 1090]
    msft_values = [900, 945, 930, 970, 1000]
    al30_values = [1000, 1003, 1001, 1004, 1006]

    for i, (aapl, msft, al30) in enumerate(zip(aapl_values, msft_values, al30_values)):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "AAPL", aapl, tipo="ACCIONES", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha, "MSFT", msft, tipo="ACCIONES", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha, "AL30", al30, tipo="TitulosPublicos")

    result = RiskContributionService().calculate(top_n=3)

    assert [group["key"] for group in result["by_sector"]] == ["Tecnologia", "Soberano"]
    assert [group["key"] for group in result["by_country"]] == ["USA", "Argentina"]
    assert [group["key"] for group in result["by_asset_type"]] == ["equity", "bond"]

    total_sector_contribution = round(sum(group["contribution_pct"] for group in result["by_sector"]), 2)
    total_country_contribution = round(sum(group["contribution_pct"] for group in result["by_country"]), 2)
    total_type_contribution = round(sum(group["contribution_pct"] for group in result["by_asset_type"]), 2)

    assert total_sector_contribution == round(sum(item["contribution_pct"] for item in result["items"]), 2)
    assert total_country_contribution == round(sum(item["contribution_pct"] for item in result["items"]), 2)
    assert total_type_contribution == round(sum(item["contribution_pct"] for item in result["items"]), 2)

    usa_group = result["by_country"][0]
    assert usa_group["key"] == "USA"
    assert round(usa_group["weight_pct"], 2) == round(
        sum(item["weight_pct"] for item in result["items"] if item["country"] in {"USA", "Estados Unidos"}),
        2,
    )


@pytest.mark.django_db
def test_risk_contribution_builds_recommendation_signals_for_top_assets_and_tech():
    now = timezone.now()

    tech_assets = [
        ("AAPL", [1000, 1120, 1040, 1180, 1210]),
        ("MSFT", [900, 1005, 940, 1060, 1090]),
        ("NVDA", [800, 930, 860, 1020, 1080]),
    ]

    for symbol, _ in tech_assets:
        ParametroActivo.objects.create(
            simbolo=symbol,
            sector="Tecnologia",
            bloque_estrategico="Growth",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )

    for i in range(5):
        fecha = now - timedelta(days=4 - i)
        for symbol, values in tech_assets:
            _make_asset_snapshot(fecha, symbol, values[i], tipo="ACCIONES", moneda="dolar_Estadounidense")

    signals = RiskContributionService().build_recommendation_signals(top_n=3)
    signal_keys = {signal["signal_key"] for signal in signals}

    assert "risk_concentration_top_assets" in signal_keys
    assert "risk_concentration_tech" in signal_keys


@pytest.mark.django_db
def test_risk_contribution_builds_argentina_and_divergence_signals():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="GD30",
        sector="Soberano",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )
    ParametroActivo.objects.create(
        simbolo="AL30",
        sector="Soberano",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="Bond",
    )
    ParametroActivo.objects.create(
        simbolo="KO",
        sector="Consumo defensivo",
        bloque_estrategico="Dividendos",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    gd30_values = [1000, 1180, 1030, 1210, 1260]
    al30_values = [950, 1110, 980, 1150, 1200]
    ko_values = [1200, 1210, 1205, 1215, 1220]

    for i in range(5):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "GD30", gd30_values[i], tipo="TitulosPublicos")
        _make_asset_snapshot(fecha, "AL30", al30_values[i], tipo="TitulosPublicos")
        _make_asset_snapshot(fecha, "KO", ko_values[i], tipo="ACCIONES", moneda="dolar_Estadounidense")

    signals = RiskContributionService().build_recommendation_signals(top_n=3)
    keyed = {signal["signal_key"]: signal for signal in signals}

    assert "risk_concentration_argentina" in keyed
    assert keyed["risk_concentration_argentina"]["evidence"]["country"] == "Argentina"
    assert "risk_vs_weight_divergence" in keyed


@pytest.mark.django_db
def test_risk_contribution_single_position_returns_full_contribution_and_respects_top_n():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="SPY",
        sector="Indice",
        bloque_estrategico="Core",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    for i, value in enumerate([1000, 1010, 1030, 1025, 1050]):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "SPY", value, tipo="CEDEARS", moneda="dolar_Estadounidense")

    result = RiskContributionService().calculate(top_n=1)

    assert len(result["items"]) == 1
    assert len(result["top_contributors"]) == 1
    assert result["items"][0]["symbol"] == "SPY"
    assert result["items"][0]["contribution_pct"] == 100.0
    assert result["top_contributors"][0]["symbol"] == "SPY"


@pytest.mark.django_db
def test_risk_contribution_top_contributors_are_sorted_and_limited():
    now = timezone.now()

    fixtures = [
        ("AAPL", "Tecnologia", "USA", "Equity", [1000, 1100, 1010, 1140, 1200], "ACCIONES", "dolar_Estadounidense"),
        ("AL30", "Soberano", "Argentina", "Bond", [1000, 1040, 990, 1050, 1070], "TitulosPublicos", "peso_Argentino"),
        ("KO", "Consumo defensivo", "USA", "Equity", [1000, 1005, 1002, 1008, 1010], "ACCIONES", "dolar_Estadounidense"),
    ]

    for symbol, sector, country, patrimonial, _, _, _ in fixtures:
        ParametroActivo.objects.create(
            simbolo=symbol,
            sector=sector,
            bloque_estrategico="Test",
            pais_exposicion=country,
            tipo_patrimonial=patrimonial,
        )

    for i in range(5):
        fecha = now - timedelta(days=4 - i)
        for symbol, _, _, _, values, tipo, moneda in fixtures:
            _make_asset_snapshot(fecha, symbol, values[i], tipo=tipo, moneda=moneda)

    result = RiskContributionService().calculate(top_n=2)

    top = result["top_contributors"]
    assert len(top) == 2
    assert top[0]["contribution_pct"] >= top[1]["contribution_pct"]
    assert top[0]["symbol"] == "AAPL"


@pytest.mark.django_db
def test_risk_contribution_metadata_degrades_with_mixed_fallback_and_missing_metadata():
    now = timezone.now()

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    # AAPL con histórico suficiente
    for i, value in enumerate([1000, 1060, 1020, 1090, 1120]):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "AAPL", value, tipo="ACCIONES", moneda="dolar_Estadounidense")

    # UNKNOWN sin metadata y con histórico insuficiente
    _make_asset_snapshot(now - timedelta(days=1), "UNKNOWN", 800, tipo="ACCIONES", moneda="dolar_Estadounidense")
    _make_asset_snapshot(now, "UNKNOWN", 810, tipo="ACCIONES", moneda="dolar_Estadounidense")

    result = RiskContributionService().calculate(top_n=3)

    assert result["metadata"]["confidence"] == "low"
    assert "missing_metadata:UNKNOWN" in result["metadata"]["warnings"]
    assert "used_fallback:UNKNOWN:insufficient_history" in result["metadata"]["warnings"]


@pytest.mark.django_db
def test_risk_contribution_output_contract_contains_all_expected_keys():
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

    for i, (aapl, al30) in enumerate(zip([1000, 1040, 1020, 1060, 1090], [1000, 1004, 1002, 1006, 1008])):
        fecha = now - timedelta(days=4 - i)
        _make_asset_snapshot(fecha, "AAPL", aapl, tipo="ACCIONES", moneda="dolar_Estadounidense")
        _make_asset_snapshot(fecha, "AL30", al30, tipo="TitulosPublicos")

    result = RiskContributionService().calculate(top_n=2)

    assert set(result.keys()) == {
        "items",
        "by_sector",
        "by_country",
        "by_asset_type",
        "top_contributors",
        "metadata",
    }
    assert set(result["items"][0].keys()) == {
        "symbol",
        "weight_pct",
        "volatility_proxy",
        "risk_score",
        "contribution_pct",
        "sector",
        "country",
        "asset_type",
        "used_volatility_fallback",
    }
    assert set(result["metadata"].keys()) == {
        "methodology",
        "data_basis",
        "limitations",
        "confidence",
        "warnings",
    }
