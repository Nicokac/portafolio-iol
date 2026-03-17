from apps.core.services.analytics_v2.schemas import NormalizedPosition
from apps.core.services.candidate_asset_ranking_service import CandidateAssetRankingService


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


def make_position(
    symbol,
    *,
    market_value,
    weight_pct,
    sector,
    country,
    asset_type,
    strategic_bucket="",
    patrimonial_type="",
    currency="USD",
):
    return NormalizedPosition(
        symbol=symbol,
        description=f"Activo {symbol}",
        market_value=market_value,
        weight_pct=weight_pct,
        sector=sector,
        country=country,
        asset_type=asset_type,
        strategic_bucket=strategic_bucket,
        patrimonial_type=patrimonial_type,
        currency=currency,
    )


def build_service(
    *,
    monthly_plan=None,
    positions=None,
    factor_result=None,
    stress_result=None,
    scenarios=None,
    risk_result=None,
    covariance_result=None,
):
    return CandidateAssetRankingService(
        monthly_allocation_loader=lambda capital_amount: monthly_plan
        or {
            "capital_total": int(capital_amount),
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "score": 4.8},
                {"bucket": "global_index", "label": "Indice global", "score": 3.6},
            ],
            "avoided_blocks": [{"bucket": "tech_growth", "label": "Tecnologia / growth"}],
        },
        positions_loader=lambda: positions
        if positions is not None
        else [
            make_position(
                "KO",
                market_value=1200,
                weight_pct=6.0,
                sector="Consumo defensivo",
                country="USA",
                asset_type="equity",
                strategic_bucket="Dividend",
                patrimonial_type="Dividend",
            ),
            make_position(
                "PEP",
                market_value=1100,
                weight_pct=5.5,
                sector="Consumo defensivo",
                country="USA",
                asset_type="equity",
                strategic_bucket="Defensive",
                patrimonial_type="Dividend",
            ),
            make_position(
                "SPY",
                market_value=3000,
                weight_pct=12.0,
                sector="Indice",
                country="USA",
                asset_type="equity",
                strategic_bucket="Index",
                patrimonial_type="Growth",
            ),
            make_position(
                "AAPL",
                market_value=2800,
                weight_pct=11.0,
                sector="Tecnologia",
                country="USA",
                asset_type="equity",
                strategic_bucket="Growth",
                patrimonial_type="Growth",
            ),
        ],
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
                "fragility_score": 70.0,
                "total_loss_pct": -14.0,
                "vulnerable_assets": [{"symbol": "AAPL"}],
                "metadata": {"warnings": []},
            }
        ),
        scenario_analysis_service=DummyScenarioAnalysisService(
            scenarios
            or {
                "tech_shock": {"top_negative_contributors": [{"symbol": "AAPL"}]},
                "argentina_stress": {"top_negative_contributors": []},
            }
        ),
        risk_contribution_service=DummyRiskContributionService(
            risk_result
            or {
                "items": [
                    {"symbol": "KO", "contribution_pct": 4.2},
                    {"symbol": "PEP", "contribution_pct": 5.1},
                    {"symbol": "SPY", "contribution_pct": 9.0},
                    {"symbol": "AAPL", "contribution_pct": 21.0},
                ]
            }
        ),
        covariance_risk_contribution_service=DummyCovarianceRiskContributionService(
            covariance_result or {"model_variant": "mvp_proxy"}
        ),
    )


def test_build_ranking_returns_ranked_candidates_by_block():
    service = build_service()

    result = service.build_ranking(600000)

    assert result["capital_total"] == 600000
    assert result["candidate_assets_count"] >= 2
    assert result["candidate_assets"]
    assert result["candidate_assets"][0]["block"] == "defensive"
    assert result["candidate_assets"][0]["rank"] == 1
    assert result["candidate_assets"][0]["asset"] in {"KO", "PEP"}
    assert "defensive_sector_match" in result["candidate_assets"][0]["reasons"]
    assert [item["score"] for item in result["by_block"][0]["candidates"]] == sorted(
        [item["score"] for item in result["by_block"][0]["candidates"]],
        reverse=True,
    )
    assert result["explanation"]


def test_build_ranking_penalizes_high_risk_and_stress_assets():
    service = build_service()

    result = service.build_ranking(600000)

    assets = {item["asset"]: item for item in result["candidate_assets"]}
    assert "AAPL" not in assets
    assert assets["KO"]["score"] > assets["SPY"]["score"]


def test_build_ranking_handles_single_asset_portfolio():
    service = build_service(
        monthly_plan={
            "capital_total": 600000,
            "recommended_blocks": [{"bucket": "defensive", "label": "Defensive / resiliente", "score": 4.8}],
            "avoided_blocks": [],
        },
        positions=[
            make_position(
                "KO",
                market_value=1200,
                weight_pct=6.0,
                sector="Consumo defensivo",
                country="USA",
                asset_type="equity",
                strategic_bucket="Dividend",
                patrimonial_type="Dividend",
            )
        ],
    )

    result = service.build_ranking(600000)

    assert result["candidate_assets_count"] == 1
    assert result["candidate_assets"][0]["asset"] == "KO"
    assert result["candidate_assets"][0]["rank"] == 1


def test_build_ranking_returns_empty_when_no_positions_exist():
    service = build_service(positions=[])

    result = service.build_ranking(600000)

    assert result["candidate_assets_count"] == 0
    assert result["candidate_assets"] == []
    assert "No hay activos elegibles" in result["explanation"]


def test_build_ranking_returns_empty_when_all_candidates_are_penalized():
    service = build_service(
        monthly_plan={
            "capital_total": 600000,
            "recommended_blocks": [{"bucket": "defensive", "label": "Defensive / resiliente", "score": 4.8}],
            "avoided_blocks": [
                {"bucket": "tech_growth"},
                {"bucket": "argentina_local"},
                {"bucket": "local_crisis"},
            ],
        },
        positions=[
            make_position(
                "TXAR",
                market_value=1800,
                weight_pct=9.0,
                sector="Tecnologia",
                country="Argentina",
                asset_type="equity",
                strategic_bucket="Growth",
                patrimonial_type="Growth",
            )
        ],
        factor_result={"underrepresented_factors": [], "dominant_factor": "growth", "metadata": {"warnings": []}},
        stress_result={
            "scenario_key": "local_crisis_severe",
            "fragility_score": 90.0,
            "total_loss_pct": -20.0,
            "vulnerable_assets": [{"symbol": "TXAR"}],
            "metadata": {"warnings": []},
        },
        scenarios={
            "tech_shock": {"top_negative_contributors": [{"symbol": "TXAR"}]},
            "argentina_stress": {"top_negative_contributors": [{"symbol": "TXAR"}]},
        },
        risk_result={"items": [{"symbol": "TXAR", "contribution_pct": 28.0}]},
    )

    result = service.build_ranking(600000)

    assert result["candidate_assets_count"] == 0
    assert result["candidate_assets"] == []
    assert result["by_block"][0]["candidates"] == []
