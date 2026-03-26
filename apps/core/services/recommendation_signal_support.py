from typing import Dict, List


def build_analytics_v2_recommendations(
    service,
    scenario_service_class,
    factor_service_class,
    stress_service_class,
    expected_return_service_class,
    local_macro_service_class,
) -> List[Dict]:
    signals = (
        service._build_risk_contribution_signals()
        + scenario_service_class().build_recommendation_signals()
        + factor_service_class().build_recommendation_signals()
        + stress_service_class().build_recommendation_signals()
        + expected_return_service_class().build_recommendation_signals()
        + local_macro_service_class().build_recommendation_signals()
    )
    if not signals:
        return []

    normalized = [service._map_signal_to_recommendation(signal) for signal in signals]
    return sorted(
        normalized,
        key=lambda rec: {"alta": 0, "media": 1, "baja": 2}.get(rec.get("prioridad", "media"), 3),
    )


def build_risk_contribution_signals(logger, covariance_service_class, risk_service_class) -> List[Dict]:
    try:
        covariance_service = covariance_service_class()
        covariance_result = covariance_service.calculate(top_n=5)
        if covariance_result.get("model_variant") == "covariance_aware":
            return [
                {
                    **signal,
                    "risk_model_variant": "covariance_aware",
                }
                for signal in covariance_service.build_recommendation_signals(top_n=5)
            ]
    except Exception as exc:
        logger.error("Error evaluating covariance-aware risk contribution signals: %s", exc)

    return [
        {
            **signal,
            "risk_model_variant": "mvp_proxy",
        }
        for signal in risk_service_class().build_recommendation_signals(top_n=5)
    ]


def prioritize_recommendations(recommendations: List[Dict], priority_rank: Dict[str, int]) -> List[Dict]:
    selected_by_topic = {}

    for index, recommendation in enumerate(recommendations):
        topic_key = recommendation_topic_key(recommendation)
        sort_key = recommendation_sort_key(recommendation, index, priority_rank)
        current = selected_by_topic.get(topic_key)
        if current is None or sort_key < current[0]:
            selected_by_topic[topic_key] = (sort_key, recommendation)

    return [
        entry[1]
        for entry in sorted(selected_by_topic.values(), key=lambda item: item[0])
    ]


def recommendation_topic_key(recommendation: Dict) -> str:
    recommendation_type = str(recommendation.get("tipo", "")).lower()
    evidence = recommendation.get("evidence") or {}
    topic_aliases = {
        "liquidez_excesiva": "liquidity_excess",
        "analytics_v2_expected_return_liquidity_drag": "liquidity_excess",
        "analytics_v2_local_liquidity_real_carry_negative": "liquidity_excess",
        "analytics_v2_local_fx_gap_high": "local_fx_stress",
        "analytics_v2_local_fx_regime_tensioned": "local_fx_stress",
        "analytics_v2_local_fx_regime_divergent": "local_fx_stress",
        "analytics_v2_local_fx_gap_deteriorating": "local_fx_stress",
        "concentracion_argentina_alta": "argentina_concentration",
        "analytics_v2_risk_concentration_argentina": "argentina_concentration",
        "analytics_v2_local_sovereign_risk_excess": "argentina_concentration",
        "analytics_v2_local_country_risk_high": "argentina_concentration",
        "analytics_v2_local_inflation_hedge_gap": "local_fixed_income_mix",
        "analytics_v2_local_sovereign_hard_dollar_dependence": "local_fixed_income_mix",
        "riesgo_concentracion_alto": "portfolio_concentration",
        "riesgo_concentracion_media": "portfolio_concentration",
        "analytics_v2_risk_concentration_top_assets": "portfolio_concentration",
    }
    if recommendation_type == "analytics_v2_country_risk_overconcentration":
        country = str(evidence.get("country", "")).strip().lower()
        if country == "argentina":
            return "argentina_concentration"
        if country:
            return f"country_risk_overconcentration:{country}"
    if recommendation_type == "analytics_v2_country_risk_underconcentration":
        country = str(evidence.get("country", "")).strip().lower()
        if country:
            return f"country_risk_underconcentration:{country}"
    if recommendation_type == "analytics_v2_sector_risk_overconcentration":
        sector = str(evidence.get("sector", "")).strip().lower()
        if "tecnolog" in sector or "tech" in sector:
            return "tech_concentration"
        if sector:
            return f"sector_risk_overconcentration:{sector}"
    if recommendation_type == "analytics_v2_risk_concentration_tech":
        return "tech_concentration"
    return topic_aliases.get(recommendation_type, recommendation_type)


