import pytest

from apps.core.services.analytics_v2.factor_classifier_service import FactorClassifierService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


@pytest.fixture
def service():
    return FactorClassifierService()


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


def test_factor_classifier_uses_explicit_symbol_mapping(service):
    result = service.classify_position(_position(symbol="AAPL"))

    assert result["factor"] == "growth"
    assert result["source"] == "explicit_symbol_map"
    assert result["confidence"] == "high"


def test_factor_classifier_falls_back_to_strategic_bucket(service):
    result = service.classify_position(
        _position(symbol="GEN1", sector="Indice", strategic_bucket="Dividendos")
    )

    assert result["factor"] == "dividend"
    assert result["source"] == "strategic_bucket"
    assert "strategic_bucket=Dividendos" in result["notes"]


def test_factor_classifier_falls_back_to_technology_sector(service):
    result = service.classify_position(
        _position(symbol="GEN2", sector="Tecnologia / Semiconductores", strategic_bucket="Core")
    )

    assert result["factor"] == "growth"
    assert result["source"] == "sector"


def test_factor_classifier_falls_back_to_sector_mapping(service):
    result = service.classify_position(
        _position(symbol="GEN3", sector="Utilities", strategic_bucket="Core")
    )

    assert result["factor"] == "defensive"
    assert result["source"] == "sector"


def test_factor_classifier_returns_unknown_for_bonds(service):
    result = service.classify_position(
        _position(symbol="AL30", sector="Soberano", asset_type="bond", strategic_bucket="Argentina", currency="ARS")
    )

    assert result["factor"] is None
    assert result["source"] == "unknown"
    assert result["confidence"] == "low"


def test_factor_classifier_returns_unknown_when_no_proxy_is_reliable(service):
    result = service.classify_position(
        _position(symbol="GEN4", sector="Indice", strategic_bucket="Core", asset_type="equity")
    )

    assert result["factor"] is None
    assert result["source"] == "unknown"
