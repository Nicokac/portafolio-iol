from typing import Dict, List

from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.dashboard.incremental_history import (
    _build_incremental_manual_decision_headline,
    _format_incremental_backlog_priority,
    _format_incremental_manual_decision_status,
)


def _build_incremental_backlog_shortlist_item(*, index: int, item: Dict) -> Dict:
    snapshot = dict(item.get("snapshot") or {})
    simulation_delta = dict(snapshot.get("simulation_delta") or {})
    economic_edge = bool(item.get("improves_profitability") and item.get("protects_fragility"))
    tactical_edge = bool(item.get("tactical_clean"))
    conviction = _build_incremental_backlog_conviction(item, economic_edge=economic_edge, tactical_edge=tactical_edge)
    followup = _build_incremental_backlog_followup(conviction_level=str(conviction.get("level") or "low"))
    return {
        "rank": index,
        "proposal_label": snapshot.get("proposal_label") or "-",
        "priority": item.get("priority") or "low",
        "priority_label": item.get("priority_label") or _format_incremental_backlog_priority("low"),
        "next_action": item.get("next_action") or "",
        "selected_context": snapshot.get("selected_context") or "",
        "score_difference": item.get("score_difference"),
        "expected_return_change": simulation_delta.get("expected_return_change"),
        "fragility_change": simulation_delta.get("fragility_change"),
        "scenario_loss_change": simulation_delta.get("scenario_loss_change"),
        "snapshot_id": snapshot.get("id"),
        "reapply_querystring": snapshot.get("reapply_querystring") or "",
        "reapply_truncated": bool(snapshot.get("reapply_truncated")),
        "is_backlog_front": bool(snapshot.get("is_backlog_front")),
        "is_tracking_baseline": bool(snapshot.get("is_tracking_baseline")),
        "economic_edge": economic_edge,
        "tactical_edge": tactical_edge,
        "conviction": conviction,
        "followup": followup,
    }


def _build_incremental_backlog_focus_item(item: Dict | None, *, focus: str) -> Dict | None:
    if not item:
        return None
    shortlist_item = _build_incremental_backlog_shortlist_item(index=1, item=item)
    if focus == "economic":
        shortlist_item["focus_label"] = "Líder económico"
        shortlist_item["focus_summary"] = "Mejora retorno esperado sin deterioro material de fragilidad."
    else:
        shortlist_item["focus_label"] = "Líder táctico"
        shortlist_item["focus_summary"] = "Conserva la ejecutabilidad más limpia para reconsiderar una compra."
    return shortlist_item


def _build_incremental_backlog_conviction(item: Dict, *, economic_edge: bool, tactical_edge: bool) -> Dict:
    priority = str(item.get("priority") or "low")
    if priority == "high" and economic_edge and tactical_edge:
        return {
            "level": "high",
            "label": "Convicción alta",
            "summary": "Mejora la ecuación económica y conserva una ejecutabilidad táctica limpia.",
        }
    if priority in {"high", "medium"} and (economic_edge or tactical_edge):
        return {
            "level": "medium",
            "label": "Convicción media",
            "summary": "Tiene mérito para reabrir la compra, pero no domina ambos frentes al mismo tiempo.",
        }
    return {
        "level": "low",
        "label": "Convicción baja",
        "summary": "Conviene mantenerla en observación hasta que mejore retorno, fragilidad o ejecutabilidad.",
    }


def _build_incremental_backlog_followup(*, conviction_level: str) -> Dict:
    if conviction_level == "high":
        return {
            "status": "review_now",
            "label": "Revisar ya",
            "summary": "Vale la pena reabrir esta propuesta como candidata inmediata de compra futura.",
        }
    if conviction_level == "medium":
        return {
            "status": "monitor",
            "label": "Monitorear",
            "summary": "Conviene seguirla de cerca y revalidarla antes de mover el proximo aporte.",
        }
    return {
        "status": "hold",
        "label": "En espera",
        "summary": "No conviene priorizarla ahora; queda como referencia secundaria del backlog.",
    }