def recommendation_sort_key(recommendation: Dict, index: int, priority_rank: Dict[str, int]) -> tuple:
    priority = priority_rank.get(
        str(recommendation.get("prioridad", "media")).lower(),
        3,
    )
    origin = 0 if recommendation.get("origen") == "analytics_v2" else 1
    specificity = recommendation_specificity_rank(recommendation)
    has_assets = 0 if recommendation.get("activos_sugeridos") else 1
    return (priority, origin, specificity, has_assets, index)


def recommendation_specificity_rank(recommendation: Dict) -> int:
    recommendation_type = str(recommendation.get("tipo", "")).lower()
    specificity_rank = {
        "analytics_v2_local_liquidity_real_carry_negative": 0,
        "analytics_v2_local_fx_regime_divergent": -1,
        "analytics_v2_local_fx_regime_tensioned": 0,
        "analytics_v2_local_fx_gap_deteriorating": 1,
        "analytics_v2_local_fx_gap_high": 2,
        "analytics_v2_local_country_risk_high": -1,
        "analytics_v2_country_risk_overconcentration": 0,
        "analytics_v2_sector_risk_overconcentration": 0,
        "analytics_v2_country_risk_underconcentration": 0,
        "analytics_v2_local_sovereign_hard_dollar_dependence": 0,
        "analytics_v2_local_sovereign_risk_excess": 0,
        "analytics_v2_local_inflation_hedge_gap": 1,
        "analytics_v2_expected_return_liquidity_drag": 1,
        "analytics_v2_risk_concentration_argentina": 1,
        "analytics_v2_risk_concentration_tech": 1,
        "liquidez_excesiva": 2,
        "concentracion_argentina_alta": 2,
    }
    return specificity_rank.get(recommendation_type, 1)


def map_signal_to_recommendation(service, signal: Dict) -> Dict:
    severity = str(signal.get("severity", "medium")).lower()
    prioridad = {"high": "alta", "medium": "media", "low": "baja"}.get(severity, "media")
    evidence = signal.get("evidence") or {}

    recommendation = {
        "tipo": f"analytics_v2_{signal.get('signal_key', 'signal')}",
        "prioridad": prioridad,
        "titulo": signal.get("title", "Señal Analytics v2"),
        "descripcion": signal.get("description", ""),
        "acciones_sugeridas": service._build_signal_actions(signal),
        "impacto_esperado": "Mejor trazabilidad entre riesgo, escenarios y planeación",
        "origen": "analytics_v2",
    }

    suggested_assets = extract_signal_assets(evidence)
    if suggested_assets:
        recommendation["activos_sugeridos"] = suggested_assets
    if signal.get("risk_model_variant"):
        recommendation["modelo_riesgo"] = signal["risk_model_variant"]
    return recommendation


def extract_signal_assets(evidence: Dict) -> List[str]:
    top_symbols = evidence.get("top_symbols")
    if isinstance(top_symbols, list) and top_symbols:
        return [str(symbol) for symbol in top_symbols[:3]]
    factor = evidence.get("factor")
    if factor:
        return [str(factor)]
    return []


