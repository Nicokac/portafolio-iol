from typing import Dict

from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.dashboard.incremental_followup import (
    _build_incremental_adoption_check_item,
    _build_incremental_adoption_checklist_headline,
    _build_incremental_baseline_drift_alerts,
    _build_incremental_baseline_drift_explanation,
    _build_incremental_baseline_drift_summary,
    _build_incremental_followup_headline,
    _build_incremental_followup_summary_items,
    _build_incremental_snapshot_comparison,
    _build_incremental_snapshot_reapply_payload,
    _format_incremental_followup_status,
    _format_incremental_purchase_plan_summary,
    _summarize_incremental_drift_alerts,
)
from apps.dashboard.incremental_future_purchases import (
    _build_incremental_backlog_deferred_review_summary,
    _build_incremental_backlog_focus_item,
    _build_incremental_backlog_followup_filter_options,
    _build_incremental_backlog_manual_review_summary,
    _build_incremental_backlog_shortlist_item,
    _format_incremental_backlog_followup_filter_label,
    _normalize_incremental_backlog_followup_filter,
    get_incremental_proposal_tracking_baseline,
)
from apps.dashboard.incremental_history_enrichment import (
    _build_incremental_history_baseline_trace,
    _build_incremental_history_deferred_fit,
    _build_incremental_history_deferred_fit_counts,
    _build_incremental_history_priority,
    _build_incremental_history_priority_counts,
    _build_incremental_tactical_trace,
)
from apps.dashboard.incremental_history_sources import (
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_source_counts,
    _build_incremental_future_purchase_source_filter_options,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_history_deferred_fit_filter_options,
    _build_incremental_history_priority_filter_options,
    _build_incremental_history_sort_options,
    _sort_incremental_history_items,
)
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_front_summary_headline,
    _build_incremental_backlog_front_summary_items,
    _build_incremental_backlog_next_action,
    _build_incremental_backlog_prioritization_explanation,
    _build_incremental_backlog_prioritization_headline,
    _build_incremental_decision_executive_headline,
    _build_incremental_decision_executive_items,
    _build_incremental_history_available_filters,
    _build_incremental_history_headline,
    _build_incremental_operational_semaphore_headline,
    _build_incremental_operational_semaphore_items,
    _build_incremental_pending_backlog_explanation,
    _build_incremental_pending_backlog_headline,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
    _format_incremental_future_purchase_source_filter_label,
    _format_incremental_history_decision_filter_label,
    _format_incremental_history_deferred_fit_filter_label,
    _format_incremental_history_priority_filter_label,
    _format_incremental_history_sort_mode_label,
    _format_incremental_manual_decision_status,
    _format_incremental_operational_semaphore,
    _incremental_backlog_priority_order,
    _normalize_incremental_future_purchase_source_filter,
    _normalize_incremental_history_decision_filter,
    _normalize_incremental_history_deferred_fit_filter,
    _normalize_incremental_history_priority_filter,
    _normalize_incremental_history_sort_mode,
)
from apps.dashboard.incremental_backlog_decision import (
    build_incremental_adoption_checklist,
    build_incremental_decision_executive_summary,
    build_incremental_followup_executive_summary,
)
from apps.dashboard.incremental_backlog_analysis import (
    build_incremental_baseline_drift_payload,
    build_incremental_pending_backlog_vs_baseline_payload,
    build_incremental_proposal_history_payload,
)
from apps.dashboard.incremental_simulation import get_preferred_incremental_portfolio_proposal


def get_incremental_proposal_history(
    *,
    user,
    limit: int = 5,
    decision_status: str | None = None,
    priority_filter: str | None = None,
    deferred_fit_filter: str | None = None,
    future_purchase_source_filter: str | None = None,
    sort_mode: str | None = None,
    preferred_source: str | None = None,
    reactivated_snapshot_ids: list[int] | set[int] | tuple[int, ...] | None = None,
) -> Dict:
    """Retorna historial reciente de propuestas incrementales guardadas por el usuario."""
    service = IncrementalProposalHistoryService()
    normalized_filter = _normalize_incremental_history_decision_filter(decision_status)
    normalized_priority_filter = _normalize_incremental_history_priority_filter(priority_filter)
    normalized_deferred_fit_filter = _normalize_incremental_history_deferred_fit_filter(deferred_fit_filter)
    normalized_future_purchase_source_filter = _normalize_incremental_future_purchase_source_filter(
        future_purchase_source_filter
    )
    normalized_sort_mode = _normalize_incremental_history_sort_mode(sort_mode)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    return build_incremental_proposal_history_payload(
        service=service,
        user=user,
        limit=limit,
        normalized_filter=normalized_filter,
        normalized_priority_filter=normalized_priority_filter,
        normalized_deferred_fit_filter=normalized_deferred_fit_filter,
        normalized_future_purchase_source_filter=normalized_future_purchase_source_filter,
        normalized_sort_mode=normalized_sort_mode,
        preferred_source=preferred_source,
        baseline_payload=baseline_payload,
        reactivated_snapshot_ids=reactivated_snapshot_ids,
    )


