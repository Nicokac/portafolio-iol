from __future__ import annotations

from decimal import Decimal


def build_candidate_map(candidate_blocks: dict[str, dict]) -> dict[str, dict]:
    candidates = {}
    for bucket, config in candidate_blocks.items():
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
    boost(
        candidates,
        "dividend",
        Decimal("0.5"),
        "favorece ingresos pasivos cuando no hay penalizacion dominante",
        signal="passive_income_preference",
        source="monthly_allocation_mvp",
    )
    boost(
        candidates,
        "fixed_income_ar",
        Decimal("0.25"),
        "aporta carry y generacion de renta si el bloque local no esta penalizado",
        signal="carry_income_bias",
        source="monthly_allocation_mvp",
    )
    return candidates


def apply_factor_rules(candidates: dict, analytics: dict) -> None:
    factor_result = analytics.get("factor_result", {})
    underrepresented = [str(item).strip().lower() for item in factor_result.get("underrepresented_factors", [])]
    dominant_factor = str(factor_result.get("dominant_factor") or "").strip().lower()

    if "defensive" in underrepresented:
        boost(candidates, "defensive", Decimal("3"), "cubre defensive_gap detectado por factor exposure", signal="factor_defensive_gap", source="factor_exposure")
        boost(candidates, "dividend", Decimal("1"), "complementa el sesgo defensivo faltante", signal="diversification_needed", source="factor_exposure")
    if "dividend" in underrepresented:
        boost(candidates, "dividend", Decimal("3"), "cubre dividend_gap detectado por factor exposure", signal="factor_dividend_gap", source="factor_exposure")
    if "value" in underrepresented:
        boost(candidates, "dividend", Decimal("1"), "agrega sesgo value via activos orientados a renta", signal="factor_value_gap", source="factor_exposure")
        boost(candidates, "fixed_income_ar", Decimal("0.75"), "refuerza un bloque de carry estructural", signal="factor_value_gap", source="factor_exposure")
    if dominant_factor == "growth":
        boost(candidates, "defensive", Decimal("1.5"), "reduce dependencia del factor growth dominante", signal="factor_growth_excess", source="factor_exposure")
        boost(candidates, "dividend", Decimal("1"), "balancea el sesgo growth con renta", signal="factor_growth_excess", source="factor_exposure")


def apply_expected_return_rules(candidates: dict, analytics: dict) -> None:
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
            boost(candidates, "global_index", bonus, f"equity_beta muestra mejor referencia estructural de retorno ({float(expected_return_pct):.2f}%)", signal="expected_return_bucket_preferred", source="expected_return")
        elif bucket_key == "fixed_income_ar":
            boost(candidates, "fixed_income_ar", bonus, f"renta fija AR muestra referencia estructural positiva ({float(expected_return_pct):.2f}%)", signal="expected_return_bucket_preferred", source="expected_return")
        elif bucket_key == "liquidity_ars":
            boost(candidates, "liquidity_ars", Decimal("0.5"), f"liquidez tactica mantiene retorno estructural positivo ({float(expected_return_pct):.2f}%)", signal="expected_return_bucket_preferred", source="expected_return")

    if result.get("real_expected_return_pct") is not None and float(result["real_expected_return_pct"]) < 0:
        boost(candidates, "dividend", Decimal("0.75"), "busca mejorar el perfil de retorno real con renta", signal="expected_return_real_weak", source="expected_return")
        boost(candidates, "global_index", Decimal("0.75"), "compensa retorno real debil del mix actual", signal="expected_return_real_weak", source="expected_return")