def build_signal_actions(signal: Dict) -> List[str]:
    key = str(signal.get("signal_key", ""))
    if "liquidity_drag" in key:
        return [
            "Reducir gradualmente liquidez excedente si no cumple una función táctica explícita",
            "Dirigir nuevos flujos a buckets con mejor retorno esperado estructural",
        ]
    if "real_carry" in key:
        return [
            "Revisar si la liquidez en ARS sigue cumpliendo una función táctica clara",
            "Comparar BADLAR contra inflación antes de mantener saldos altos en pesos",
        ]
    if "real_rate_negative" in key:
        return [
            "Revisar si la liquidez en ARS sigue justificándose cuando BADLAR corre por debajo de UVA",
            "Mover nuevos flujos hacia cobertura CER u otros activos con mejor defensa real si la tesis local sigue vigente",
        ]
    if "local_fx_regime_divergent" in key:
        return [
            "Tomar MEP y CCL como señales separadas y evitar asumir una sola referencia financiera limpia",
            "Frenar nuevas decisiones locales apalancadas en arbitrajes FX hasta que la divergencia se normalice",
        ]
    if "local_fx_regime_tensioned" in key:
        return [
            "Reducir dependencia de una brecha cambiaria tensionada antes de sumar riesgo argentino",
            "Usar nuevos aportes para reforzar diversificación internacional o liquidez dura si la tesis local no cambió",
        ]
    if "fx_gap" in key:
        return [
            "Revisar cuánta exposición argentina depende de una brecha cambiaria tensionada",
            "Evitar sumar riesgo local en ARS o soberano sin una convicción táctica explícita",
        ]
    if "sector_risk_overconcentration" in key:
        sector = signal.get("evidence", {}).get("sector", "ese sector")
        return [
            f"Revisar concentración de riesgo en el sector {sector}.",
            "Usar nuevos aportes para bajar dependencia del bloque sectorial que domina el riesgo.",
        ]
    if "country_risk_overconcentration" in key:
        country = signal.get("evidence", {}).get("country", "ese país")
        return [
            f"Revisar concentración geográfica de riesgo en {country}.",
            "Reducir dependencia del bloque geográfico que hoy explica más riesgo que peso.",
        ]
    if "country_risk_underconcentration" in key:
        country = signal.get("evidence", {}).get("country", "ese país")
        return [
            f"El peso patrimonial en {country} es mayor que su contribución actual al riesgo.",
            "Mantener la lectura como señal informativa antes de rebalancear solo por patrimonio.",
        ]
    if "country_risk" in key:
        return [
            "Revisar si el peso de soberanos locales sigue siendo consistente con el nivel actual de riesgo país",
            "Reducir dependencia de crédito soberano argentino si el bloque local ya es material",
        ]
    if "single_name" in key and "sovereign" in key:
        return [
            "Reducir dependencia de un solo bono soberano dentro del bloque argentino",
            "Distribuir el riesgo local entre instrumentos con drivers distintos si la convicción sigue siendo local",
        ]
    if "hard_dollar" in key and "sovereign" in key:
        return [
            "Revisar si el bloque de renta fija local depende demasiado de soberanos hard dollar",
            "Balancear el bloque local con CER u otras exposiciones argentinas menos correlacionadas",
        ]
    if "inflation_hedge" in key:
        return [
            "Evaluar si la cobertura CER es suficiente para la exposición argentina actual",
            "Evitar depender solo de carry nominal cuando la inflación local sigue alta",
        ]
    if "inflation_accelerating" in key:
        return [
            "Revisar si la cobertura indexada local acompaña la aceleración reciente de UVA",
            "Evitar ampliar exposición nominal en ARS sin una cobertura inflacionaria proporcional",
        ]
    if "sovereign_risk" in key:
        return [
            "Reducir dependencia de soberanos locales si ya dominan el bloque argentino",
            "Diversificar riesgo local entre instrumentos menos concentrados o exposición internacional",
        ]
    if "argentina" in key or "local_crisis" in key:
        return [
            "Bajar vulnerabilidad local con diversificación internacional adicional",
            "Evitar sumar riesgo argentino sin convicción táctica explícita",
        ]
    if "tech" in key or "growth" in key:
        return [
            "Balancear exposición growth/tech con factores defensivos o dividend",
            "Reforzar diversificación sectorial antes de ampliar posiciones dominantes",
        ]
    if "defensive_gap" in key or "dividend_gap" in key:
        return [
            "Canalizar nuevos aportes a segmentos defensivos o generadores de renta",
            "Usar diversificación por estilo además de diversificación geográfica",
        ]
    if "fragility" in key or "stress" in key:
        return [
            "Reducir concentración en activos o sectores que dominan la pérdida bajo stress",
            "Usar liquidez y diversificación para bajar fragilidad extrema",
        ]
    if "real_weak" in key or "nominal_weak" in key:
        return [
            "Revisar si la composición actual justifica el retorno esperado estructural",
            "Comparar el peso de liquidez y renta fija contra los objetivos de crecimiento real",
        ]
    return [
        "Revisar la señal analítica antes de sumar exposición en los bloques dominantes",
        "Usar nuevos aportes para corregir el desbalance detectado",
    ]