def _normalize_incremental_backlog_followup_filter(followup_filter: str | None) -> str | None:
    normalized = str(followup_filter or "").strip().lower()
    if normalized in {"review_now", "monitor", "hold"}:
        return normalized
    return None


def _format_incremental_backlog_followup_filter_label(followup_filter: str | None) -> str:
    mapping = {
        "review_now": "Revisar ya",
        "monitor": "Monitorear",
        "hold": "En espera",
    }
    return mapping.get(str(followup_filter or "").strip().lower(), "Todas")


def _build_incremental_backlog_followup_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "review_now", "label": "Revisar ya", "count": int(counts.get("review_now", 0))},
        {"key": "monitor", "label": "Monitorear", "count": int(counts.get("monitor", 0))},
        {"key": "hold", "label": "En espera", "count": int(counts.get("hold", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_backlog_manual_review_summary(decision_counts: Dict[str, int]) -> Dict:
    pending_count = int(decision_counts.get("pending", 0))
    deferred_count = int(decision_counts.get("deferred", 0))
    accepted_count = int(decision_counts.get("accepted", 0))
    rejected_count = int(decision_counts.get("rejected", 0))
    closed_count = accepted_count + rejected_count
    reviewed_count = deferred_count + closed_count
    if pending_count > 0:
        headline = "Todavia hay propuestas vigentes para futuras compras dentro del backlog."
    elif reviewed_count > 0:
        headline = "El backlog vigente ya fue revisado manualmente y hoy no quedan propuestas pendientes."
    else:
        headline = "Todavia no hay decisiones manuales suficientes para leer cobertura operativa del backlog."
    return {
        "pending_count": pending_count,
        "deferred_count": deferred_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "closed_count": closed_count,
        "reviewed_count": reviewed_count,
        "headline": headline,
        "has_manual_reviews": bool(reviewed_count),
    }


def _build_incremental_backlog_deferred_review_summary(items: List[Dict], decision_counts: Dict[str, int]) -> Dict:
    deferred_count = int(decision_counts.get("deferred", len(items)))
    reactivable_items = [
        item
        for item in items
        if str((item.get("history_priority") or {}).get("priority") or "") in {"high", "medium"}
    ]
    archivable_items = [
        item
        for item in items
        if str((item.get("history_priority") or {}).get("priority") or "") not in {"high", "medium"}
    ]
    top_reactivable = reactivable_items[0] if reactivable_items else None

    if reactivable_items:
        headline = "Parte de las diferidas todavia conserva fit suficiente para reactivarse como futura compra."
    elif deferred_count > 0:
        headline = "Las diferidas actuales ya no muestran suficiente fit economico o tactico y conviene archivarlas."
    else:
        headline = "Todavia no hay diferidas revisadas para separar entre reactivables y archivables."

    return {
        "deferred_count": deferred_count,
        "reactivable_count": len(reactivable_items),
        "archivable_count": len(archivable_items),
        "top_reactivable_label": (top_reactivable or {}).get("proposal_label") or "",
        "top_reactivable_priority_label": str(((top_reactivable or {}).get("history_priority") or {}).get("priority_label") or ""),
        "has_reactivable": bool(reactivable_items),
        "headline": headline,
    }


def get_incremental_proposal_tracking_baseline(*, user) -> Dict:
    """Retorna el snapshot incremental activo como baseline de seguimiento del usuario."""

    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return {
            "item": None,
            "has_baseline": False,
        }
    item = IncrementalProposalHistoryService().get_tracking_baseline(user=user)
    return {
        "item": item,
        "has_baseline": item is not None,
    }


def get_incremental_manual_decision_summary(*, user) -> Dict:
    """Resume la ultima decision manual persistida sobre propuestas incrementales guardadas."""

    item = IncrementalProposalHistoryService().get_latest_manual_decision(user=user)
    status = str((item or {}).get("manual_decision_status") or "pending")
    return {
        "item": item,
        "has_decision": item is not None,
        "status": status,
        "status_label": _format_incremental_manual_decision_status(status),
        "headline": _build_incremental_manual_decision_headline(item),
    }