def get_incremental_baseline_drift(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara el baseline incremental activo contra la propuesta preferida actual."""
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    return build_incremental_baseline_drift_payload(
        baseline_payload=baseline_payload,
        preferred_payload=preferred_payload,
    )


def get_incremental_pending_backlog_vs_baseline(*, user, limit: int = 5) -> Dict:
    """Compara el backlog pendiente de snapshots contra el baseline incremental activo."""
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    pending_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="pending")
    return build_incremental_pending_backlog_vs_baseline_payload(
        baseline_payload=baseline_payload,
        pending_history=pending_history,
    )


def get_incremental_backlog_prioritization(*, user, limit: int = 5, followup_filter: str | None = None) -> Dict:
    """Ordena el backlog pendiente en prioridades operativas explicitas."""
    backlog_payload = get_incremental_pending_backlog_vs_baseline(user=user, limit=limit)
    deferred_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="deferred")
    items = []
    for item in backlog_payload.get("items", []):
        priority = _classify_incremental_backlog_priority(item)
        enriched = dict(item)
        enriched["priority"] = priority
        enriched["priority_label"] = _format_incremental_backlog_priority(priority)
        enriched["next_action"] = _build_incremental_backlog_next_action(priority, item)
        items.append(enriched)

    ordered_items = sorted(
        items,
        key=lambda item: (
            0 if item["snapshot"].get("is_backlog_front") else 1,
            _incremental_backlog_priority_order(item["priority"]),
            -(item.get("score_difference") if item.get("score_difference") is not None else float("-inf")),
            item["snapshot"].get("proposal_label") or "",
        ),
    )

    counts = {
        "high": sum(1 for item in ordered_items if item["priority"] == "high"),
        "medium": sum(1 for item in ordered_items if item["priority"] == "medium"),
        "watch": sum(1 for item in ordered_items if item["priority"] == "watch"),
        "low": sum(1 for item in ordered_items if item["priority"] == "low"),
    }
    decision_counts = dict(backlog_payload.get("decision_counts", {}))
    top_item = ordered_items[0] if ordered_items else None
    economic_leader = next(
        (
            item
            for item in ordered_items
            if item.get("improves_profitability") and item.get("protects_fragility")
        ),
        None,
    )
    tactical_leader = next(
        (item for item in ordered_items if item.get("tactical_clean")),
        None,
    )
    normalized_followup_filter = _normalize_incremental_backlog_followup_filter(followup_filter)
    shortlist_items = [
        _build_incremental_backlog_shortlist_item(index=index + 1, item=item)
        for index, item in enumerate(ordered_items)
    ]
    followup_counts = {
        "review_now": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "review_now"),
        "monitor": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "monitor"),
        "hold": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "hold"),
    }
    if normalized_followup_filter:
        shortlist_items = [
            item for item in shortlist_items
            if str((item.get("followup") or {}).get("status") or "") == normalized_followup_filter
        ]
    shortlist = shortlist_items[:3]

    return {
        "baseline": backlog_payload.get("baseline"),
        "items": ordered_items,
        "count": len(ordered_items),
        "counts": counts,
        "manual_review_summary": _build_incremental_backlog_manual_review_summary(decision_counts),
        "deferred_review_summary": _build_incremental_backlog_deferred_review_summary(
            list(deferred_history.get("items") or []),
            decision_counts,
        ),
        "top_item": top_item,
        "economic_leader": _build_incremental_backlog_focus_item(economic_leader, focus="economic"),
        "tactical_leader": _build_incremental_backlog_focus_item(tactical_leader, focus="tactical"),
        "has_focus_split": bool(economic_leader or tactical_leader),
        "active_followup_filter": normalized_followup_filter or "all",
        "active_followup_filter_label": _format_incremental_backlog_followup_filter_label(normalized_followup_filter),
        "available_followup_filters": _build_incremental_backlog_followup_filter_options(
            normalized_followup_filter,
            followup_counts,
        ),
        "followup_counts": followup_counts,
        "shortlist": shortlist,
        "has_shortlist": bool(shortlist),
        "has_priorities": bool(ordered_items),
        "headline": _build_incremental_backlog_prioritization_headline(backlog_payload, counts, top_item),
        "explanation": _build_incremental_backlog_prioritization_explanation(backlog_payload, counts, top_item),
    }


def get_incremental_backlog_front_summary(*, user, limit: int = 5) -> Dict:
    """Resume en una sola lectura el baseline activo y el frente operativo del backlog."""
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    prioritization_payload = get_incremental_backlog_prioritization(user=user, limit=limit)

    baseline = baseline_payload.get("item")
    front_item = prioritization_payload.get("top_item")
    if baseline is None and front_item is None:
        status = "empty"
    elif baseline is None:
        status = "no_baseline"
    elif front_item is None:
        status = "baseline_only"
    elif front_item.get("snapshot", {}).get("is_backlog_front"):
        status = "manual_front"
    elif front_item.get("priority") == "high":
        status = "candidate_over_baseline"
    elif front_item.get("priority") == "medium":
        status = "watch"
    else:
        status = "baseline_holds"

    return {
        "status": status,
        "baseline": baseline,
        "front_item": front_item,
        "counts": prioritization_payload.get("counts", {}),
        "has_summary": bool(baseline or front_item),
        "headline": _build_incremental_backlog_front_summary_headline(status, baseline, front_item),
        "items": _build_incremental_backlog_front_summary_items(baseline, front_item, prioritization_payload),
    }


def get_incremental_backlog_operational_semaphore(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Clasifica el estado operativo incremental en semaforo reutilizando baseline, drift y backlog."""
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)
    prioritization = get_incremental_backlog_prioritization(user=user, limit=limit)

    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    front_status = front_summary.get("status", "empty")
    high_count = int(prioritization.get("counts", {}).get("high", 0))

    if drift_status == "unfavorable":
        status = "red"
    elif front_status == "candidate_over_baseline" or high_count > 0:
        status = "yellow"
    elif front_status == "manual_front":
        status = "yellow"
    elif drift_status in {"favorable", "stable"} and front_status in {"baseline_only", "empty"}:
        status = "green"
    else:
        status = "gray"

    return {
        "status": status,
        "label": _format_incremental_operational_semaphore(status),
        "headline": _build_incremental_operational_semaphore_headline(status, front_summary, drift_payload),
        "items": _build_incremental_operational_semaphore_items(drift_payload, front_summary, prioritization),
        "has_signal": bool(drift_payload.get("has_baseline") or front_summary.get("has_summary")),
    }


def get_incremental_followup_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza una lectura ejecutiva de seguimiento incremental para Planeacion."""
    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    return build_incremental_followup_executive_summary(
        preferred_payload=preferred_payload,
        baseline_payload=baseline_payload,
        drift_payload=drift_payload,
    )


def get_incremental_adoption_checklist(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Construye un checklist operativo para decidir adopcion de la propuesta incremental actual."""
    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    executive_payload = get_incremental_followup_executive_summary(query_params, user=user, capital_amount=capital_amount)
    return build_incremental_adoption_checklist(
        preferred_payload=preferred_payload,
        baseline_payload=baseline_payload,
        drift_payload=drift_payload,
        executive_payload=executive_payload,
    )


def get_incremental_decision_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Consolida la lectura ejecutiva de decision incremental en una sola sintesis."""
    semaphore = get_incremental_backlog_operational_semaphore(
        query_params,
        user=user,
        capital_amount=capital_amount,
        limit=limit,
    )
    followup = get_incremental_followup_executive_summary(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    checklist = get_incremental_adoption_checklist(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)
    return build_incremental_decision_executive_summary(
        semaphore=semaphore,
        followup=followup,
        checklist=checklist,
        front_summary=front_summary,
    )
