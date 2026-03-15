import pytest

from apps.core.services.analytics_v2.scenario_sensitivity_service import ScenarioSensitivityService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


@pytest.fixture
def service():
    return ScenarioSensitivityService()


def _position(
    symbol="AAPL",
    *,
    sector="Tecnologia",
    country="USA",
    asset_type="equity",
    strategic_bucket="Growth",
    patrimonial_type="Equity",
    currency="USD",
):
    return NormalizedPosition(
        symbol=symbol,
        description=symbol,
        market_value=1000.0,
        weight_pct=25.0,
        sector=sector,
        country=country,
        asset_type=asset_type,
        strategic_bucket=strategic_bucket,
        patrimonial_type=patrimonial_type,
        currency=currency,
    )


def test_sensitivity_service_rejects_unknown_scenario(service):
    with pytest.raises(ValueError, match="Unknown scenario_key"):
        service.resolve_asset_sensitivity("unknown", _position())


def test_spy_down_10_hits_us_equity_more_than_bond(service):
    equity = service.resolve_asset_sensitivity("spy_down_10", _position())
    bond = service.resolve_asset_sensitivity(
        "spy_down_10",
        _position(symbol="AL30", sector="Soberano", country="Argentina", asset_type="bond", patrimonial_type="Bond", currency="ARS"),
    )

    assert equity["shock_multiplier"] == -0.10
    assert equity["transmission_channel"] == "equity_usa"
    assert bond["shock_multiplier"] == -0.02


def test_tech_shock_hits_technology_more_than_non_tech(service):
    tech = service.resolve_asset_sensitivity("tech_shock", _position())
    defensive = service.resolve_asset_sensitivity(
        "tech_shock",
        _position(symbol="KO", sector="Consumo defensivo", strategic_bucket="Dividendos"),
    )

    assert tech["shock_multiplier"] == -0.18
    assert defensive["shock_multiplier"] == -0.06


def test_argentina_stress_hits_local_bonds_more_than_non_argentina(service):
    local_bond = service.resolve_asset_sensitivity(
        "argentina_stress",
        _position(symbol="GD30", sector="Soberano", country="Argentina", asset_type="bond", patrimonial_type="Bond", currency="ARS"),
    )
    usa_equity = service.resolve_asset_sensitivity(
        "argentina_stress",
        _position(symbol="SPY", sector="Indice", country="USA", asset_type="etf", currency="USD"),
    )

    assert local_bond["shock_multiplier"] == -0.30
    assert usa_equity["shock_multiplier"] == 0.0


def test_ars_devaluation_benefits_usd_exposure(service):
    usd_position = service.resolve_asset_sensitivity("ars_devaluation", _position())
    ars_position = service.resolve_asset_sensitivity(
        "ars_devaluation",
        _position(symbol="YPFD", sector="Energia", country="Argentina", asset_type="equity", currency="ARS"),
    )

    assert usd_position["shock_multiplier"] == 0.20
    assert ars_position["shock_multiplier"] == -0.08


def test_usa_rates_up_200bps_hits_us_bond_more_than_non_usa(service):
    us_bond = service.resolve_asset_sensitivity(
        "usa_rates_up_200bps",
        _position(symbol="IEF", sector="Bond", country="USA", asset_type="bond", patrimonial_type="Bond", currency="USD"),
    )
    non_usa = service.resolve_asset_sensitivity(
        "usa_rates_up_200bps",
        _position(symbol="AL30", sector="Soberano", country="Argentina", asset_type="bond", patrimonial_type="Bond", currency="ARS"),
    )

    assert us_bond["shock_multiplier"] == -0.10
    assert non_usa["shock_multiplier"] == 0.0
