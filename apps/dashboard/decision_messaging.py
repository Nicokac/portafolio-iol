from __future__ import annotations

from typing import Dict


def _build_decision_explanation(
    *,
    macro_state: Dict,
    recommendation: Dict,
    expected_impact: Dict,
    confidence: str,
    preferred_proposal: Dict | None,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> list[str]:
    recommendation_block = recommendation.get("block") or "el bloque sugerido"
    recommendation_reason = recommendation.get("reason") or "es la prioridad mas clara del mes"
    proposal_label = (preferred_proposal or {}).get("proposal_label") or "la mejor propuesta disponible"

    risk_line = "El riesgo no aumenta materialmente con la propuesta actual."
    if expected_impact.get("status") == "negative" or confidence == "Baja":
        risk_line = "El riesgo pide revision adicional antes de ejecutar la decision."
    elif expected_impact.get("status") == "mixed":
        risk_line = "El riesgo queda controlado, pero conviene revisar las senales mixtas."

    bullets = [
        f"Se refuerza {recommendation_block} porque {recommendation_reason}.",
        f"El contexto macro esta en {str(macro_state.get('label') or 'Indefinido').lower()} y {macro_state.get('summary') or 'no invalida la decision principal'}.",
        f"El impacto esperado de {proposal_label} es {expected_impact.get('status') or 'neutral'} en retorno, fragilidad y peor escenario.",
        risk_line,
    ]
    if (parking_signal or {}).get("has_signal"):
        bullets.append("Hay parking visible en cartera y conviene revisar esas restricciones antes de ejecutar la propuesta.")
    if recommendation.get("was_reprioritized_by_parking"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original quedaba condicionado por parking visible.")
    elif recommendation.get("is_conditioned_by_parking"):
        bullets.append("La recomendacion principal quedo condicionada por parking visible en el mismo bloque estrategico.")
    if recommendation.get("was_reprioritized_by_market_history"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original mostraba liquidez reciente debil.")
    elif recommendation.get("is_conditioned_by_market_history") or (market_history_signal or {}).get("has_signal"):
        bullets.append("La liquidez reciente del bloque sugerido pide validar mejor la ejecucion antes de comprar.")
    if (operation_execution_signal or {}).get("status") == "missing":
        bullets.append("La propuesta no tiene huella operativa comparable reciente y conviene validar costo real de ejecucion antes de comprar.")
    elif (operation_execution_signal or {}).get("status") == "partial":
        bullets.append("La propuesta solo tiene cobertura operativa parcial y pide confirmar la ejecucion real de todos los simbolos sugeridos.")
    elif (operation_execution_signal or {}).get("status") == "fragmented":
        bullets.append("La referencia operativa reciente existe, pero muestra fragmentacion y conviene cuidar la forma de entrada.")
    elif (operation_execution_signal or {}).get("status") == "costly":
        bullets.append("La huella operativa reciente muestra costo observado alto y conviene revisar aranceles reales antes de comprar.")
    elif (operation_execution_signal or {}).get("status") == "watch_cost":
        bullets.append("La huella operativa reciente muestra una friccion moderada y conviene monitorear mejor el costo visible de ejecucion.")
    if (preferred_proposal or {}).get("was_reprioritized_by_parking"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa mas limpia frente a parking visible.")
    elif (preferred_proposal or {}).get("was_reprioritized_by_market_history"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa con liquidez reciente mas limpia.")
    return bullets[:8]

def _build_decision_tracking_payload(
    *,
    preferred_proposal: Dict | None,
    recommendation: Dict,
    expected_impact: Dict,
    score: int,
    confidence: str,
    macro_state: Dict,
    portfolio_state: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
    execution_gate: Dict | None = None,
) -> Dict:
    preferred_proposal = preferred_proposal or {}
    parking_signal = parking_signal or {}
    market_history_signal = market_history_signal or {}
    operation_execution_signal = operation_execution_signal or {}
    execution_gate = execution_gate or {}
    return {
        "recommended_block": recommendation.get("block"),
        "recommended_amount": recommendation.get("amount"),
        "preferred_proposal": {
            "proposal_key": preferred_proposal.get("proposal_key"),
            "proposal_label": preferred_proposal.get("proposal_label"),
            "source_label": preferred_proposal.get("source_label"),
        },
        "purchase_plan": list(preferred_proposal.get("purchase_plan") or []),
        "simulation_delta": dict(preferred_proposal.get("simulation_delta") or {}),
        "score": score,
        "confidence": confidence,
        "macro_state": macro_state.get("key"),
        "portfolio_state": portfolio_state.get("key"),
        "expected_impact_status": expected_impact.get("status"),
        "governance": {
            "execution_gate_key": execution_gate.get("key"),
            "parking_signal_active": bool(parking_signal.get("has_signal")),
            "parking_blocks": [
                str(item.get("label") or "").strip()
                for item in (parking_signal.get("parking_blocks") or [])
                if str(item.get("label") or "").strip()
            ],
            "market_history_signal_active": bool(market_history_signal.get("has_signal")),
            "market_history_blocks": [
                str(item.get("label") or "").strip()
                for item in (
                    [{"label": block} for block in (market_history_signal.get("overlap_blocks") or [])]
                )
                if str(item.get("label") or "").strip()
            ],
            "operation_execution_signal_active": bool(operation_execution_signal.get("has_signal")),
            "operation_execution_signal_status": operation_execution_signal.get("status"),
            "operation_execution_tracked_symbols": list(operation_execution_signal.get("tracked_symbols") or []),
            "recommendation": {
                "block": recommendation.get("block"),
                "priority_label": recommendation.get("priority_label"),
                "conditioned_by_parking": bool(recommendation.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(recommendation.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(recommendation.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(recommendation.get("was_reprioritized_by_market_history")),
                "original_block_label": recommendation.get("original_block_label"),
            },
            "preferred_proposal": {
                "proposal_label": preferred_proposal.get("proposal_label"),
                "conditioned_by_parking": bool(preferred_proposal.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(preferred_proposal.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(preferred_proposal.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(preferred_proposal.get("was_reprioritized_by_market_history")),
            },
        },
    }
