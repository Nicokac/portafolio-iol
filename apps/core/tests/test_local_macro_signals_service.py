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


def test_local_macro_signals_detects_fx_gap_deterioration_with_material_argentina_weight():
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
        "fx_gap_change_30d": 7.0,
        "fx_gap_change_pct_30d": 46.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["fx_gap_change_30d"] == 7.0
    assert result["summary"]["fx_gap_change_pct_30d"] == 46.0
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_fx_gap_deteriorating" in keyed
    assert keyed["local_fx_gap_deteriorating"]["evidence"]["fx_gap_change_30d"] == 7.0


def test_local_macro_signals_detects_divergent_fx_regime_with_ccl():
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
        "usdars_mep": 1180.0,
        "usdars_ccl": 1230.0,
        "usdars_financial": 1205.0,
        "fx_gap_pct": 20.5,
        "fx_gap_change_30d": 9.5,
        "fx_gap_change_pct_30d": 86.36,
        "fx_mep_ccl_spread_pct": 4.24,
        "fx_signal_state": "divergent",
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["usdars_ccl"] == 1230.0
    assert result["summary"]["fx_signal_state"] == "divergent"
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_fx_regime_divergent" in keyed
    assert keyed["local_fx_regime_divergent"]["evidence"]["fx_mep_ccl_spread_pct"] == 4.24


def test_local_macro_signals_detects_uva_acceleration_and_negative_real_rate():
    positions = [
        build_position(symbol="CAUCION", market_value=320.0, sector="Liquidez", country="Argentina", asset_type="cash", patrimonial_type="Cash"),
        build_position(symbol="GD30", market_value=180.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="SPY", market_value=500.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.side_effect = lambda position: position.asset_type == "cash"

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 30.0,
        "ipc_nacional_variation_yoy": 32.0,
        "ipc_nacional_variation_ytd": 8.0,
        "usdars_oficial": 1000.0,
        "uva": 1524.4,
        "uva_change_30d": 44.4,
        "uva_change_pct_30d": 3.0,
        "uva_annualized_pct_30d": 43.27,
        "real_rate_badlar_vs_uva_30d": -13.27,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["uva_change_pct_30d"] == 3.0
    assert result["summary"]["real_rate_badlar_vs_uva_30d"] == -13.27
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "inflation_accelerating" in keyed
    assert "real_rate_negative" in keyed


def test_local_macro_signals_detects_high_country_risk_with_sovereign_weight():
    positions = [
        build_position(symbol="GD30", market_value=220.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="AL30", market_value=140.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="SPY", market_value=640.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.return_value = False

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 28.0,
        "ipc_nacional_variation_yoy": 36.0,
        "ipc_nacional_variation_ytd": 9.0,
        "usdars_oficial": 1000.0,
        "riesgo_pais_arg": 1250.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["riesgo_pais_arg"] == 1250.0
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_country_risk_high" in keyed
    assert keyed["local_country_risk_high"]["evidence"]["riesgo_pais_arg"] == 1250.0


def test_local_macro_signals_detects_country_risk_deterioration_with_material_local_exposure():
    positions = [
        build_position(symbol="GD30", market_value=240.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="AL30", market_value=140.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="SPY", market_value=620.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.return_value = False

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 28.0,
        "ipc_nacional_variation_yoy": 36.0,
        "ipc_nacional_variation_ytd": 9.0,
        "usdars_oficial": 1000.0,
        "riesgo_pais_arg": 1280.0,
        "riesgo_pais_arg_change_30d": 220.0,
        "riesgo_pais_arg_change_pct_30d": 20.75,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["riesgo_pais_arg_change_30d"] == 220.0
    assert result["summary"]["riesgo_pais_arg_change_pct_30d"] == 20.75
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_country_risk_deteriorating" in keyed
    assert keyed["local_country_risk_deteriorating"]["evidence"]["riesgo_pais_arg_change_30d"] == 220.0


def test_local_macro_signals_detects_single_name_concentration_in_local_sovereigns():
    positions = [
        build_position(symbol="GD30", market_value=300.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="AL30", market_value=120.0, sector="Soberano", country="Argentina", asset_type="bond"),
        build_position(symbol="TZX26", market_value=80.0, sector="CER", country="Argentina", asset_type="bond"),
        build_position(symbol="SPY", market_value=580.0, sector="Indice", country="USA", asset_type="equity", strategic_bucket="Growth", patrimonial_type="Equity", currency="USD"),
    ]
    positions_loader = Mock()
    positions_loader._load_current_positions.return_value = positions
    positions_loader._is_cash_like_position.return_value = False

    macro_service = Mock()
    macro_service.get_context_summary.return_value = {
        "badlar_privada": 28.0,
        "ipc_nacional_variation_yoy": 36.0,
        "ipc_nacional_variation_ytd": 9.0,
        "usdars_oficial": 1000.0,
        "riesgo_pais_arg": 1250.0,
    }
    service = LocalMacroSignalsService(positions_loader=positions_loader, macro_service=macro_service)

    result = service.calculate()
    signals = service.build_recommendation_signals()

    assert result["summary"]["top_local_sovereign_symbol"] == "GD30"
    assert result["summary"]["local_sovereign_symbols_count"] == 2
    assert result["summary"]["top_local_sovereign_share_pct"] == 71.43
    assert result["summary"]["local_sovereign_concentration_hhi"] == 5918.49
    assert result["summary"]["local_hard_dollar_bond_weight_pct"] == 38.89
    assert result["summary"]["local_cer_bond_weight_pct"] == 7.41
    assert result["summary"]["local_hard_dollar_share_pct"] == 84.0
    assert result["summary"]["local_cer_share_pct"] == 16.0
    keyed = {signal["signal_key"]: signal for signal in signals}
    assert "local_sovereign_single_name_concentration" in keyed
    assert "local_sovereign_hard_dollar_dependence" in keyed
    assert keyed["local_sovereign_single_name_concentration"]["evidence"]["top_local_sovereign_symbol"] == "GD30"


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
