from types import SimpleNamespace

import pytest

from apps.core.services.analytics_v2.stress_fragility_service import StressFragilityService


def _scenario_result(
    scenario_key,
    *,
    total_impact_pct,
    total_impact_money,
    by_asset,
    by_sector,
    by_country,
    warnings=None,
):
    return {
        "scenario_key": scenario_key,
        "total_impact_pct": total_impact_pct,
        "total_impact_money": total_impact_money,
        "by_asset": by_asset,
        "by_sector": by_sector,
        "by_country": by_country,
        "top_negative_contributors": by_asset[:5],
        "metadata": {
            "warnings": warnings or [],
            "confidence": "high",
        },
    }


def test_stress_fragility_invalid_stress_raises():
    service = StressFragilityService(
        stress_catalog_service=SimpleNamespace(require_stress=lambda key: (_ for _ in ()).throw(ValueError("Unknown stress_key: invalid"))),
        scenario_analysis_service=SimpleNamespace(),
    )

    with pytest.raises(ValueError, match="Unknown stress_key"):
        service.calculate("invalid")


def test_stress_fragility_returns_empty_payload_for_empty_portfolio():
    catalog = SimpleNamespace(require_stress=lambda key: {"stress_key": key, "scenario_keys": ["spy_down_20"], "legacy_mapping_keys": []})
    scenario_service = SimpleNamespace(
        analyze=lambda key: _scenario_result(
            key,
            total_impact_pct=0.0,
            total_impact_money=0.0,
            by_asset=[],
            by_sector=[],
            by_country=[],
            warnings=["empty_portfolio"],
        )
    )
    service = StressFragilityService(catalog, scenario_service)

    result = service.calculate("usa_crash_severe")

    assert result["fragility_score"] == 0.0
    assert result["metadata"]["warnings"] == ["empty_portfolio"]


def test_stress_fragility_combines_multiple_scenarios_and_groups():
    catalog = SimpleNamespace(
        require_stress=lambda key: {
            "stress_key": key,
            "scenario_keys": ["argentina_stress", "ars_devaluation"],
            "legacy_mapping_keys": ["argentina_crisis", "usd_plus_20"],
        }
    )
    scenario_results = {
        "argentina_stress": _scenario_result(
            "argentina_stress",
            total_impact_pct=-12.0,
            total_impact_money=-1200.0,
            by_asset=[
                {
                    "symbol": "AL30",
                    "market_value": 1000.0,
                    "estimated_impact_pct": -30.0,
                    "estimated_impact_money": -300.0,
                    "transmission_channel": "country_argentina",
                },
                {
                    "symbol": "YPFD",
                    "market_value": 1000.0,
                    "estimated_impact_pct": -25.0,
                    "estimated_impact_money": -250.0,
                    "transmission_channel": "country_argentina",
                },
            ],
            by_sector=[{"key": "Soberano", "impact_pct": -15.0, "impact_money": -300.0}],
            by_country=[{"key": "Argentina", "impact_pct": -27.5, "impact_money": -550.0}],
            warnings=[],
        ),
        "ars_devaluation": _scenario_result(
            "ars_devaluation",
            total_impact_pct=-6.0,
            total_impact_money=-600.0,
            by_asset=[
                {
                    "symbol": "AL30",
                    "market_value": 1000.0,
                    "estimated_impact_pct": -8.0,
                    "estimated_impact_money": -80.0,
                    "transmission_channel": "fx_ars",
                },
                {
                    "symbol": "YPFD",
                    "market_value": 1000.0,
                    "estimated_impact_pct": -8.0,
                    "estimated_impact_money": -80.0,
                    "transmission_channel": "fx_ars",
                },
            ],
            by_sector=[{"key": "Soberano", "impact_pct": -4.0, "impact_money": -80.0}],
            by_country=[{"key": "Argentina", "impact_pct": -8.0, "impact_money": -160.0}],
            warnings=[],
        ),
    }
    scenario_service = SimpleNamespace(
        analyze=lambda key: scenario_results[key],
        _load_current_positions=lambda: [],
        _get_cash_like_weight_pct=lambda positions: 5.0,
    )
    service = StressFragilityService(catalog, scenario_service)

    result = service.calculate("local_crisis_severe")

    assert result["total_loss_money"] == -710.0
    assert result["vulnerable_assets"][0]["symbol"] == "AL30"
    assert result["vulnerable_countries"][0]["key"] == "Argentina"
    assert "legacy_mappings:argentina_crisis,usd_plus_20" in result["metadata"]["warnings"]


def test_stress_fragility_high_liquidity_reduces_score_relative_to_low_liquidity():
    catalog = SimpleNamespace(require_stress=lambda key: {"stress_key": key, "scenario_keys": ["spy_down_20"], "legacy_mapping_keys": []})
    high_liquidity_service = SimpleNamespace(
        analyze=lambda key: _scenario_result(
            key,
            total_impact_pct=-4.0,
            total_impact_money=-200.0,
            by_asset=[
                {
                    "symbol": "SPY",
                    "market_value": 5000.0,
                    "estimated_impact_pct": -4.0,
                    "estimated_impact_money": -200.0,
                    "transmission_channel": "equity_usa",
                }
            ],
            by_sector=[{"key": "Indice", "impact_pct": -4.0, "impact_money": -200.0}],
            by_country=[{"key": "USA", "impact_pct": -4.0, "impact_money": -200.0}],
            warnings=[],
        ),
        _load_current_positions=lambda: [],
        _get_cash_like_weight_pct=lambda positions: 30.0,
    )
    low_liquidity_service = SimpleNamespace(
        analyze=high_liquidity_service.analyze,
        _load_current_positions=lambda: [],
        _get_cash_like_weight_pct=lambda positions: 5.0,
    )
    high_service = StressFragilityService(catalog, high_liquidity_service)
    low_service = StressFragilityService(catalog, low_liquidity_service)

    high_result = high_service.calculate("usa_crash_severe")
    low_result = low_service.calculate("usa_crash_severe")

    assert high_result["fragility_score"] < low_result["fragility_score"]


def test_stress_fragility_degrades_confidence_with_missing_metadata_warning():
    catalog = SimpleNamespace(require_stress=lambda key: {"stress_key": key, "scenario_keys": ["em_stress"], "legacy_mapping_keys": []})
    scenario_service = SimpleNamespace(
        analyze=lambda key: _scenario_result(
            key,
            total_impact_pct=-5.0,
            total_impact_money=-500.0,
            by_asset=[
                {
                    "symbol": "UNK",
                    "market_value": 1000.0,
                    "estimated_impact_pct": -5.0,
                    "estimated_impact_money": -500.0,
                    "transmission_channel": "emerging_markets",
                }
            ],
            by_sector=[{"key": "unknown", "impact_pct": -5.0, "impact_money": -500.0}],
            by_country=[{"key": "unknown", "impact_pct": -5.0, "impact_money": -500.0}],
            warnings=["missing_metadata:UNK"],
        ),
        _load_current_positions=lambda: [],
        _get_cash_like_weight_pct=lambda positions: 12.0,
    )
    service = StressFragilityService(catalog, scenario_service)

    result = service.calculate("em_deterioration")

    assert result["metadata"]["confidence"] == "medium"
