from __future__ import annotations

from typing import Dict
from urllib.parse import urlencode

from apps.dashboard.decision_engine_utils import _coerce_optional_float
from apps.dashboard.decision_recommendation import (
    _build_decision_preferred_proposal,
    _build_decision_recommendation,
    _build_decision_suggested_assets,
)
from apps.dashboard.decision_execution import (
    _annotate_preferred_proposal_with_execution_quality,
    _build_decision_action_suggestions,
    _build_decision_execution_gate,
    _build_decision_market_history_signal,
    _build_decision_operation_execution_signal,
    _build_decision_parking_signal,
)
from apps.dashboard.decision_messaging import (
    _build_decision_explanation,
    _build_decision_tracking_payload,
)


def _build_decision_engine_query_stamp(query_params) -> str:
    if query_params is None:
        return "none"
    if isinstance(query_params, dict):
        items = sorted((str(key), str(value)) for key, value in query_params.items())
        return urlencode(items)
    items_method = getattr(query_params, "lists", None)
    if callable(items_method):
        normalized = []
        for key, values in query_params.lists():
            for value in values:
                normalized.append((str(key), str(value)))
        return urlencode(sorted(normalized))
    return str(query_params)


def _build_decision_macro_state(macro_local: Dict | None) -> Dict:
    macro_local = macro_local or {}
    fx_state = str(macro_local.get("fx_signal_state") or "").strip().lower()
    riesgo_pais = _coerce_optional_float(macro_local.get("riesgo_pais_arg"))
    uva_annualized = _coerce_optional_float(macro_local.get("uva_annualized_pct_30d"))

    if fx_state == "divergent" or (riesgo_pais is not None and riesgo_pais >= 900):
        return {
            "key": "crisis",
            "label": "Crisis",
            "score_component": 4,
            "summary": "El contexto local exige maxima cautela antes de sumar riesgo.",
        }
    if fx_state == "tensioned" or (riesgo_pais is not None and riesgo_pais >= 700) or (
        uva_annualized is not None and uva_annualized >= 35
    ):
        return {
            "key": "tension",
            "label": "Tension",
            "score_component": 13,
            "summary": "Hay tension local y conviene evitar decisiones agresivas.",
        }
    if fx_state or riesgo_pais is not None or uva_annualized is not None:
        return {
            "key": "normal",
            "label": "Normal",
            "score_component": 25,
            "summary": "No hay una senal macro dominante que invalide el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto macro suficiente para una lectura mas firme.",
    }


def _build_decision_portfolio_state(analytics: Dict | None) -> Dict:
    analytics = analytics or {}
    stress = analytics.get("stress_testing") or {}
    expected = analytics.get("expected_return") or {}
    risk = analytics.get("risk_contribution") or {}
    top_asset = risk.get("top_asset") or {}

    fragility_score = _coerce_optional_float(stress.get("fragility_score"))
    total_loss_pct = _coerce_optional_float(stress.get("total_loss_pct"))
    real_expected_return_pct = _coerce_optional_float(expected.get("real_expected_return_pct"))
    top_asset_contribution = _coerce_optional_float(top_asset.get("contribution_pct"))

    if (fragility_score is not None and fragility_score >= 70) or (
        total_loss_pct is not None and total_loss_pct < -20
    ):
        return {
            "key": "riesgo",
            "label": "Riesgo",
            "score_component": 5,
            "summary": "La cartera ya muestra fragilidad relevante y pide prudencia.",
        }
    if (real_expected_return_pct is not None and real_expected_return_pct < 0) or (
        top_asset_contribution is not None and top_asset_contribution > 0.25
    ):
        return {
            "key": "desbalance",
            "label": "Desbalance",
            "score_component": 14,
            "summary": "Hay senales de concentracion o retorno real debil a corregir.",
        }
    if (
        fragility_score is not None
        or total_loss_pct is not None
        or real_expected_return_pct is not None
        or top_asset_contribution is not None
    ):
        return {
            "key": "ok",
            "label": "OK",
            "score_component": 25,
            "summary": "La cartera admite un aporte incremental sin desviar el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto suficiente sobre el estado actual de la cartera.",
    }


