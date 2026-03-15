import pytest

from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    DataQualityFlags,
    ExpectedReturnBucketItem,
    ExpectedReturnResult,
    FactorExposureItem,
    FactorExposureResult,
    NormalizedPosition,
    RiskContributionItem,
    RiskContributionResult,
    RecommendationSignal,
    ScenarioAnalysisResult,
    ScenarioAssetImpact,
    ScenarioGroupImpact,
    StressFragilityResult,
)


def test_analytics_metadata_validates_confidence():
    with pytest.raises(ValueError, match="confidence"):
        AnalyticsMetadata(
            methodology="proxy",
            data_basis="portfolio",
            limitations="heuristic",
            confidence="invalid",
        )


def test_data_quality_flags_warnings_are_not_shared():
    first = DataQualityFlags()
    second = DataQualityFlags()

    first.warnings.append("missing_metadata")

    assert second.warnings == []


def test_normalized_position_serializes_to_dict():
    position = NormalizedPosition(
        symbol="AAPL",
        description="Apple",
        market_value=1000.0,
        weight_pct=12.5,
        sector="Tecnologia",
        country="USA",
        asset_type="CEDEAR",
        strategic_bucket="Growth",
        patrimonial_type="Equity",
        currency="ARS",
        gain_pct=5.2,
        gain_money=50.0,
    )

    payload = position.to_dict()

    assert payload["symbol"] == "AAPL"
    assert payload["weight_pct"] == 12.5
    assert payload["sector"] == "Tecnologia"


def test_risk_contribution_result_serializes_nested_items():
    metadata = AnalyticsMetadata(
        methodology="peso * volatilidad_proxy",
        data_basis="current_positions",
        limitations="uses fallback volatility proxies",
        confidence="medium",
        warnings=["used_fallback"],
    )
    item = RiskContributionItem(
        symbol="AAPL",
        weight_pct=20.0,
        volatility_proxy=0.32,
        risk_score=6.4,
        contribution_pct=40.0,
        sector="Tecnologia",
        country="USA",
        asset_type="Equity",
        used_volatility_fallback=True,
    )
    result = RiskContributionResult(
        items=[item],
        by_sector=[],
        by_country=[],
        by_asset_type=[],
        top_contributors=[item],
        metadata=metadata,
    )

    payload = result.to_dict()

    assert payload["items"][0]["symbol"] == "AAPL"
    assert payload["items"][0]["used_volatility_fallback"] is True
    assert payload["metadata"]["warnings"] == ["used_fallback"]


def test_scenario_and_stress_results_serialize_consistently():
    metadata = AnalyticsMetadata(
        methodology="heuristic scenario mapping",
        data_basis="current_positions",
        limitations="not calibrated",
        confidence="medium",
    )
    asset = ScenarioAssetImpact(
        symbol="SPY",
        market_value=1000.0,
        estimated_impact_pct=-10.0,
        estimated_impact_money=-100.0,
        transmission_channel="equity_global",
    )
    sector = ScenarioGroupImpact(
        key="Tecnologia",
        impact_pct=-5.0,
        impact_money=-50.0,
    )
    scenario = ScenarioAnalysisResult(
        scenario_key="spy_down_10",
        total_impact_pct=-4.5,
        total_impact_money=-450.0,
        by_asset=[asset],
        by_sector=[sector],
        by_country=[],
        top_negative_contributors=[asset],
        metadata=metadata,
    )
    stress = StressFragilityResult(
        scenario_key="usa_crash_severe",
        fragility_score=72.5,
        total_loss_pct=-12.0,
        total_loss_money=-1200.0,
        vulnerable_assets=[asset],
        vulnerable_sectors=[sector],
        vulnerable_countries=[],
        metadata=metadata,
    )

    scenario_payload = scenario.to_dict()
    stress_payload = stress.to_dict()

    assert scenario_payload["by_asset"][0]["transmission_channel"] == "equity_global"
    assert stress_payload["fragility_score"] == 72.5


def test_factor_exposure_result_supports_unknown_assets():
    metadata = AnalyticsMetadata(
        methodology="explicit mapping + fallback",
        data_basis="current_positions",
        limitations="unknown assets remain unclassified",
        confidence="medium",
    )
    result = FactorExposureResult(
        factors=[
            FactorExposureItem(factor="growth", exposure_pct=35.0, confidence="high"),
            FactorExposureItem(factor="defensive", exposure_pct=10.0, confidence="medium"),
        ],
        dominant_factor="growth",
        underrepresented_factors=["dividend"],
        unknown_assets=["AL30"],
        metadata=metadata,
    )

    payload = result.to_dict()

    assert payload["dominant_factor"] == "growth"
    assert payload["unknown_assets"] == ["AL30"]
    assert payload["factors"][0]["confidence"] == "high"


def test_expected_return_result_requires_basis_reference():
    metadata = AnalyticsMetadata(
        methodology="bucket baseline",
        data_basis="portfolio_structure",
        limitations="simple reference model",
        confidence="low",
    )

    with pytest.raises(ValueError, match="basis_reference"):
        ExpectedReturnResult(
            expected_return_pct=8.0,
            real_expected_return_pct=1.5,
            basis_reference="",
            by_bucket=[
                ExpectedReturnBucketItem(
                    bucket_key="usa",
                    label="CEDEAR USA",
                    weight_pct=40.0,
                    expected_return_pct=10.0,
                    basis_reference="SPY",
                )
            ],
            metadata=metadata,
        )


def test_recommendation_signal_validates_required_fields():
    with pytest.raises(ValueError, match="signal_key"):
        RecommendationSignal(
            signal_key="",
            severity="medium",
            title="Signal",
            description="Desc",
            affected_scope="portfolio",
        )
