from apps.dashboard.analytics_v2_builders import (
    build_expected_return_detail,
    build_factor_exposure_detail,
    build_risk_contribution_detail,
    resolve_active_risk_contribution_result,
)


class DummyExplanationService:
    def build_risk_contribution_explanation(self, result):
        return f"risk:{result['metadata']['confidence']}"

    def build_factor_exposure_explanation(self, result):
        return f"factor:{result['metadata']['confidence']}"

    def build_expected_return_explanation(self, result):
        return f"expected:{result['metadata']['confidence']}"


def test_resolve_active_risk_contribution_result_prefers_covariance_variant():
    class DummyBaseRiskService:
        def calculate(self):
            return {"model_variant": "mvp_proxy"}

    class DummyCovarianceRiskService:
        def calculate(self):
            return {"model_variant": "covariance_aware"}

    resolved = resolve_active_risk_contribution_result(
        base_risk_service=DummyBaseRiskService(),
        covariance_risk_service=DummyCovarianceRiskService(),
    )

    assert resolved["active_result"]["model_variant"] == "covariance_aware"


def test_build_risk_contribution_detail_adds_interpretation_and_deltas():
    resolved = {
        "active_result": {
            "by_sector": [{"key": "Tech", "weight_pct": 10.0, "contribution_pct": 14.0}],
            "by_country": [{"key": "USA", "weight_pct": 20.0, "contribution_pct": 18.0}],
            "items": [
                {
                    "symbol": "AAPL",
                    "sector": "Tech",
                    "country": "USA",
                    "asset_type": "CEDEAR",
                    "weight_pct": 10.0,
                    "volatility_proxy": 0.2,
                    "risk_score": 12.0,
                    "contribution_pct": 14.0,
                    "used_volatility_fallback": False,
                }
            ],
            "top_contributors": [{"symbol": "AAPL"}],
            "metadata": {"confidence": "high", "warnings": []},
        },
        "covariance_result": {
            "model_variant": "covariance_aware",
            "covariance_observations": 120,
            "coverage_pct": 88.0,
            "portfolio_volatility_proxy": 19.4,
            "covered_symbols": ["AAPL"],
            "excluded_symbols": [],
        },
    }

    detail = build_risk_contribution_detail(
        resolved=resolved,
        explanation_service=DummyExplanationService(),
    )

    assert detail["interpretation"] == "risk:high"
    assert detail["items"][0]["risk_vs_weight_delta"] == 4.0
    assert detail["by_country"][0]["risk_vs_weight_delta"] == -2.0


def test_build_factor_exposure_detail_ranks_rows_and_counts_unknown_assets():
    detail = build_factor_exposure_detail(
        factor_result={
            "factors": [
                {"factor": "quality", "exposure_pct": 11.0, "confidence": "high"},
                {"factor": "value", "exposure_pct": 4.0, "confidence": "medium"},
            ],
            "dominant_factor": "quality",
            "unknown_assets": ["XYZ"],
            "underrepresented_factors": ["size"],
            "metadata": {"confidence": "medium", "warnings": ["partial_map"]},
        },
        explanation_service=DummyExplanationService(),
    )

    assert detail["factors"][0]["factor"] == "quality"
    assert detail["unknown_assets_count"] == 1
    assert detail["interpretation"] == "factor:medium"


def test_build_expected_return_detail_picks_main_warning_and_dominant_bucket():
    detail = build_expected_return_detail(
        result={
            "expected_return_pct": 15.0,
            "real_expected_return_pct": 2.3,
            "basis_reference": "weighted_bucket_baseline_current_positions",
            "by_bucket": [
                {"bucket_key": "equity", "label": "Equity", "weight_pct": 60.0, "expected_return_pct": 20.0},
                {"bucket_key": "fixed", "label": "Fixed", "weight_pct": 40.0, "expected_return_pct": 8.0},
            ],
            "metadata": {"confidence": "high", "warnings": ["missing_badlar"]},
        },
        explanation_service=DummyExplanationService(),
    )

    assert detail["dominant_bucket"]["bucket_key"] == "equity"
    assert detail["main_warning"] == "missing_badlar"
    assert detail["interpretation"] == "expected:high"
