from __future__ import annotations

from apps.core.services.analytics_v2.helpers import safe_percentage
from apps.core.services.analytics_v2.scenario_analysis_service import ScenarioAnalysisService
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    ScenarioAssetImpact,
    ScenarioGroupImpact,
    StressFragilityResult,
)
from apps.core.services.analytics_v2.stress_catalog import StressCatalogService


class StressFragilityService:
    """Calcula fragilidad simple combinando escenarios extremos cerrados del MVP."""

    TOP3_VULNERABILITY_WEIGHT = 0.4
    LOSS_WEIGHT = 4.0
    LOW_LIQUIDITY_THRESHOLD = 10.0
    LOW_LIQUIDITY_PENALTY = 10.0
    HIGH_LIQUIDITY_THRESHOLD = 25.0
    HIGH_LIQUIDITY_CREDIT = 5.0

    def __init__(
        self,
        stress_catalog_service: StressCatalogService | None = None,
        scenario_analysis_service: ScenarioAnalysisService | None = None,
    ):
        self.stress_catalog_service = stress_catalog_service or StressCatalogService()
        self.scenario_analysis_service = scenario_analysis_service or ScenarioAnalysisService()

    def calculate(self, stress_key: str) -> dict:
        stress = self.stress_catalog_service.require_stress(stress_key)
        scenario_keys = stress["scenario_keys"]
        if not scenario_keys:
            return StressFragilityResult(
                scenario_key=stress_key,
                fragility_score=0.0,
                total_loss_pct=0.0,
                total_loss_money=0.0,
                vulnerable_assets=[],
                vulnerable_sectors=[],
                vulnerable_countries=[],
                metadata=AnalyticsMetadata(
                    methodology="combined extreme stress over scenario analysis outputs",
                    data_basis="current_positions_market_value",
                    limitations="The stress does not define scenario_keys",
                    confidence="low",
                    warnings=["empty_stress_definition"],
                ),
            ).to_dict()

        scenario_results = [self.scenario_analysis_service.analyze(scenario_key) for scenario_key in scenario_keys]
        if all(result["metadata"]["warnings"] == ["empty_portfolio"] for result in scenario_results):
            return StressFragilityResult(
                scenario_key=stress_key,
                fragility_score=0.0,
                total_loss_pct=0.0,
                total_loss_money=0.0,
                vulnerable_assets=[],
                vulnerable_sectors=[],
                vulnerable_countries=[],
                metadata=AnalyticsMetadata(
                    methodology="combined extreme stress over scenario analysis outputs",
                    data_basis="current_positions_market_value",
                    limitations="No current positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ),
            ).to_dict()

        combined_assets = self._combine_asset_impacts(scenario_results)
        combined_sectors = self._combine_group_impacts(scenario_results, "by_sector")
        combined_countries = self._combine_group_impacts(scenario_results, "by_country")

        total_loss_money = round(sum(item.estimated_impact_money for item in combined_assets), 2)
        total_basis = sum(item.market_value for item in combined_assets)
        total_loss_pct = round(safe_percentage(total_loss_money, total_basis), 2)

        vulnerable_assets = sorted(combined_assets, key=lambda item: item.estimated_impact_money)[:5]
        vulnerable_sectors = sorted(combined_sectors, key=lambda item: item.impact_money)[:5]
        vulnerable_countries = sorted(combined_countries, key=lambda item: item.impact_money)[:5]

        top3_loss_share = self._top3_loss_share(vulnerable_assets, total_loss_money)
        liquidity_pct = self.scenario_analysis_service._get_cash_like_weight_pct(  # noqa: SLF001
            self.scenario_analysis_service._load_current_positions()  # noqa: SLF001
        )
        fragility_score = self._calculate_fragility_score(
            total_loss_pct=total_loss_pct,
            top3_loss_share=top3_loss_share,
            liquidity_pct=liquidity_pct,
        )

        warnings: list[str] = []
        for result in scenario_results:
            warnings.extend(result["metadata"]["warnings"])
        if stress.get("legacy_mapping_keys"):
            warnings.append(f"legacy_mappings:{','.join(stress['legacy_mapping_keys'])}")

        return StressFragilityResult(
            scenario_key=stress_key,
            fragility_score=fragility_score,
            total_loss_pct=total_loss_pct,
            total_loss_money=total_loss_money,
            vulnerable_assets=vulnerable_assets,
            vulnerable_sectors=vulnerable_sectors,
            vulnerable_countries=vulnerable_countries,
            metadata=AnalyticsMetadata(
                methodology="combined scenario analysis outputs with simple fragility scoring",
                data_basis="current_positions_market_value",
                limitations=(
                    "Stress results are heuristic and combine closed scenario shocks. "
                    "Fragility score is rule-based, not probabilistic."
                ),
                confidence=self._derive_confidence(warnings),
                warnings=self._dedupe(warnings),
            ),
        ).to_dict()

    @staticmethod
    def _combine_asset_impacts(scenario_results: list[dict]) -> list[ScenarioAssetImpact]:
        combined: dict[str, dict] = {}
        for result in scenario_results:
            for item in result["by_asset"]:
                bucket = combined.setdefault(
                    item["symbol"],
                    {
                        "market_value": float(item["market_value"]),
                        "estimated_impact_money": 0.0,
                        "estimated_impact_pct": 0.0,
                        "transmission_channels": [],
                    },
                )
                bucket["estimated_impact_money"] += float(item["estimated_impact_money"])
                bucket["transmission_channels"].append(item["transmission_channel"])

        assets: list[ScenarioAssetImpact] = []
        for symbol, payload in combined.items():
            market_value = payload["market_value"]
            impact_money = payload["estimated_impact_money"]
            impact_pct = safe_percentage(impact_money, market_value)
            assets.append(
                ScenarioAssetImpact(
                    symbol=symbol,
                    market_value=round(market_value, 2),
                    estimated_impact_pct=round(impact_pct, 2),
                    estimated_impact_money=round(impact_money, 2),
                    transmission_channel="+".join(payload["transmission_channels"]),
                )
            )
        return assets

    @staticmethod
    def _combine_group_impacts(scenario_results: list[dict], group_key: str) -> list[ScenarioGroupImpact]:
        combined: dict[str, float] = {}
        total_basis = 0.0
        if scenario_results:
            total_basis = sum(float(item["market_value"]) for item in scenario_results[0]["by_asset"])

        for result in scenario_results:
            for item in result[group_key]:
                key = item["key"]
                combined[key] = combined.get(key, 0.0) + float(item["impact_money"])

        groups: list[ScenarioGroupImpact] = []
        for key, impact_money in sorted(combined.items(), key=lambda pair: pair[1]):
            groups.append(
                ScenarioGroupImpact(
                    key=key,
                    impact_pct=round(safe_percentage(impact_money, total_basis), 2),
                    impact_money=round(impact_money, 2),
                )
            )
        return groups

    @staticmethod
    def _top3_loss_share(vulnerable_assets: list[ScenarioAssetImpact], total_loss_money: float) -> float:
        if total_loss_money >= 0:
            return 0.0
        top3_loss = sum(abs(item.estimated_impact_money) for item in vulnerable_assets[:3] if item.estimated_impact_money < 0)
        return safe_percentage(top3_loss, abs(total_loss_money))

    def _calculate_fragility_score(self, *, total_loss_pct: float, top3_loss_share: float, liquidity_pct: float) -> float:
        loss_component = abs(min(total_loss_pct, 0.0)) * self.LOSS_WEIGHT
        concentration_component = top3_loss_share * self.TOP3_VULNERABILITY_WEIGHT
        liquidity_adjustment = 0.0
        if liquidity_pct < self.LOW_LIQUIDITY_THRESHOLD:
            liquidity_adjustment += self.LOW_LIQUIDITY_PENALTY
        elif liquidity_pct >= self.HIGH_LIQUIDITY_THRESHOLD:
            liquidity_adjustment -= self.HIGH_LIQUIDITY_CREDIT
        return round(max(0.0, min(100.0, loss_component + concentration_component + liquidity_adjustment)), 2)

    @staticmethod
    def _derive_confidence(warnings: list[str]) -> str:
        if any("missing_metadata" in warning for warning in warnings):
            return "medium"
        return "high"

    @staticmethod
    def _dedupe(warnings: list[str]) -> list[str]:
        seen: list[str] = []
        for warning in warnings:
            if warning not in seen:
                seen.append(warning)
        return seen