def _build_decision_expected_impact(simulation: Dict | None) -> Dict:
    simulation = simulation or {}
    delta = dict(simulation.get("delta") or {})
    expected_return = _coerce_optional_float(delta.get("expected_return_change"))
    fragility = _coerce_optional_float(delta.get("fragility_change"))
    worst_case = _coerce_optional_float(delta.get("scenario_loss_change"))
    risk_concentration = _coerce_optional_float(delta.get("risk_concentration_change"))

    favorable = 0
    unfavorable = 0
    if expected_return is not None:
        favorable += 1 if expected_return >= 0 else 0
        unfavorable += 1 if expected_return < 0 else 0
    if fragility is not None:
        favorable += 1 if fragility <= 0 else 0
        unfavorable += 1 if fragility > 0 else 0
    if worst_case is not None:
        favorable += 1 if worst_case >= 0 else 0
        unfavorable += 1 if worst_case < 0 else 0
    if risk_concentration is not None:
        favorable += 1 if risk_concentration <= 0 else 0
        unfavorable += 1 if risk_concentration > 0 else 0

    if favorable and not unfavorable:
        status = "positive"
        score_component = 25
    elif unfavorable and not favorable:
        status = "negative"
        score_component = 5
    elif favorable or unfavorable:
        status = "mixed"
        score_component = 14
    else:
        status = "neutral"
        score_component = 12

    return {
        "return": expected_return,
        "fragility": fragility,
        "worst_case": worst_case,
        "risk_concentration": risk_concentration,
        "status": status,
        "score_component": score_component,
        "summary": str(simulation.get("interpretation") or "Impacto incremental no disponible."),
    }