def apply_risk_and_stress_rules(candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
    risk_result = analytics.get("risk_result", {})
    stress_result = analytics.get("stress_result", {})
    tech_scenario = analytics.get("tech_scenario", {})
    argentina_scenario = analytics.get("argentina_scenario", {})

    top_sector = str(((risk_result.get("by_sector") or [{}])[0]).get("key", "")).lower()
    top_country = str(((risk_result.get("by_country") or [{}])[0]).get("key", "")).lower()

    if "tecnolog" in top_sector or "tech" in top_sector:
        avoided_blocks["tech_growth"] = {
            "bucket": "tech_growth",
            "label": "Tecnologia / growth",
            "reason": "ya domina el riesgo relativo actual y no conviene ampliarlo con capital incremental",
        }
        boost(candidates, "defensive", Decimal("1.5"), "compensa sobreconcentracion actual en tecnologia", signal="diversification_needed", source="risk_contribution")
        boost(candidates, "dividend", Decimal("1"), "reduce dependencia de bloques growth/tech", signal="diversification_needed", source="risk_contribution")

    if "argentina" in top_country:
        avoided_blocks["argentina_local"] = {
            "bucket": "argentina_local",
            "label": "Argentina / bloque local",
            "reason": "ya concentra una parte alta del riesgo actual y conviene evitar ampliarlo con el nuevo aporte",
        }
        penalize(candidates, "fixed_income_ar", Decimal("3"), "el bloque argentino ya domina riesgo pais o concentracion geografica", signal="country_risk_overconcentration", source="risk_contribution", block=True)
        boost(candidates, "global_index", Decimal("1.5"), "diversifica fuera del bloque local dominante", signal="diversification_needed", source="risk_contribution")
        boost(candidates, "emerging", Decimal("1"), "agrega diversificacion fuera de Argentina", signal="diversification_needed", source="risk_contribution")

    if float(tech_scenario.get("total_impact_pct") or 0.0) <= -8.0:
        avoided_blocks.setdefault("tech_shock", {"bucket": "tech_shock", "label": "Bloque tech", "reason": "el shock tech sigue siendo una fuente relevante de perdida en escenarios adversos"})
        boost(candidates, "defensive", Decimal("1.5"), "amortigua la vulnerabilidad al shock tech", signal="scenario_vulnerability_tech", source="scenario_analysis")
        boost(candidates, "dividend", Decimal("0.75"), "favorece un sesgo menos prociclico", signal="scenario_vulnerability_tech", source="scenario_analysis")

    if float(argentina_scenario.get("total_impact_pct") or 0.0) <= -6.0:
        avoided_blocks.setdefault("argentina_stress", {"bucket": "argentina_stress", "label": "Stress Argentina", "reason": "un escenario adverso local ya genera perdida material en la cartera actual"})
        penalize(candidates, "fixed_income_ar", Decimal("2"), "el escenario local sigue siendo demasiado severo para ampliar el bloque argentino", signal="scenario_vulnerability_argentina", source="scenario_analysis", block=True)
        boost(candidates, "global_index", Decimal("1"), "mueve el aporte hacia diversificacion internacional", signal="diversification_needed", source="scenario_analysis")

    vulnerable_country = str(((stress_result.get("vulnerable_countries") or [{}])[0]).get("key", "")).lower()
    if "argentina" in vulnerable_country or float(stress_result.get("total_loss_pct") or 0.0) <= -12.0:
        avoided_blocks.setdefault("local_crisis", {"bucket": "local_crisis", "label": "Bloque local fragil", "reason": "la crisis local severa sigue explicando una fragilidad alta del portafolio"})
        penalize(candidates, "fixed_income_ar", Decimal("2"), "la fragilidad local actual hace prudente no reforzar el bloque argentino en el MVP", signal="stress_fragility_local_crisis", source="stress_fragility", block=True)
        boost(candidates, "defensive", Decimal("2"), "reduce fragilidad estructural bajo stress extremo", signal="stress_fragility_high", source="stress_fragility")
        boost(candidates, "dividend", Decimal("1"), "mejora resiliencia y flujo pasivo", signal="stress_fragility_high", source="stress_fragility")


def apply_recommendation_rules(candidates: dict, avoided_blocks: dict, analytics: dict) -> None:
    for recommendation in analytics.get("recommendations", []):
        recommendation_type = str(recommendation.get("tipo") or "").lower()
        evidence = recommendation.get("evidence") or {}

        if "expected_return_liquidity_drag" in recommendation_type or recommendation_type == "liquidez_excesiva":
            penalize(candidates, "liquidity_ars", Decimal("4"), "la liquidez ya actua como drag de retorno esperado", signal="expected_return_liquidity_drag", source="recommendation_engine", block=True)
            boost(candidates, "global_index", Decimal("1"), "redirige flujos desde liquidez excedente", signal="expected_return_liquidity_drag", source="recommendation_engine")
            boost(candidates, "defensive", Decimal("1"), "usa el nuevo capital para diversificar en lugar de dejarlo en caja", signal="expected_return_liquidity_drag", source="recommendation_engine")
            boost(candidates, "dividend", Decimal("1"), "convierte caja excedente en renta potencial", signal="expected_return_liquidity_drag", source="recommendation_engine")

        if "factor_defensive_gap" in recommendation_type:
            boost(candidates, "defensive", Decimal("3"), "RecommendationEngine marca falta de factor defensivo", signal="factor_defensive_gap", source="recommendation_engine")

        if "factor_dividend_gap" in recommendation_type:
            boost(candidates, "dividend", Decimal("3"), "RecommendationEngine marca falta de factor dividend", signal="factor_dividend_gap", source="recommendation_engine")

        if "factor_concentration_excessive" in recommendation_type:
            boost(candidates, "defensive", Decimal("1"), "reduce concentracion factorial excesiva", signal="factor_concentration_excessive", source="recommendation_engine")
            boost(candidates, "dividend", Decimal("1"), "agrega otro estilo complementario", signal="factor_concentration_excessive", source="recommendation_engine")
            boost(candidates, "emerging", Decimal("1"), "amplia diversificacion de drivers", signal="factor_concentration_excessive", source="recommendation_engine")

        if "risk_concentration_tech" in recommendation_type or "scenario_vulnerability_tech" in recommendation_type:
            avoided_blocks.setdefault("tech_growth", {"bucket": "tech_growth", "label": "Tecnologia / growth", "reason": "las senales priorizadas sugieren no reforzar el bloque tech con nuevos aportes"})

        if "risk_concentration_argentina" in recommendation_type or "concentracion_argentina_alta" in recommendation_type:
            avoided_blocks.setdefault("argentina_local", {"bucket": "argentina_local", "label": "Argentina / bloque local", "reason": "las senales priorizadas indican que el riesgo pais ya es material"})
            penalize(candidates, "fixed_income_ar", Decimal("2"), "RecommendationEngine prioriza bajar la dependencia argentina", signal="country_risk_overconcentration", source="recommendation_engine", block=True)

        if "stress_fragility_high" in recommendation_type or "stress_sector_fragility" in recommendation_type:
            boost(candidates, "defensive", Decimal("1.5"), "mitiga la fragilidad alta detectada por stress testing", signal="stress_fragility_high", source="recommendation_engine")
            boost(candidates, "dividend", Decimal("1"), "agrega resiliencia adicional al aporte", signal="stress_fragility_high", source="recommendation_engine")

        if "country_risk_overconcentration" in recommendation_type:
            country = str(evidence.get("country", "")).strip()
            if country:
                avoided_blocks.setdefault(
                    f"country:{country.lower()}",
                    {
                        "bucket": f"country:{country.lower()}",
                        "label": country,
                        "reason": f"ese pais ya explica mas riesgo que peso patrimonial en la cartera actual",
                    },
                )


def boost(
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


def penalize(
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


def select_recommended_candidates(candidates: dict[str, dict], *, max_recommended_blocks: int) -> list[dict]:
    eligible = [
        candidate
        for candidate in candidates.values()
        if candidate["score"] > 0 and not candidate["blocked"]
    ]
    return sorted(
        eligible,
        key=lambda item: (item["score"], item["label"]),
        reverse=True,
    )[: max_recommended_blocks]


def should_use_liquidity_fallback(analytics: dict, avoided_blocks: dict[str, dict]) -> bool:
    underrepresented = analytics.get("factor_result", {}).get("underrepresented_factors") or []
    positive_expected_buckets = [
        item
        for item in analytics.get("expected_return_result", {}).get("by_bucket", [])
        if item.get("expected_return_pct") is not None and float(item.get("expected_return_pct") or 0.0) > 0
    ]
    severe_overload = len(avoided_blocks) >= 2
    return severe_overload and not underrepresented and not positive_expected_buckets


def fallback_liquidity_candidate(*, liquidity_label: str) -> dict:
    return {
        "bucket": "liquidity_ars",
        "label": liquidity_label,
        "score": Decimal("1"),
        "reasons": [
            "no hay bloques de inversion claramente favorecidos; se preserva flexibilidad tactica como fallback del MVP"
        ],
        "score_breakdown": {
            "positive_signals": [
                {
                    "signal": "fallback_liquidity_preservation",
                    "impact": "+1.00",
                    "source": "monthly_allocation_mvp",
                    "reason": "no hay bloques positivos claros y se preserva flexibilidad tactica",
                }
            ],
            "negative_signals": [],
            "notes": "Fallback prudente cuando el motor no encuentra bloques de inversion claramente favorecidos.",
        },
        "blocked": False,
    }
