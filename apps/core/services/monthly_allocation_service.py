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
        candidates = {}
        for bucket, config in self.CANDIDATE_BLOCKS.items():
            candidates[bucket] = {
                "bucket": bucket,
                "label": config["label"],
                "score": Decimal("0"),
                "reasons": [],
                "score_breakdown": {
                    "positive_signals": [],
                    "negative_signals": [],
                    "notes": "Score compuesto por reglas explicables del MVP sobre analytics_v2 y recomendaciones priorizadas.",
                },
                "blocked": False,
            }
        self._boost(
            candidates,
            "dividend",
            Decimal("0.5"),
            "favorece ingresos pasivos cuando no hay penalización dominante",
            signal="passive_income_preference",
            source="monthly_allocation_mvp",
        )
        self._boost(
            candidates,
            "fixed_income_ar",
            Decimal("0.25"),
            "aporta carry y generación de renta si el bloque local no está penalizado",
            signal="carry_income_bias",
            source="monthly_allocation_mvp",
        )
        return candidates

    def _apply_factor_rules(self, candidates: dict, analytics: dict) -> None:
        factor_result = analytics.get("factor_result", {})
        underrepresented = [str(item).strip().lower() for item in factor_result.get("underrepresented_factors", [])]
        dominant_factor = str(factor_result.get("dominant_factor") or "").strip().lower()

        if "defensive" in underrepresented:
            self._boost(
                candidates,
                "defensive",
                Decimal("3"),
                "cubre defensive_gap detectado por factor exposure",
                signal="factor_defensive_gap",
                source="factor_exposure",
            )
            self._boost(
                candidates,
                "dividend",
                Decimal("1"),
                "complementa el sesgo defensivo faltante",
                signal="diversification_needed",
                source="factor_exposure",
            )
        if "dividend" in underrepresented:
            self._boost(
                candidates,
                "dividend",
                Decimal("3"),
                "cubre dividend_gap detectado por factor exposure",
                signal="factor_dividend_gap",
                source="factor_exposure",
            )
        if "value" in underrepresented:
            self._boost(
                candidates,
                "dividend",
                Decimal("1"),
                "agrega sesgo value vía activos orientados a renta",
                signal="factor_value_gap",
                source="factor_exposure",
            )
            self._boost(
                candidates,
                "fixed_income_ar",
                Decimal("0.75"),
                "refuerza un bloque de carry estructural",
                signal="factor_value_gap",
                source="factor_exposure",
            )
        if dominant_factor == "growth":
            self._boost(
                candidates,
                "defensive",
                Decimal("1.5"),
                "reduce dependencia del factor growth dominante",
                signal="factor_growth_excess",
                source="factor_exposure",
            )
            self._boost(
                candidates,
                "dividend",
                Decimal("1"),
                "balancea el sesgo growth con renta",
                signal="factor_growth_excess",
                source="factor_exposure",
            )

    def _apply_expected_return_rules(self, candidates: dict, analytics: dict) -> None:
        result = analytics.get("expected_return_result", {})
        bucket_rows = sorted(
            result.get("by_bucket", []),
            key=lambda item: float(item.get("expected_return_pct") or -9999),
            reverse=True,
        )
        top_bucket_key = bucket_rows[0].get("bucket_key") if bucket_rows else None

        for item in bucket_rows:
            bucket_key = item.get("bucket_key")
            expected_return_pct = item.get("expected_return_pct")
            if expected_return_pct is None or float(expected_return_pct) <= 0:
                continue

            bonus = Decimal("2.5") if bucket_key == top_bucket_key else Decimal("1.25")
            if bucket_key == "equity_beta":
                self._boost(
                    candidates,
                    "global_index",
                    bonus,
                    f"equity_beta muestra mejor referencia estructural de retorno ({float(expected_return_pct):.2f}%)",
                    signal="expected_return_bucket_preferred",
                    source="expected_return",
                )
            elif bucket_key == "fixed_income_ar":
                self._boost(
                    candidates,
                    "fixed_income_ar",
                    bonus,
                    f"renta fija AR muestra referencia estructural positiva ({float(expected_return_pct):.2f}%)",
                    signal="expected_return_bucket_preferred",
                    source="expected_return",
                )
            elif bucket_key == "liquidity_ars":
                self._boost(
                    candidates,
                    "liquidity_ars",
                    Decimal("0.5"),
                    f"liquidez táctica mantiene retorno estructural positivo ({float(expected_return_pct):.2f}%)",
                    signal="expected_return_bucket_preferred",
                    source="expected_return",
                )

        if result.get("real_expected_return_pct") is not None and float(result["real_expected_return_pct"]) < 0:
            self._boost(
                candidates,
                "dividend",
                Decimal("0.75"),
                "busca mejorar el perfil de retorno real con renta",
                signal="expected_return_real_weak",
                source="expected_return",
            )
            self._boost(
                candidates,
                "global_index",
                Decimal("0.75"),
                "compensa retorno real débil del mix actual",
                signal="expected_return_real_weak",
                source="expected_return",
            )

    def _apply_risk_and_stress_rules(self, candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
        risk_result = analytics.get("risk_result", {})
        stress_result = analytics.get("stress_result", {})
        tech_scenario = analytics.get("tech_scenario", {})
        argentina_scenario = analytics.get("argentina_scenario", {})

        top_sector = str(((risk_result.get("by_sector") or [{}])[0]).get("key", "")).lower()
        top_country = str(((risk_result.get("by_country") or [{}])[0]).get("key", "")).lower()

        if "tecnolog" in top_sector or "tech" in top_sector:
            avoided_blocks["tech_growth"] = {
                "bucket": "tech_growth",
                "label": "Tecnología / growth",
                "reason": "ya domina el riesgo relativo actual y no conviene ampliarlo con capital incremental",
            }
            self._boost(
                candidates,
                "defensive",
                Decimal("1.5"),
                "compensa sobreconcentración actual en tecnología",
                signal="diversification_needed",
                source="risk_contribution",
            )
            self._boost(
                candidates,
                "dividend",
                Decimal("1"),
                "reduce dependencia de bloques growth/tech",
                signal="diversification_needed",
                source="risk_contribution",
            )

        if "argentina" in top_country:
            avoided_blocks["argentina_local"] = {
                "bucket": "argentina_local",
                "label": "Argentina / bloque local",
                "reason": "ya concentra una parte alta del riesgo actual y conviene evitar ampliarlo con el nuevo aporte",
            }
            self._penalize(
                candidates,
                "fixed_income_ar",
                Decimal("3"),
                "el bloque argentino ya domina riesgo país o concentración geográfica",
                signal="country_risk_overconcentration",
                source="risk_contribution",
                block=True,
            )
            self._boost(
                candidates,
                "global_index",
                Decimal("1.5"),
                "diversifica fuera del bloque local dominante",
                signal="diversification_needed",
                source="risk_contribution",
            )
            self._boost(
                candidates,
                "emerging",
                Decimal("1"),
                "agrega diversificación fuera de Argentina",
                signal="diversification_needed",
                source="risk_contribution",
            )

        if float(tech_scenario.get("total_impact_pct") or 0.0) <= -8.0:
            avoided_blocks.setdefault(
                "tech_shock",
                {
                    "bucket": "tech_shock",
                    "label": "Bloque tech",
                    "reason": "el shock tech sigue siendo una fuente relevante de pérdida en escenarios adversos",
                },
            )
            self._boost(
                candidates,
                "defensive",
                Decimal("1.5"),
                "amortigua la vulnerabilidad al shock tech",
                signal="scenario_vulnerability_tech",
                source="scenario_analysis",
            )
            self._boost(
                candidates,
                "dividend",
                Decimal("0.75"),
                "favorece un sesgo menos procíclico",
                signal="scenario_vulnerability_tech",
                source="scenario_analysis",
            )

        if float(argentina_scenario.get("total_impact_pct") or 0.0) <= -6.0:
            avoided_blocks.setdefault(
                "argentina_stress",
                {
                    "bucket": "argentina_stress",
                    "label": "Stress Argentina",
                    "reason": "un escenario adverso local ya genera pérdida material en la cartera actual",
                },
            )
            self._penalize(
                candidates,
                "fixed_income_ar",
                Decimal("2"),
                "el escenario local sigue siendo demasiado severo para ampliar el bloque argentino",
                signal="scenario_vulnerability_argentina",
                source="scenario_analysis",
                block=True,
            )
            self._boost(
                candidates,
                "global_index",
                Decimal("1"),
                "mueve el aporte hacia diversificación internacional",
                signal="diversification_needed",
                source="scenario_analysis",
            )

        vulnerable_country = str(((stress_result.get("vulnerable_countries") or [{}])[0]).get("key", "")).lower()
        if "argentina" in vulnerable_country or float(stress_result.get("total_loss_pct") or 0.0) <= -12.0:
            avoided_blocks.setdefault(
                "local_crisis",
                {
                    "bucket": "local_crisis",
                    "label": "Bloque local frágil",
                    "reason": "la crisis local severa sigue explicando una fragilidad alta del portafolio",
                },
            )
            self._penalize(
                candidates,
                "fixed_income_ar",
                Decimal("2"),
                "la fragilidad local actual hace prudente no reforzar el bloque argentino en el MVP",
                signal="stress_fragility_local_crisis",
                source="stress_fragility",
                block=True,
            )
            self._boost(
                candidates,
                "defensive",
                Decimal("2"),
                "reduce fragilidad estructural bajo stress extremo",
                signal="stress_fragility_high",
                source="stress_fragility",
            )
            self._boost(
                candidates,
                "dividend",
                Decimal("1"),
                "mejora resiliencia y flujo pasivo",
                signal="stress_fragility_high",
                source="stress_fragility",
            )

    def _apply_recommendation_rules(self, candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
        for recommendation in analytics.get("recommendations", []):
            recommendation_type = str(recommendation.get("tipo") or "").lower()
            evidence = recommendation.get("evidence") or {}

            if "expected_return_liquidity_drag" in recommendation_type or recommendation_type == "liquidez_excesiva":
                self._penalize(
                    candidates,
                    "liquidity_ars",
                    Decimal("4"),
                    "la liquidez ya actúa como drag de retorno esperado",
                    signal="expected_return_liquidity_drag",
                    source="recommendation_engine",
                    block=True,
                )
                self._boost(
                    candidates,
                    "global_index",
                    Decimal("1"),
                    "redirige flujos desde liquidez excedente",
                    signal="expected_return_liquidity_drag",
                    source="recommendation_engine",
                )
                self._boost(
                    candidates,
                    "defensive",
                    Decimal("1"),
                    "usa el nuevo capital para diversificar en lugar de dejarlo en caja",
                    signal="expected_return_liquidity_drag",
                    source="recommendation_engine",
                )
                self._boost(
                    candidates,
                    "dividend",
                    Decimal("1"),
                    "convierte caja excedente en renta potencial",
                    signal="expected_return_liquidity_drag",
                    source="recommendation_engine",
                )

            if "factor_defensive_gap" in recommendation_type:
                self._boost(
                    candidates,
                    "defensive",
                    Decimal("3"),
                    "RecommendationEngine marca falta de factor defensivo",
                    signal="factor_defensive_gap",
                    source="recommendation_engine",
                )

            if "factor_dividend_gap" in recommendation_type:
                self._boost(
                    candidates,
                    "dividend",
                    Decimal("3"),
                    "RecommendationEngine marca falta de factor dividend",
                    signal="factor_dividend_gap",
                    source="recommendation_engine",
                )

            if "factor_concentration_excessive" in recommendation_type:
                self._boost(
                    candidates,
                    "defensive",
                    Decimal("1"),
                    "reduce concentración factorial excesiva",
                    signal="factor_concentration_excessive",
                    source="recommendation_engine",
                )
                self._boost(
                    candidates,
                    "dividend",
                    Decimal("1"),
                    "agrega otro estilo complementario",
                    signal="factor_concentration_excessive",
                    source="recommendation_engine",
                )
                self._boost(
                    candidates,
                    "emerging",
                    Decimal("1"),
                    "amplía diversificación de drivers",
                    signal="factor_concentration_excessive",
                    source="recommendation_engine",
                )

            if "risk_concentration_tech" in recommendation_type or "scenario_vulnerability_tech" in recommendation_type:
                avoided_blocks.setdefault(
                    "tech_growth",
                    {
                        "bucket": "tech_growth",
                        "label": "Tecnología / growth",
                        "reason": "las señales priorizadas sugieren no reforzar el bloque tech con nuevos aportes",
                    },
                )

            if "risk_concentration_argentina" in recommendation_type or "concentracion_argentina_alta" in recommendation_type:
                avoided_blocks.setdefault(
                    "argentina_local",
                    {
                        "bucket": "argentina_local",
                        "label": "Argentina / bloque local",
                        "reason": "las señales priorizadas indican que el riesgo país ya es material",
                    },
                )
                self._penalize(
                    candidates,
                    "fixed_income_ar",
                    Decimal("2"),
                    "RecommendationEngine prioriza bajar la dependencia argentina",
                    signal="country_risk_overconcentration",
                    source="recommendation_engine",
                    block=True,
                )

            if "stress_fragility_high" in recommendation_type or "stress_sector_fragility" in recommendation_type:
                self._boost(
                    candidates,
                    "defensive",
                    Decimal("1.5"),
                    "mitiga la fragilidad alta detectada por stress testing",
                    signal="stress_fragility_high",
                    source="recommendation_engine",
                )
                self._boost(
                    candidates,
                    "dividend",
                    Decimal("1"),
                    "agrega resiliencia adicional al aporte",
                    signal="stress_fragility_high",
                    source="recommendation_engine",
                )

            if "country_risk_overconcentration" in recommendation_type:
                country = str(evidence.get("country", "")).strip()
                if country:
                    avoided_blocks.setdefault(
                        f"country:{country.lower()}",
                        {
                            "bucket": f"country:{country.lower()}",
                            "label": country,
                            "reason": f"ese país ya explica más riesgo que peso patrimonial en la cartera actual",
                        },
                    )

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
        candidate = candidates.get(bucket)
        if not candidate:
            return
        candidate["score"] += points
        candidate["reasons"].append(reason)
        candidate["score_breakdown"]["positive_signals"].append(
            {
                "signal": signal,
                "impact": f"+{float(points):.2f}",
                "source": source,
                "reason": reason,
            }
        )

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
        candidate = candidates.get(bucket)
        if not candidate:
            return
        candidate["score"] -= points
        candidate["reasons"].append(reason)
        candidate["score_breakdown"]["negative_signals"].append(
            {
                "signal": signal,
                "impact": f"-{float(points):.2f}",
                "source": source,
                "reason": reason,
            }
        )
        candidate["blocked"] = candidate["blocked"] or block

    def _select_recommended_candidates(self, candidates: dict[str, dict]) -> list[dict]:
        eligible = [
            candidate
            for candidate in candidates.values()
            if candidate["score"] > 0 and not candidate["blocked"]
        ]
        return sorted(
            eligible,
            key=lambda item: (item["score"], item["label"]),
            reverse=True,
        )[: self.MAX_RECOMMENDED_BLOCKS]

    @staticmethod
    def _should_use_liquidity_fallback(analytics: dict, avoided_blocks: dict[str, dict]) -> bool:
        underrepresented = analytics.get("factor_result", {}).get("underrepresented_factors") or []
        positive_expected_buckets = [
            item
            for item in analytics.get("expected_return_result", {}).get("by_bucket", [])
            if item.get("expected_return_pct") is not None and float(item.get("expected_return_pct") or 0.0) > 0
        ]
        severe_overload = len(avoided_blocks) >= 2
        return severe_overload and not underrepresented and not positive_expected_buckets

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
        return {
            "bucket": "liquidity_ars",
            "label": self.CANDIDATE_BLOCKS["liquidity_ars"]["label"],
            "score": Decimal("1"),
            "reasons": [
                "no hay bloques de inversión claramente favorecidos; se preserva flexibilidad táctica como fallback del MVP"
            ],
            "score_breakdown": {
                "positive_signals": [
                    {
                        "signal": "fallback_liquidity_preservation",
                        "impact": "+1.00",
                        "source": "monthly_allocation_mvp",
                        "reason": "no hay bloques positivos claros y se preserva flexibilidad táctica",
                    }
                ],
                "negative_signals": [],
                "notes": "Fallback prudente cuando el motor no encuentra bloques de inversión claramente favorecidos.",
            },
            "blocked": False,
        }

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