def _compute_decision_score(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    recommendation: Dict,
    suggested_assets: list[Dict],
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> int:
    recommendation_score = 0
    if recommendation.get("has_recommendation"):
        recommendation_score += 10
    if suggested_assets:
        recommendation_score += 5
    if len(suggested_assets) >= 2:
        recommendation_score += 3
    if preferred_proposal:
        recommendation_score += 7
    recommendation_score = min(recommendation_score, 25)

    total = (
        int(macro_state.get("score_component") or 0)
        + int(portfolio_state.get("score_component") or 0)
        + recommendation_score
        + int(expected_impact.get("score_component") or 0)
    )
    if (parking_signal or {}).get("has_signal"):
        total -= 5
    if (market_history_signal or {}).get("has_signal"):
        total -= 4
    if (operation_execution_signal or {}).get("status") in {"missing", "partial"}:
        total -= 4
    elif (operation_execution_signal or {}).get("status") == "fragmented":
        total -= 2
    elif (operation_execution_signal or {}).get("status") == "costly":
        total -= 3
    elif (operation_execution_signal or {}).get("status") == "watch_cost":
        total -= 1
    return max(0, min(100, total))


def _build_decision_recommendation_context(portfolio_scope: Dict | None) -> str | None:
    portfolio_scope = portfolio_scope or {}
    cash_ratio_total = _coerce_optional_float(portfolio_scope.get("cash_ratio_total")) or 0.0
    invested_ratio_total = _coerce_optional_float(portfolio_scope.get("invested_ratio_total")) or 0.0

    if cash_ratio_total > 0.30:
        return "high_cash"
    if invested_ratio_total > 0.90:
        return "fully_invested"
    return None


def _build_decision_strategy_bias(recommendation_context: str | None) -> str | None:
    if recommendation_context == "high_cash":
        return "deploy_cash"
    if recommendation_context == "fully_invested":
        return "rebalance"
    return None


def _build_decision_finviz_support(
    *,
    finviz_shortlist: Dict | None,
    finviz_watchlist: Dict | None,
) -> Dict:
    finviz_shortlist = finviz_shortlist or {}
    finviz_watchlist = finviz_watchlist or {}

    external = ((finviz_watchlist.get("external_candidates") or [])[:1] or [None])[0]
    reinforce = ((finviz_watchlist.get("reinforce_candidates") or [])[:1] or [None])[0]

    if not external and not reinforce:
        return {
            "has_signal": False,
            "title": "Apoyo Finviz para esta decision",
            "summary": "Todavia no hay cobertura Finviz suficiente para sumar contraste externo a esta decision.",
            "external_candidate": None,
            "reinforce_candidate": None,
        }

    summary_parts = []
    if external:
        summary_parts.append(
            f"afuera lidera {external.get('internal_symbol')} con score "
            f"{float(external.get('composite_buy_score') or 0):.1f}"
        )
    if reinforce:
        summary_parts.append(
            f"en cartera se sostiene {reinforce.get('internal_symbol')} con score "
            f"{float(reinforce.get('composite_buy_score') or 0):.1f}"
        )

    return {
        "has_signal": True,
        "title": "Apoyo Finviz para esta decision",
        "summary": " | ".join(summary_parts) if summary_parts else "Hay lectura Finviz disponible como contraste.",
        "external_candidate": external,
        "reinforce_candidate": reinforce,
    }


def _manual_execution_readiness_rank(status: str) -> int:
    normalized = str(status or "pending").strip()
    if normalized == "ready":
        return 3
    if normalized == "monitor":
        return 2
    if normalized == "review_execution":
        return 1
    return 0


def _build_manual_incremental_execution_readiness(
    *,
    proposal: Dict | None,
    operation_execution_signal: Dict | None = None,
) -> Dict:
    proposal = proposal or {}
    operation_execution_signal = operation_execution_signal or {}
    proposal_label = str(proposal.get("proposal_label") or proposal.get("label") or "este plan").strip()
    execution_quality = proposal.get("execution_quality") or {}
    execution_order_summary = str(execution_quality.get("execution_order_summary") or "").strip()
    signal_status = str(operation_execution_signal.get("status") or "none").strip()

    if signal_status in {"missing", "partial"}:
        return {
            "status": "review_execution",
            "label": "Validar ejecucion",
            "tone": "warning",
            "summary": execution_order_summary or f"{proposal_label} necesita validar mejor su ejecucion real antes de pasar a compra.",
        }
    if signal_status in {"fragmented", "costly", "watch_cost"}:
        return {
            "status": "monitor",
            "label": "Seguir observando",
            "tone": "secondary",
            "summary": (
                operation_execution_signal.get("summary")
                or execution_order_summary
                or f"{proposal_label} tiene referencia operativa, pero conviene cuidar la forma de entrada."
            ),
        }
    if proposal:
        return {
            "status": "ready",
            "label": "Listo para ejecutar",
            "tone": "success",
            "summary": execution_order_summary or f"{proposal_label} ya tiene fit operativo suficiente para ejecutarse como mejor plan manual.",
        }
    return {
        "status": "pending",
        "label": "Sin lectura",
        "tone": "secondary",
        "summary": "",
    }


def _build_manual_incremental_execution_readiness_summary(best_proposal: Dict | None) -> Dict:
    best_proposal = best_proposal or {}
    readiness = dict(best_proposal.get("execution_readiness") or {})
    if not best_proposal or not readiness:
        return {
            "has_summary": False,
            "status": "pending",
            "label": "",
            "tone": "secondary",
            "headline": "",
            "summary": "",
        }
    proposal_label = str(best_proposal.get("proposal_label") or best_proposal.get("label") or "este plan").strip()
    status = str(readiness.get("status") or "pending")
    if status == "ready":
        headline = f"{proposal_label} es el mejor plan manual y hoy queda listo para ejecutar."
    elif status == "review_execution":
        headline = f"{proposal_label} lidera el comparador manual, pero pide validar ejecucion antes de comprar."
    else:
        headline = f"{proposal_label} lidera el comparador manual, pero por ahora conviene seguir observando su forma de entrada."
    return {
        "has_summary": True,
        "status": status,
        "label": readiness.get("label") or "",
        "tone": readiness.get("tone") or "secondary",
        "headline": headline,
        "summary": readiness.get("summary") or "",
    }


def _compute_decision_confidence(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    operation_execution_signal: Dict | None = None,
) -> str:
    if preferred_proposal is None:
        return "Baja"
    if expected_impact.get("status") == "negative":
        return "Baja"
    if macro_state.get("key") == "crisis":
        return "Baja"
    if (
        macro_state.get("key") == "normal"
        and portfolio_state.get("key") != "riesgo"
        and expected_impact.get("status") in {"positive", "neutral"}
    ):
        confidence = "Alta"
    else:
        confidence = "Media"

    if (
        (parking_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("was_reprioritized_by_parking")
        or (preferred_proposal or {}).get("is_conditioned_by_parking")
        or (market_history_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("is_conditioned_by_market_history")
        or (operation_execution_signal or {}).get("status") in {"missing", "partial", "fragmented", "costly", "watch_cost"}
    ):
        if confidence == "Alta":
            return "Media"
        return "Baja"
    return confidence
