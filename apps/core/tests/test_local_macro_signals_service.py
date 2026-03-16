from unittest.mock import Mock

import pytest

from apps.core.services.analytics_v2.local_macro_signals_service import LocalMacroSignalsService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


def build_position(
    *,
    symbol: str,
    market_value: float,
    sector: str,
    country: str,
    asset_type: str,
    strategic_bucket: str = "Argentina",
    patrimonial_type: str = "Bond",
    currency: str = "ARS",
):
    return NormalizedPosition(
        symbol=symbol,
        description=symbol,
        market_value=market_value,
        weight_pct=0.0,
        sector=sector,
        country=country,
        asset_type=asset_type,
        strategic_bucket=strategic_bucket,
        patrimonial_type=patrimonial_type,
        currency=currency,
        gain_pct=0.0,
        gain_money=0.0,
    )


@pytest.mark.django_db
def test_local_macro_signals_returns_empty_portfolio_warning():
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = []
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=Mock())

    result = service.calculate()

    assert result["summary"] == {}
    assert result["metadata"]["warnings"] == ["empty_portfolio"]


def test_local_macro_signals_detect_negative_real_carry_and_sovereign_risk():
    positions = [
        build_position(symbol="CAUCION", market_value=350.0, sector="Liquidez", country="Argentina", asset_type="cash", patrimonial_type="Cash"),
        build_position(symbol="GD30", market_value=180.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="AL30", market_value=120.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="SPY", market_value=350.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.side_effect = lambda position: position.asset_type == "cash"

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 24.0,
        "ipc_nacional_variation_yoy": 32.0,
        "ipc_nacional_variation_ytd": 8.0,
        "usdars_oficial": 1400.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["ars_liquidity_weight_pct"] == 35.0
    assert result["summary"]["badlar_real_carry_pct"] == -8.0
    signal_keys = {signal["signal_key"] for signal in signals}
    assert "local_liquidity_real_carry_negative" in signal_keys
    assert "local_sovereign_risk_excess" in signal_keys


def test_local_macro_signals_detects_low_cer_hedge_with_high_argentina_weight():
    positions = [
        build_position(symbol="GD30", market_value=220.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="YPFD", market_value=120.0, sector="Energia", country="Argentina", asset_type="equity", patrimonial_type="Equity"),
        build_position(symbol="SPY", market_value=660.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.return_value = False

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 28.0,
        "ipc_nacional_variation_yoy": 40.0,
        "ipc_nacional_variation_ytd": 10.0,
        "usdars_oficial": 1400.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    signals = service.build_recommendation_signals()

    signal_keys = {signal["signal_key"] for signal in signals}
    assert "local_inflation_hedge_gap" in signal_keys


def test_local_macro_signals_detects_high_fx_gap_with_material_argentina_weight():
    positions = [
        build_position(symbol="GD30", market_value=260.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="CAUCION", market_value=140.0, sector="Liquidez", country="Argentina", asset_type="cash", patrimonial_type="Cash"),
        build_position(symbol="SPY", market_value=600.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.side_effect = lambda position: position.asset_type == "cash"

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 28.0,
        "ipc_nacional_variation_yoy": 36.0,
        "ipc_nacional_variation_ytd": 9.0,
        "usdars_oficial": 1000.0,
        "usdars_mep": 1220.0,
        "fx_gap_pct": 22.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["fx_gap_pct"] == 22.0
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_fx_gap_high" in keyed
    assert keyed["local_fx_gap_high"]["evidence"]["usdars_mep"] == 1220.0


def test_local_macro_signals_degrades_confidence_when_macro_references_are_missing():
    positions = [
        build_position(symbol="GD30", market_value=100.0, sector="Soberano", country="Argentina", asset_type="bond"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.return_value = False

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {}
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()

    assert result["metadata"]["confidence"] == "low"
    assert "missing_macro_reference:badlar_privada" in result["metadata"]["warnings"]
    assert "missing_macro_reference:ipc_nacional_variation_yoy" in result["metadata"]["warnings"]
