from apps.core.services.analytics_v2.analytics_explanation_service import AnalyticsExplanationService


def test_build_risk_contribution_explanation_mentions_top_assets_argentina_and_model():
    result = {
        "top_contributors": [
            {"symbol": "SPY", "contribution_pct": 22.33},
            {"symbol": "NEM", "contribution_pct": 20.76},
        ],
        "by_country": [
            {"key": "Argentina", "weight_pct": 30.0, "contribution_pct": 12.0},
            {"key": "USA", "weight_pct": 50.0, "contribution_pct": 70.0},
        ],
        "model_variant": "mvp_proxy",
        "metadata": {"confidence": "high"},
    }

    text = AnalyticsExplanationService().build_risk_contribution_explanation(result)

    assert "SPY y NEM" in text
    assert "Argentina representa una parte importante del patrimonio" in text
    assert "mvp_proxy" in text
    assert "Confianza del resultado: high." in text


def test_build_scenario_analysis_explanation_mentions_worst_scenario_and_sector():
    result = {
        "worst_scenario": {
            "label": "Tech Shock",
            "total_impact_pct": -8.4,
            "by_sector": [
                {"key": "Tecnologia", "impact_pct": -5.1},
                {"key": "Defensivo", "impact_pct": -1.0},
            ],
            "top_negative_contributors": [{"symbol": "NVDA"}],
        }
    }

    text = AnalyticsExplanationService().build_scenario_analysis_explanation(result)

    assert "Tech Shock" in text
    assert "-8.40%" in text
    assert "Tecnologia" in text


def test_build_factor_exposure_explanation_mentions_dominant_factor_and_unknown_assets():
    result = {
        "dominant_factor": "growth",
        "factors": [
            {"factor": "growth", "exposure_pct": 35.8},
            {"factor": "defensive", "exposure_pct": 4.0},
        ],
        "unknown_assets": ["GD30", "AL30"],
    }

    text = AnalyticsExplanationService().build_factor_exposure_explanation(result)

    assert "factor growth" in text
    assert "35.80%" in text
    assert "2 activos" in text


def test_explanation_service_handles_missing_data_without_breaking():
    service = AnalyticsExplanationService()

    assert "No hay datos suficientes" in service.build_risk_contribution_explanation({})
    assert "No hay datos suficientes" in service.build_scenario_analysis_explanation({})
    assert "No hay datos suficientes" in service.build_factor_exposure_explanation({})
