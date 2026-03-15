from __future__ import annotations

from apps.core.services.analytics_v2.factor_catalog import FACTOR_CATALOG
from apps.core.services.analytics_v2.factor_classifier_service import FactorClassifierService
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    FactorExposureItem,
    FactorExposureResult,
    RecommendationSignal,
)
from apps.core.services.analytics_v2.scenario_analysis_service import ScenarioAnalysisService
from apps.core.services.analytics_v2.helpers import safe_percentage


class FactorExposureService:
    """Agrega exposicion factorial MVP sobre posiciones clasificadas."""

    UNDERREPRESENTED_THRESHOLD = 5.0
    GROWTH_EXCESS_THRESHOLD = 45.0
    DEFENSIVE_MIN_THRESHOLD = 8.0
    DIVIDEND_MIN_THRESHOLD = 8.0
    FACTOR_CONCENTRATION_THRESHOLD = 55.0

    def __init__(
        self,
        classifier_service: FactorClassifierService | None = None,
        positions_loader: ScenarioAnalysisService | None = None,
    ):
        self.classifier_service = classifier_service or FactorClassifierService()
        self.positions_loader = positions_loader or ScenarioAnalysisService()

    def calculate(self) -> dict:
        positions = self._load_current_positions()
        factor_keys = [entry.definition.factor_key for entry in FACTOR_CATALOG]
        if not positions:
            return FactorExposureResult(
                factors=[],
                dominant_factor=None,
                underrepresented_factors=factor_keys,
                unknown_assets=[],
                metadata=AnalyticsMetadata(
                    methodology="proxy factor aggregation over classified current positions",
                    data_basis="classified_positions_market_value",
                    limitations="No current positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ),
            ).to_dict()

        classified_market_value = 0.0
        grouped_market_value = {factor_key: 0.0 for factor_key in factor_keys}
        grouped_confidences: dict[str, list[str]] = {factor_key: [] for factor_key in factor_keys}
        unknown_assets: list[str] = []
        unknown_market_value = 0.0
        warnings: list[str] = []

        for position in positions:
            classification = self.classifier_service.classify_position(position)
            factor = classification["factor"]
            source = classification["source"]
            if factor:
                grouped_market_value[factor] += float(position.market_value)
                grouped_confidences[factor].append(classification["confidence"])
                classified_market_value += float(position.market_value)
                if source != "explicit_symbol_map":
                    warnings.append(f"used_factor_fallback:{position.symbol}:{source}")
            else:
                unknown_assets.append(position.symbol)
                unknown_market_value += float(position.market_value)
                warnings.append(f"unknown_factor_classification:{position.symbol}")

        factor_items: list[FactorExposureItem] = []
        for factor_key in factor_keys:
            market_value = grouped_market_value[factor_key]
            if market_value <= 0 or classified_market_value <= 0:
                exposure_pct = 0.0
                confidence = "low"
            else:
                exposure_pct = round(safe_percentage(market_value, classified_market_value), 2)
                confidence = self._derive_factor_confidence(grouped_confidences[factor_key])
            factor_items.append(
                FactorExposureItem(
                    factor=factor_key,
                    exposure_pct=exposure_pct,
                    confidence=confidence,
                )
            )

        dominant_factor = None
        non_zero_factors = [item for item in factor_items if item.exposure_pct > 0]
        if non_zero_factors:
            dominant_factor = max(non_zero_factors, key=lambda item: item.exposure_pct).factor

        underrepresented_factors = [
            item.factor
            for item in factor_items
            if item.exposure_pct < self.UNDERREPRESENTED_THRESHOLD
        ]

        unknown_ratio = safe_percentage(unknown_market_value, classified_market_value + unknown_market_value)
        confidence = self._derive_result_confidence(unknown_ratio)
        if unknown_assets:
            warnings.append(f"unknown_assets_count:{len(unknown_assets)}")

        return FactorExposureResult(
            factors=factor_items,
            dominant_factor=dominant_factor,
            underrepresented_factors=underrepresented_factors,
            unknown_assets=unknown_assets,
            metadata=AnalyticsMetadata(
                methodology=(
                    "explicit symbol mapping with fallback by strategic bucket and sector; "
                    "factor exposures are aggregated over classified positions only"
                ),
                data_basis="classified_positions_market_value",
                limitations=(
                    "Assets without reliable proxy remain in unknown_assets and are excluded "
                    "from factor exposure percentages."
                ),
                confidence=confidence,
                warnings=warnings,
            ),
        ).to_dict()

    def build_recommendation_signals(self) -> list[dict]:
        result = self.calculate()
        factors = {item["factor"]: item for item in result.get("factors", [])}
        if not factors:
            return []

        signals: list[RecommendationSignal] = []

        growth_pct = float(factors.get("growth", {}).get("exposure_pct", 0.0) or 0.0)
        if growth_pct >= self.GROWTH_EXCESS_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="factor_growth_excess",
                    severity="high" if growth_pct >= self.FACTOR_CONCENTRATION_THRESHOLD else "medium",
                    title="Exceso de sesgo growth",
                    description="La cartera muestra una exposicion growth elevada frente al resto de factores.",
                    affected_scope="factor",
                    evidence={
                        "factor": "growth",
                        "exposure_pct": round(growth_pct, 2),
                    },
                )
            )

        defensive_pct = float(factors.get("defensive", {}).get("exposure_pct", 0.0) or 0.0)
        if defensive_pct < self.DEFENSIVE_MIN_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="factor_defensive_gap",
                    severity="medium",
                    title="Falta de factor defensivo",
                    description="La exposicion defensiva es baja para amortiguar shocks o fases mas conservadoras del mercado.",
                    affected_scope="factor",
                    evidence={
                        "factor": "defensive",
                        "exposure_pct": round(defensive_pct, 2),
                        "threshold_pct": self.DEFENSIVE_MIN_THRESHOLD,
                    },
                )
            )

        dividend_pct = float(factors.get("dividend", {}).get("exposure_pct", 0.0) or 0.0)
        if dividend_pct < self.DIVIDEND_MIN_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="factor_dividend_gap",
                    severity="medium",
                    title="Falta de sesgo dividend",
                    description="La cartera tiene poca exposicion a activos orientados a renta recurrente o dividendos.",
                    affected_scope="factor",
                    evidence={
                        "factor": "dividend",
                        "exposure_pct": round(dividend_pct, 2),
                        "threshold_pct": self.DIVIDEND_MIN_THRESHOLD,
                    },
                )
            )

        dominant_factor = result.get("dominant_factor")
        dominant_factor_pct = float(factors.get(dominant_factor, {}).get("exposure_pct", 0.0) or 0.0)
        if dominant_factor and dominant_factor_pct >= self.FACTOR_CONCENTRATION_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="factor_concentration_excessive",
                    severity="high",
                    title="Concentracion factorial excesiva",
                    description="Un solo factor domina una parte demasiado alta de la exposicion clasificada.",
                    affected_scope="factor",
                    evidence={
                        "factor": dominant_factor,
                        "exposure_pct": round(dominant_factor_pct, 2),
                    },
                )
            )

        return [signal.to_dict() for signal in signals]

    def _load_current_positions(self):
        return self.positions_loader._load_current_positions()

    @staticmethod
    def _derive_factor_confidence(confidences: list[str]) -> str:
        if not confidences:
            return "low"
        if all(confidence == "high" for confidence in confidences):
            return "high"
        if any(confidence == "medium" for confidence in confidences):
            return "medium"
        return "low"

    @staticmethod
    def _derive_result_confidence(unknown_ratio: float) -> str:
        if unknown_ratio > 35.0:
            return "low"
        if unknown_ratio > 0:
            return "medium"
        return "high"
