from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable

from apps.core.services.analytics_v2 import (
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    RiskContributionService,
    ScenarioAnalysisService,
    StressFragilityService,
)
from apps.core.services.monthly_allocation_rules import (
    apply_expected_return_rules,
    apply_factor_rules,
    apply_recommendation_rules,
    apply_risk_and_stress_rules,
    boost,
    build_candidate_map,
    fallback_liquidity_candidate,
    penalize,
    select_recommended_candidates,
    should_use_liquidity_fallback,
)


class MonthlyAllocationService:
    """Motor MVP de asignacion mensual incremental guiado por señales y analytics actuales."""

    DEFAULT_CRITERION = "rules_based_analytics_v2_mvp"
    MAX_RECOMMENDED_BLOCKS = 3
    CANDIDATE_BLOCKS = {
        "defensive": {"label": "Defensive / resiliente"},
        "dividend": {"label": "Dividend / ingresos pasivos"},
        "global_index": {"label": "Indice global"},
        "fixed_income_ar": {"label": "Renta fija AR"},
        "emerging": {"label": "Emergentes diversificados"},
        "liquidity_ars": {"label": "Liquidez tactica ARS"},
    }

    def __init__(
        self,
        *,
        expected_return_service: ExpectedReturnService | None = None,
        factor_exposure_service: FactorExposureService | None = None,
        stress_fragility_service: StressFragilityService | None = None,
        scenario_analysis_service: ScenarioAnalysisService | None = None,
        risk_contribution_service: RiskContributionService | None = None,
        covariance_risk_contribution_service: CovarianceAwareRiskContributionService | None = None,
        recommendation_loader: Callable[[], list[dict]] | None = None,
    ):
        self.expected_return_service = expected_return_service or ExpectedReturnService()
        self.factor_exposure_service = factor_exposure_service or FactorExposureService()
        self.stress_fragility_service = stress_fragility_service or StressFragilityService()
        self.scenario_analysis_service = scenario_analysis_service or ScenarioAnalysisService()
        self.risk_contribution_service = risk_contribution_service or RiskContributionService()
        self.covariance_risk_contribution_service = (
            covariance_risk_contribution_service or CovarianceAwareRiskContributionService()
        )
        self.recommendation_loader = recommendation_loader

    def build_plan(self, capital_amount: Decimal | int | float | str) -> dict:
        capital = self._coerce_capital(capital_amount)
        if capital <= 0:
            return self._empty_plan(
                capital_total=capital,
                warning="invalid_capital",
                explanation="No se genera propuesta porque el capital incremental es cero o inválido.",
            )

        analytics = self._load_analytics()
        candidates = self._build_candidate_map()
        avoided_blocks: dict[str, dict] = {}

        self._apply_factor_rules(candidates, analytics)
        self._apply_expected_return_rules(candidates, analytics)
        self._apply_risk_and_stress_rules(candidates, avoided_blocks, analytics)
        self._apply_recommendation_rules(candidates, avoided_blocks, analytics)

        use_liquidity_fallback = self._should_use_liquidity_fallback(analytics, avoided_blocks)
        recommended_candidates = [] if use_liquidity_fallback else self._select_recommended_candidates(candidates)
        if not recommended_candidates:
            fallback = self._fallback_liquidity_candidate()
            recommended_candidates = [fallback]
            avoided_blocks.setdefault(
                "overloaded_portfolio",
                {
                    "bucket": "overloaded_portfolio",
                    "label": "Portafolio sobrecargado",
                    "reason": "Todos los bloques de inversión quedaron penalizados; se usa liquidez táctica como fallback prudente.",
                },
            )

        allocations = self._allocate_amounts(capital, recommended_candidates)
        explanation = self._build_explanation(allocations, avoided_blocks)

        return {
            "capital_total": int(capital),
            "recommended_blocks_count": len(allocations),
            "criterion": self.DEFAULT_CRITERION,
            "recommended_blocks": allocations,
            "avoided_blocks": list(avoided_blocks.values()),
            "explanation": explanation,
            "signals_considered": len(analytics.get("recommendations", [])),
        }

    @staticmethod
    def _coerce_capital(value: Decimal | int | float | str) -> Decimal:
        try:
            capital = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")
        return capital.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    def _load_analytics(self) -> dict:
        covariance_result = self.covariance_risk_contribution_service.calculate(top_n=5)
        if covariance_result.get("model_variant") == "covariance_aware":
            risk_result = covariance_result
        else:
            risk_result = self.risk_contribution_service.calculate(top_n=5)

        return {
            "risk_result": risk_result,
            "expected_return_result": self.expected_return_service.calculate(),
            "factor_result": self.factor_exposure_service.calculate(),
            "stress_result": self.stress_fragility_service.calculate("local_crisis_severe"),
            "tech_scenario": self.scenario_analysis_service.analyze("tech_shock"),
            "argentina_scenario": self.scenario_analysis_service.analyze("argentina_stress"),
            "recommendations": self._load_recommendations(),
        }

    def _load_recommendations(self) -> list[dict]:
        if self.recommendation_loader is not None:
            return self.recommendation_loader() or []

        from apps.core.services.recommendation_engine import RecommendationEngine

        return RecommendationEngine().generate_recommendations() or []

    def _build_candidate_map(self) -> dict[str, dict]:
        return build_candidate_map(self.CANDIDATE_BLOCKS)

    def _apply_factor_rules(self, candidates: dict, analytics: dict) -> None:
        apply_factor_rules(candidates, analytics)

    def _apply_expected_return_rules(self, candidates: dict, analytics: dict) -> None:
        apply_expected_return_rules(candidates, analytics)

    def _apply_risk_and_stress_rules(self, candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
        apply_risk_and_stress_rules(candidates, avoided_blocks, analytics)

    def _apply_recommendation_rules(self, candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
        apply_recommendation_rules(candidates, avoided_blocks, analytics)

    @staticmethod
    def _boost(
        candidates: dict,
        bucket: str,
        points: Decimal,
        reason: str,
        *,
        signal: str,
        source: str,
    ) -> None:
        boost(candidates, bucket, points, reason, signal=signal, source=source)

    @staticmethod
    def _penalize(
        candidates: dict,
        bucket: str,
        points: Decimal,
        reason: str,
        *,
        signal: str,
        source: str,
        block: bool = False,
    ) -> None:
        penalize(candidates, bucket, points, reason, signal=signal, source=source, block=block)

    def _select_recommended_candidates(self, candidates: dict[str, dict]) -> list[dict]:
        return select_recommended_candidates(candidates, max_recommended_blocks=self.MAX_RECOMMENDED_BLOCKS)

    @staticmethod
    def _should_use_liquidity_fallback(analytics: dict, avoided_blocks: dict[str, dict]) -> bool:
        return should_use_liquidity_fallback(analytics, avoided_blocks)

    def _allocate_amounts(self, capital: Decimal, candidates: list[dict]) -> list[dict]:
        total_score = sum(candidate["score"] for candidate in candidates)
        if total_score <= 0:
            return []

        allocations = []
        allocated = Decimal("0")
        for index, candidate in enumerate(candidates):
            if index == len(candidates) - 1:
                amount = capital - allocated
            else:
                raw_amount = (capital * candidate["score"] / total_score).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                amount = raw_amount
                allocated += amount

            suggested_pct = round((float(amount) / float(capital)) * 100.0, 2) if capital > 0 else 0.0
            allocations.append(
                {
                    "bucket": candidate["bucket"],
                    "label": candidate["label"],
                    "score": round(float(candidate["score"]), 2),
                    "suggested_amount": int(amount),
                    "suggested_pct": suggested_pct,
                    "reason": candidate["reasons"][0],
                    "reasons": candidate["reasons"],
                    "score_breakdown": candidate["score_breakdown"],
                }
            )

        return allocations

    def _build_explanation(self, allocations: list[dict], avoided_blocks: dict[str, dict]) -> str:
        if not allocations:
            return "No hay bloques suficientes para construir una propuesta incremental."

        reinforced = ", ".join(item["label"] for item in allocations[:2])
        avoided = ", ".join(item["label"] for item in list(avoided_blocks.values())[:2])
        if avoided:
            return (
                f"El aporte mensual se concentra en {reinforced} porque hoy ofrecen mejor combinación "
                f"de diversificación, resiliencia y retorno estructural. Se evita reforzar {avoided} "
                "porque esos bloques ya cargan concentración de riesgo o fragilidad."
            )
        return (
            f"El aporte mensual se concentra en {reinforced} porque hoy combinan mejor diversificación, "
            "retorno estructural y reducción de fragilidad dentro del MVP basado en reglas."
        )

    def _fallback_liquidity_candidate(self) -> dict:
        return fallback_liquidity_candidate(liquidity_label=self.CANDIDATE_BLOCKS["liquidity_ars"]["label"])

    def _empty_plan(self, *, capital_total: Decimal, warning: str, explanation: str) -> dict:
        return {
            "capital_total": int(capital_total),
            "recommended_blocks_count": 0,
            "criterion": self.DEFAULT_CRITERION,
            "recommended_blocks": [],
            "avoided_blocks": [],
            "explanation": explanation,
            "warnings": [warning],
            "signals_considered": 0,
        }
