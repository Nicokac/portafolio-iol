from __future__ import annotations

from decimal import Decimal
from typing import Callable

from apps.core.services.analytics_v2 import (
    CovarianceAwareRiskContributionService,
    FactorExposureService,
    RiskContributionService,
    ScenarioAnalysisService,
    StressFragilityService,
)
from apps.core.services.analytics_v2.schemas import NormalizedPosition
from apps.core.services.monthly_allocation_service import MonthlyAllocationService


class CandidateAssetRankingService:
    """Rankea activos ya presentes en cartera para reforzar bloques recomendados del aporte mensual."""

    MAX_CANDIDATES_PER_BLOCK = 5

    def __init__(
        self,
        *,
        monthly_allocation_loader: Callable[[Decimal | int | float | str], dict] | None = None,
        positions_loader: Callable[[], list[NormalizedPosition]] | None = None,
        factor_exposure_service: FactorExposureService | None = None,
        stress_fragility_service: StressFragilityService | None = None,
        scenario_analysis_service: ScenarioAnalysisService | None = None,
        risk_contribution_service: RiskContributionService | None = None,
        covariance_risk_contribution_service: CovarianceAwareRiskContributionService | None = None,
    ):
        self.monthly_allocation_loader = monthly_allocation_loader or MonthlyAllocationService().build_plan
        self.factor_exposure_service = factor_exposure_service or FactorExposureService()
        self.stress_fragility_service = stress_fragility_service or StressFragilityService()
        self.scenario_analysis_service = scenario_analysis_service or ScenarioAnalysisService()
        self.risk_contribution_service = risk_contribution_service or RiskContributionService()
        self.covariance_risk_contribution_service = (
            covariance_risk_contribution_service or CovarianceAwareRiskContributionService()
        )
        self.positions_loader = positions_loader or self.scenario_analysis_service._load_current_positions  # noqa: SLF001

    def build_ranking(self, capital_amount: Decimal | int | float | str = 600000) -> dict:
        monthly_plan = self.monthly_allocation_loader(capital_amount)
        positions = self.positions_loader() or []
        if not positions:
            return self._empty_result(monthly_plan, "No hay activos elegibles en cartera para rankear candidatos.")

        recommended_blocks = monthly_plan.get("recommended_blocks", [])
        if not recommended_blocks:
            return self._empty_result(monthly_plan, "No hay bloques recomendados para derivar candidatos de compra.")

        analytics = self._load_analytics()
        flat_candidates = []
        by_block = []

        for block_index, block in enumerate(recommended_blocks, start=1):
            bucket = str(block.get("bucket") or "").strip()
            block_candidates = []
            for position in positions:
                if not self._position_matches_block(position, bucket):
                    continue
                score, reasons = self._score_candidate(position, bucket, monthly_plan, analytics)
                if score <= 0:
                    continue
                block_candidates.append(
                    {
                        "asset": position.symbol,
                        "block": bucket,
                        "block_label": block.get("label", bucket),
                        "score": round(score, 2),
                        "reasons": reasons,
                        "main_reason": reasons[0] if reasons else "block_match",
                        "market_value": position.market_value,
                    }
                )

            sorted_candidates = sorted(
                block_candidates,
                key=lambda item: (-float(item["score"]), item["market_value"], item["asset"]),
            )[: self.MAX_CANDIDATES_PER_BLOCK]

            ranked_candidates = [
                {
                    **item,
                    "rank": index,
                    "block_rank": block_index,
                }
                for index, item in enumerate(sorted_candidates, start=1)
            ]
            by_block.append(
                {
                    "block": bucket,
                    "label": block.get("label", bucket),
                    "score": block.get("score"),
                    "candidates": ranked_candidates,
                }
            )
            flat_candidates.extend(ranked_candidates)

        explanation = self._build_explanation(flat_candidates, monthly_plan)
        return {
            "capital_total": monthly_plan.get("capital_total", 0),
            "candidate_assets_count": len(flat_candidates),
            "candidate_assets": flat_candidates,
            "by_block": by_block,
            "explanation": explanation,
        }

    def _load_analytics(self) -> dict:
        covariance_result = self.covariance_risk_contribution_service.calculate(top_n=5)
        if covariance_result.get("model_variant") == "covariance_aware":
            risk_result = covariance_result
        else:
            risk_result = self.risk_contribution_service.calculate(top_n=5)

        return {
            "factor_result": self.factor_exposure_service.calculate(),
            "stress_result": self.stress_fragility_service.calculate("local_crisis_severe"),
            "tech_scenario": self.scenario_analysis_service.analyze("tech_shock"),
            "argentina_scenario": self.scenario_analysis_service.analyze("argentina_stress"),
            "risk_result": risk_result,
        }

    def _score_candidate(self, position: NormalizedPosition, bucket: str, monthly_plan: dict, analytics: dict) -> tuple[float, list[str]]:
        score = 4.0
        reasons = [f"block_match:{bucket}"]

        underrepresented = [str(item).strip().lower() for item in analytics.get("factor_result", {}).get("underrepresented_factors", [])]
        risk_by_symbol = {
            str(item.get("symbol")): float(item.get("contribution_pct") or 0.0)
            for item in analytics.get("risk_result", {}).get("items", [])
        }
        stress_symbols = {
            str(item.get("symbol"))
            for item in analytics.get("stress_result", {}).get("vulnerable_assets", [])
            if item.get("symbol")
        }
        tech_symbols = {
            str(item.get("symbol"))
            for item in analytics.get("tech_scenario", {}).get("top_negative_contributors", [])
            if item.get("symbol")
        }
        argentina_symbols = {
            str(item.get("symbol"))
            for item in analytics.get("argentina_scenario", {}).get("top_negative_contributors", [])
            if item.get("symbol")
        }
        avoided_buckets = {str(item.get("bucket") or "") for item in monthly_plan.get("avoided_blocks", [])}

        if bucket == "defensive":
            if "defensive" in underrepresented:
                score += 2.0
                reasons.append("factor_defensive_gap")
            if self._is_defensive_like(position):
                score += 1.5
                reasons.append("defensive_sector_match")
        elif bucket == "dividend":
            if "dividend" in underrepresented:
                score += 2.0
                reasons.append("factor_dividend_gap")
            if self._is_dividend_like(position):
                score += 1.5
                reasons.append("dividend_profile")
        elif bucket == "global_index":
            if self._is_global_index_like(position):
                score += 2.0
                reasons.append("stable_global_exposure")
        elif bucket == "fixed_income_ar":
            if self._is_local_fixed_income_like(position):
                score += 2.0
                reasons.append("local_fixed_income_match")
        elif bucket == "emerging":
            if self._is_emerging_like(position):
                score += 2.0
                reasons.append("emerging_diversification")
        elif bucket == "liquidity_ars":
            if self._is_liquidity_like(position):
                score += 1.5
                reasons.append("tactical_liquidity_match")

        if self._improves_geographic_diversification(position, monthly_plan):
            score += 1.25
            reasons.append("geographic_diversification")

        contribution_pct = risk_by_symbol.get(position.symbol)
        if contribution_pct is not None and contribution_pct <= 8.0:
            score += 1.5
            reasons.append("low_risk_contribution")
        elif contribution_pct is not None and contribution_pct >= 18.0:
            score -= 2.5
            reasons.append("high_risk_contribution")

        if position.symbol in stress_symbols:
            score -= 2.0
            reasons.append("stress_fragility_penalty")
        if position.symbol in tech_symbols:
            score -= 1.5
            reasons.append("scenario_vulnerability_tech")
        if position.symbol in argentina_symbols:
            score -= 1.5
            reasons.append("scenario_vulnerability_argentina")

        if "tech_growth" in avoided_buckets and self._is_tech_like(position):
            score -= 2.0
            reasons.append("avoided_block:tech_growth")
        if "argentina_local" in avoided_buckets and self._is_argentina_like(position):
            score -= 2.0
            reasons.append("avoided_block:argentina_local")
        if "local_crisis" in avoided_buckets and self._is_argentina_like(position):
            score -= 1.0
            reasons.append("avoided_block:local_crisis")

        return score, reasons

    @staticmethod
    def _position_matches_block(position: NormalizedPosition, bucket: str) -> bool:
        if bucket == "defensive":
            return CandidateAssetRankingService._is_defensive_like(position)
        if bucket == "dividend":
            return CandidateAssetRankingService._is_dividend_like(position)
        if bucket == "global_index":
            return CandidateAssetRankingService._is_global_index_like(position)
        if bucket == "fixed_income_ar":
            return CandidateAssetRankingService._is_local_fixed_income_like(position)
        if bucket == "emerging":
            return CandidateAssetRankingService._is_emerging_like(position)
        if bucket == "liquidity_ars":
            return CandidateAssetRankingService._is_liquidity_like(position)
        return False

    @staticmethod
    def _is_defensive_like(position: NormalizedPosition) -> bool:
        sector = str(position.sector or "").lower()
        strategic_bucket = str(position.strategic_bucket or "").lower()
        patrimonial_type = str(position.patrimonial_type or "").lower()
        return any(
            token in sector
            for token in ("defensivo", "defensive", "utilities", "salud", "health", "telecom", "consumo defensivo")
        ) or "defens" in strategic_bucket or "defens" in patrimonial_type

    @staticmethod
    def _is_dividend_like(position: NormalizedPosition) -> bool:
        sector = str(position.sector or "").lower()
        strategic_bucket = str(position.strategic_bucket or "").lower()
        patrimonial_type = str(position.patrimonial_type or "").lower()
        symbol = str(position.symbol or "").upper()
        return (
            "dividend" in strategic_bucket
            or "dividend" in patrimonial_type
            or any(token in sector for token in ("utilities", "telecom", "consumo defensivo", "defensive"))
            or symbol in {"KO", "PEP", "T", "VZ", "MCD", "XLU"}
        )

    @staticmethod
    def _is_global_index_like(position: NormalizedPosition) -> bool:
        sector = str(position.sector or "").lower()
        country = str(position.country or "").lower()
        symbol = str(position.symbol or "").upper()
        return (
            "indice" in sector
            or symbol in {"SPY", "VOO", "IVV", "DIA", "IEUR"}
            or (position.asset_type == "equity" and country not in {"argentina", "unknown"})
        )

    @staticmethod
    def _is_local_fixed_income_like(position: NormalizedPosition) -> bool:
        country = str(position.country or "").lower()
        return position.asset_type == "bond" and "argentina" in country

    @staticmethod
    def _is_emerging_like(position: NormalizedPosition) -> bool:
        country = str(position.country or "").lower()
        symbol = str(position.symbol or "").upper()
        return symbol in {"EEM", "EWZ", "MELI", "BABA"} or country in {"latam", "brasil", "china", "emergentes", "em"}

    @staticmethod
    def _is_liquidity_like(position: NormalizedPosition) -> bool:
        asset_type = str(position.asset_type or "").lower()
        currency = str(position.currency or "").upper()
        return asset_type in {"cash", "fci"} or currency == "ARS"

    @staticmethod
    def _is_tech_like(position: NormalizedPosition) -> bool:
        sector = str(position.sector or "").lower()
        return "tecnolog" in sector or "tech" in sector

    @staticmethod
    def _is_argentina_like(position: NormalizedPosition) -> bool:
        country = str(position.country or "").lower()
        return "argentina" in country

    @staticmethod
    def _improves_geographic_diversification(position: NormalizedPosition, monthly_plan: dict) -> bool:
        avoided_buckets = {str(item.get("bucket") or "") for item in monthly_plan.get("avoided_blocks", [])}
        return "argentina_local" in avoided_buckets and not CandidateAssetRankingService._is_argentina_like(position)

    @staticmethod
    def _build_explanation(flat_candidates: list[dict], monthly_plan: dict) -> str:
        if not flat_candidates:
            return "No hay activos candidatos elegibles dentro de los bloques recomendados actuales."
        top_blocks = ", ".join(
            sorted({item["block_label"] for item in flat_candidates[:3]})
        )
        return (
            f"El ranking prioriza activos ya presentes en cartera que encajan mejor en {top_blocks}, "
            "penalizando los que ya cargan demasiado riesgo o fragilidad dentro del diagnóstico actual."
        )

    @staticmethod
    def _empty_result(monthly_plan: dict, explanation: str) -> dict:
        return {
            "capital_total": monthly_plan.get("capital_total", 0),
            "candidate_assets_count": 0,
            "candidate_assets": [],
            "by_block": [],
            "explanation": explanation,
        }
