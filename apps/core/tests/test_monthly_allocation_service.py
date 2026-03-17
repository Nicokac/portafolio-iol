from decimal import Decimal

from apps.core.services.monthly_allocation_service import MonthlyAllocationService


class DummyExpectedReturnService:
    def __init__(self, result):
        self.result = result

    def calculate(self):
        return self.result


class DummyFactorExposureService:
    def __init__(self, result):
        self.result = result

    def calculate(self):
        return self.result


class DummyStressFragilityService:
    def __init__(self, result):
        self.result = result

    def calculate(self, stress_key):
        assert stress_key == "local_crisis_severe"
        return self.result


class DummyScenarioAnalysisService:
    def __init__(self, mapping):
        self.mapping = mapping

    def analyze(self, scenario_key):
        return self.mapping[scenario_key]


class DummyRiskContributionService:
    def __init__(self, result):
        self.result = result

    def calculate(self, lookback_days=90, top_n=5):
        assert top_n == 5
        return self.result


class DummyCovarianceRiskContributionService:
    def __init__(self, result):
        self.result = result

    def calculate(self, lookback_days=252, top_n=5):
        assert top_n == 5
        return self.result


def build_service(*, recommendations=None, factor_result=None, expected_return_result=None, stress_result=None, scenarios=None, risk_result=None, covariance_result=None):
    return MonthlyAllocationService(
        expected_return_service=DummyExpectedReturnService(
            expected_return_result
            or {
                "expected_return_pct": 18.0,
                "real_expected_return_pct": 2.0,
                "by_bucket": [
                    {
                        "bucket_key": "equity_beta",
                        "label": "Equity beta / CEDEAR",
                        "weight_pct": 50.0,
                        "expected_return_pct": 20.0,
                        "basis_reference": "benchmark:cedear_usa",
                    },
                    {
                        "bucket_key": "fixed_income_ar",
                        "label": "Renta fija AR",
                        "weight_pct": 25.0,
                        "expected_return_pct": 14.0,
                        "basis_reference": "benchmark:bonos_ar",
                    },
                ],
                "metadata": {"confidence": "high", "warnings": []},
            }
        ),
        factor_exposure_service=DummyFactorExposureService(
            factor_result
            or {
                "underrepresented_factors": ["defensive", "dividend"],
                "dominant_factor": "growth",
                "metadata": {"warnings": []},
            }
        ),
        stress_fragility_service=DummyStressFragilityService(
            stress_result
            or {
                "scenario_key": "local_crisis_severe",
                "fragility_score": 72.0,
                "total_loss_pct": -14.0,
                "vulnerable_countries": [{"key": "Argentina"}],
                "metadata": {"warnings": []},
            }
        ),
        scenario_analysis_service=DummyScenarioAnalysisService(
            scenarios
            or {
                "tech_shock": {"total_impact_pct": -9.0},
                "argentina_stress": {"total_impact_pct": -8.0},
            }
        ),
        risk_contribution_service=DummyRiskContributionService(
            risk_result
            or {
                "by_sector": [{"key": "Tecnologia", "contribution_pct": 40.0}],
                "by_country": [{"key": "Argentina", "contribution_pct": 48.0}],
                "metadata": {"warnings": []},
            }
        ),
        covariance_risk_contribution_service=DummyCovarianceRiskContributionService(
            covariance_result or {"model_variant": "mvp_proxy"}
        ),
        recommendation_loader=lambda: recommendations
        or [
            {"tipo": "analytics_v2_factor_defensive_gap"},
            {"tipo": "analytics_v2_factor_dividend_gap"},
            {"tipo": "analytics_v2_risk_concentration_tech"},
            {"tipo": "analytics_v2_risk_concentration_argentina"},
            {"tipo": "analytics_v2_expected_return_liquidity_drag"},
            {"tipo": "analytics_v2_stress_fragility_high"},
        ],
    )


def test_build_plan_returns_consistent_allocation_for_valid_capital():
    service = build_service()

    result = service.build_plan(Decimal("600000"))

    assert result["capital_total"] == 600000
    assert result["recommended_blocks_count"] >= 1
    assert sum(item["suggested_amount"] for item in result["recommended_blocks"]) == 600000
    assert result["explanation"]
    recommended_buckets = {item["bucket"] for item in result["recommended_blocks"]}
    assert "defensive" in recommended_buckets or "dividend" in recommended_buckets
    avoided_buckets = {item["bucket"] for item in result["avoided_blocks"]}
    assert "tech_growth" in avoided_buckets


def test_build_plan_does_not_recommend_penalized_fixed_income_block():
    service = build_service()

    result = service.build_plan(600000)

    recommended_buckets = {item["bucket"] for item in result["recommended_blocks"]}
    assert "fixed_income_ar" not in recommended_buckets


def test_build_plan_handles_zero_capital_gracefully():
    service = build_service()

    result = service.build_plan(0)

    assert result["capital_total"] == 0
    assert result["recommended_blocks"] == []
    assert result["recommended_blocks_count"] == 0
    assert result["warnings"] == ["invalid_capital"]


def test_build_plan_falls_back_to_liquidity_when_all_blocks_are_penalized():
    service = build_service(
        factor_result={"underrepresented_factors": [], "dominant_factor": None, "metadata": {"warnings": []}},
        expected_return_result={"expected_return_pct": None, "real_expected_return_pct": None, "by_bucket": [], "metadata": {"warnings": []}},
        stress_result={"scenario_key": "local_crisis_severe", "fragility_score": 80, "total_loss_pct": -18, "vulnerable_countries": [{"key": "Argentina"}], "metadata": {"warnings": []}},
        scenarios={
            "tech_shock": {"total_impact_pct": -10.0},
            "argentina_stress": {"total_impact_pct": -12.0},
        },
        recommendations=[
            {"tipo": "analytics_v2_expected_return_liquidity_drag"},
            {"tipo": "analytics_v2_risk_concentration_argentina"},
            {"tipo": "analytics_v2_risk_concentration_tech"},
        ],
        risk_result={
            "by_sector": [{"key": "Tecnologia", "contribution_pct": 55.0}],
            "by_country": [{"key": "Argentina", "contribution_pct": 60.0}],
            "metadata": {"warnings": []},
        },
    )

    result = service.build_plan(100000)

    assert result["recommended_blocks_count"] == 1
    assert result["recommended_blocks"][0]["bucket"] == "liquidity_ars"
    assert result["recommended_blocks"][0]["suggested_amount"] == 100000


def test_build_plan_degrades_with_partial_payloads():
    service = build_service(
        factor_result={},
        expected_return_result={"by_bucket": [], "metadata": {}},
        stress_result={"scenario_key": "local_crisis_severe", "vulnerable_countries": [], "metadata": {}},
        scenarios={"tech_shock": {}, "argentina_stress": {}},
        recommendations=[],
        risk_result={"by_sector": [], "by_country": [], "metadata": {}},
    )

    result = service.build_plan("600000")

    assert result["capital_total"] == 600000
    assert sum(item["suggested_amount"] for item in result["recommended_blocks"]) == 600000
    assert result["explanation"]
