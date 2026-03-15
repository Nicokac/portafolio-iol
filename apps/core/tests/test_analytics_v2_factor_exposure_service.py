from types import SimpleNamespace

import pytest

from apps.core.services.analytics_v2.factor_exposure_service import FactorExposureService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


def _position(
    symbol="AAPL",
    *,
    market_value=1000.0,
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
        market_value=market_value,
        weight_pct=25.0,
        sector=sector,
        country=country,
        asset_type=asset_type,
        strategic_bucket=strategic_bucket,
        patrimonial_type=patrimonial_type,
        currency=currency,
    )


def test_factor_exposure_returns_empty_payload_for_empty_portfolio():
    service = FactorExposureService(positions_loader=SimpleNamespace(_load_current_positions=lambda: []))

    result = service.calculate()

    assert result["factors"] == []
    assert result["dominant_factor"] is None
    assert result["metadata"]["warnings"] == ["empty_portfolio"]


def test_factor_exposure_aggregates_classified_positions_and_unknown_assets():
    positions = [
        _position(symbol="AAPL", market_value=1200.0),
        _position(symbol="XLU", market_value=800.0, sector="Utilities", strategic_bucket="Defensivo", asset_type="etf"),
        _position(symbol="AL30", market_value=1000.0, sector="Soberano", country="Argentina", asset_type="bond", strategic_bucket="Argentina", currency="ARS"),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    result = service.calculate()
    factors = {item["factor"]: item for item in result["factors"]}

    assert factors["growth"]["exposure_pct"] == 60.0
    assert factors["defensive"]["exposure_pct"] == 40.0
    assert result["dominant_factor"] == "growth"
    assert result["unknown_assets"] == ["AL30"]
    assert result["metadata"]["confidence"] == "medium"


def test_factor_exposure_marks_underrepresented_factors():
    positions = [
        _position(symbol="AAPL", market_value=1000.0),
        _position(symbol="KO", market_value=1000.0, sector="Consumo defensivo", strategic_bucket="Dividendos"),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    result = service.calculate()

    assert "value" in result["underrepresented_factors"]
    assert "quality" in result["underrepresented_factors"]
    assert "cyclical" in result["underrepresented_factors"]
    assert "growth" not in result["underrepresented_factors"]
    assert "dividend" not in result["underrepresented_factors"]


def test_factor_exposure_degrades_factor_confidence_when_fallback_is_used():
    positions = [
        _position(symbol="GEN1", market_value=1000.0, sector="Utilities", strategic_bucket="Core", asset_type="etf"),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    result = service.calculate()
    factors = {item["factor"]: item for item in result["factors"]}

    assert factors["defensive"]["confidence"] == "medium"
    assert "used_factor_fallback:GEN1:sector" in result["metadata"]["warnings"]


def test_factor_exposure_uses_high_confidence_when_no_unknown_assets_exist():
    positions = [
        _position(symbol="AAPL", market_value=1000.0),
        _position(symbol="MSFT", market_value=1000.0),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    result = service.calculate()

    assert result["metadata"]["confidence"] == "high"
    assert result["unknown_assets"] == []


def test_factor_exposure_builds_growth_and_concentration_signals():
    positions = [
        _position(symbol="AAPL", market_value=1200.0),
        _position(symbol="MSFT", market_value=1000.0),
        _position(symbol="NVDA", market_value=800.0),
        _position(symbol="KO", market_value=200.0, sector="Consumo defensivo", strategic_bucket="Dividendos"),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    signals = service.build_recommendation_signals()
    keyed = {signal["signal_key"]: signal for signal in signals}

    assert keyed["factor_growth_excess"]["evidence"]["factor"] == "growth"
    assert keyed["factor_concentration_excessive"]["evidence"]["factor"] == "growth"


def test_factor_exposure_builds_defensive_and_dividend_gap_signals():
    positions = [
        _position(symbol="AAPL", market_value=1000.0),
        _position(symbol="MSFT", market_value=1000.0),
    ]
    service = FactorExposureService(
        positions_loader=SimpleNamespace(_load_current_positions=lambda: positions)
    )

    signals = service.build_recommendation_signals()
    signal_keys = {signal["signal_key"] for signal in signals}

    assert "factor_defensive_gap" in signal_keys
    assert "factor_dividend_gap" in signal_keys


def test_factor_exposure_build_recommendation_signals_returns_empty_for_empty_portfolio():
    service = FactorExposureService(positions_loader=SimpleNamespace(_load_current_positions=lambda: []))

    assert service.build_recommendation_signals() == []
