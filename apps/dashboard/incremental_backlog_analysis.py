from typing import Dict

from apps.dashboard.incremental_followup import (
    _build_incremental_baseline_drift_alerts,
    _build_incremental_baseline_drift_explanation,
    _build_incremental_baseline_drift_summary,
    _build_incremental_snapshot_comparison,
    _build_incremental_snapshot_reapply_payload,
    _format_incremental_followup_status,
)
from apps.dashboard.incremental_history import (
    _build_incremental_history_available_filters,
    _build_incremental_history_headline,
    _build_incremental_pending_backlog_explanation,
    _build_incremental_pending_backlog_headline,
    _format_incremental_future_purchase_source_filter_label,
    _format_incremental_history_decision_filter_label,
    _format_incremental_history_deferred_fit_filter_label,
    _format_incremental_history_priority_filter_label,
    _format_incremental_history_sort_mode_label,
    _format_incremental_manual_decision_status,
)
from apps.dashboard.incremental_history_enrichment import (
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_source_counts,
    _build_incremental_future_purchase_source_filter_options,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_history_baseline_trace,
    _build_incremental_history_deferred_fit,
    _build_incremental_history_deferred_fit_counts,
    _build_incremental_history_deferred_fit_filter_options,
    _build_incremental_history_priority,
    _build_incremental_history_priority_counts,
    _build_incremental_history_priority_filter_options,
    _build_incremental_history_sort_options,
    _build_incremental_tactical_trace,
    _sort_incremental_history_items,
)


def build_incremental_proposal_history_payload(
    *,
    service,
    user,
    limit: int,
    normalized_filter: str | None,
    normalized_priority_filter: str | None,
    normalized_deferred_fit_filter: str | None,
    normalized_future_purchase_source_filter: str | None,
    normalized_sort_mode: str,
    preferred_source: str | None,
    baseline_payload: Dict,
    reactivated_snapshot_ids: list[int] | set[int] | tuple[int, ...] | None = None,
) -> Dict:
    fetch_limit = max(int(limit), getattr(service, "MAX_SNAPSHOTS_PER_USER", 10))
    raw_items = service.list_recent(user=user, limit=fetch_limit, decision_status=normalized_filter)
    counts = service.get_decision_counts(user=user)
    baseline_item = baseline_payload.get("item")
    normalized_reactivated_snapshot_ids = {
        int(snapshot_id)
        for snapshot_id in list(reactivated_snapshot_ids or [])
        if str(snapshot_id).strip()
    }
    items = []
    for item in raw_items:
        reapply = _build_incremental_snapshot_reapply_payload(item)
        enriched = service.normalize_serialized_snapshot(item)
        enriched["manual_decision_status_label"] = _format_incremental_manual_decision_status(
            str(item.get("manual_decision_status") or "pending")
        )
        enriched["is_backlog_front_label"] = "Al frente del backlog" if item.get("is_backlog_front") else ""
        enriched["tactical_trace"] = _build_incremental_tactical_trace(item)
        enriched["baseline_trace"] = _build_incremental_history_baseline_trace(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["history_priority"] = _build_incremental_history_priority(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["deferred_fit"] = _build_incremental_history_deferred_fit(enriched)
        enriched["future_purchase_context"] = _build_incremental_future_purchase_history_context(
            enriched,
            reactivated_snapshot_ids=normalized_reactivated_snapshot_ids,
        )
        enriched.update(reapply)
        items.append(enriched)

    priority_counts = _build_incremental_history_priority_counts(items)
    deferred_fit_counts = _build_incremental_history_deferred_fit_counts(items)
    future_purchase_source_counts = _build_incremental_future_purchase_source_counts(items)
    if normalized_priority_filter:
        items = [
            item
            for item in items
            if str((item.get("history_priority") or {}).get("priority") or "") == normalized_priority_filter
        ]
    if normalized_deferred_fit_filter:
        items = [
            item
            for item in items
            if str((item.get("deferred_fit") or {}).get("status") or "") == normalized_deferred_fit_filter
        ]
    if normalized_future_purchase_source_filter:
        items = [
            item
            for item in items
            if str((item.get("future_purchase_context") or {}).get("source") or "")
            == normalized_future_purchase_source_filter
        ]

    items = _sort_incremental_history_items(
        items,
        sort_mode=normalized_sort_mode,
        preferred_source=preferred_source,
    )
    items = items[: max(int(limit), 0)]
    future_purchase_source_summary = _build_incremental_future_purchase_source_summary(
        future_purchase_source_counts,
        active_filter=normalized_future_purchase_source_filter,
    )
    future_purchase_source_quality_summary = _build_incremental_future_purchase_source_quality_summary(items)

    return {
        "items": items,
        "count": len(items),
        "has_history": bool(items),
        "active_filter": normalized_filter or "all",
        "active_filter_label": _format_incremental_history_decision_filter_label(normalized_filter),
        "active_priority_filter": normalized_priority_filter or "all",
        "active_priority_filter_label": _format_incremental_history_priority_filter_label(normalized_priority_filter),
        "active_deferred_fit_filter": normalized_deferred_fit_filter or "all",
        "active_deferred_fit_filter_label": _format_incremental_history_deferred_fit_filter_label(
            normalized_deferred_fit_filter
        ),
        "active_future_purchase_source_filter": normalized_future_purchase_source_filter or "all",
        "active_future_purchase_source_filter_label": _format_incremental_future_purchase_source_filter_label(
            normalized_future_purchase_source_filter
        ),
        "active_sort_mode": normalized_sort_mode,
        "active_sort_mode_label": _format_incremental_history_sort_mode_label(normalized_sort_mode),
        "decision_counts": counts,
        "available_filters": _build_incremental_history_available_filters(normalized_filter, counts),
        "available_priority_filters": _build_incremental_history_priority_filter_options(
            normalized_priority_filter,
            priority_counts,
        ),
        "available_deferred_fit_filters": _build_incremental_history_deferred_fit_filter_options(
            normalized_deferred_fit_filter,
            deferred_fit_counts,
        ),
        "available_future_purchase_source_filters": _build_incremental_future_purchase_source_filter_options(
            normalized_future_purchase_source_filter,
            future_purchase_source_counts,
        ),
        "available_sort_modes": _build_incremental_history_sort_options(normalized_sort_mode),
        "priority_counts": priority_counts,
        "deferred_fit_counts": deferred_fit_counts,
        "future_purchase_source_counts": future_purchase_source_counts,
        "future_purchase_source_summary": future_purchase_source_summary,
        "future_purchase_source_quality_summary": future_purchase_source_quality_summary,
        "headline": _build_incremental_history_headline(
            normalized_filter,
            counts,
            len(items),
            priority_filter=normalized_priority_filter,
            deferred_fit_filter=normalized_deferred_fit_filter,
            future_purchase_source_filter=normalized_future_purchase_source_filter,
            sort_mode=normalized_sort_mode,
        ),
    }


def build_incremental_baseline_drift_payload(*, baseline_payload: Dict, preferred_payload: Dict) -> Dict:
    baseline = baseline_payload.get("item")
    current_preferred = preferred_payload.get("preferred")
    comparison = None
    if baseline and current_preferred:
        comparison = _build_incremental_snapshot_comparison(baseline, current_preferred)

    summary = _build_incremental_baseline_drift_summary(comparison)
    alerts = _build_incremental_baseline_drift_alerts(baseline, current_preferred, summary)
    return {
        "baseline": baseline,
        "current_preferred": current_preferred,
        "comparison": comparison,
        "summary": summary,
        "alerts": alerts,
        "alerts_count": len(alerts),
        "has_alerts": bool(alerts),
        "has_drift": comparison is not None,
        "has_baseline": baseline is not None,
        "explanation": _build_incremental_baseline_drift_explanation(baseline, current_preferred, comparison, summary),
    }


def build_incremental_pending_backlog_vs_baseline_payload(*, baseline_payload: Dict, pending_history: Dict) -> Dict:
    baseline = baseline_payload.get("item")
    pending_items = list(pending_history.get("items") or [])
    comparisons = []
    for item in pending_items:
        comparison = _build_incremental_snapshot_comparison(baseline, item) if baseline else None
        summary = _build_incremental_baseline_drift_summary(comparison)
        baseline_trace = dict(item.get("baseline_trace") or {})
        tactical_trace = dict(item.get("tactical_trace") or {})
        comparison_metrics = {metric.get("key"): metric for metric in (comparison or {}).get("metrics", [])}
        expected_direction = str((comparison_metrics.get("expected_return_change") or {}).get("direction") or "neutral")
        fragility_direction = str((comparison_metrics.get("fragility_change") or {}).get("direction") or "neutral")
        scenario_direction = str((comparison_metrics.get("scenario_loss_change") or {}).get("direction") or "neutral")
        tactical_clean = bool(
            not tactical_trace.get("has_trace")
            or any(
                str(badge.get("label") or "").strip() == "Alternativa promovida"
                for badge in tactical_trace.get("badges", [])
            )
        )
        improves_profitability = expected_direction == "favorable"
        protects_fragility = fragility_direction != "unfavorable"
        comparisons.append(
            {
                "snapshot": item,
                "comparison": comparison,
                "summary": summary,
                "status_label": _format_incremental_followup_status(summary.get("status", "unavailable")),
                "score_difference": None if comparison is None else comparison.get("score_difference"),
                "beats_baseline": bool(comparison and comparison.get("winner") == "current"),
                "loses_vs_baseline": bool(comparison and comparison.get("winner") == "saved"),
                "ties_baseline": bool(comparison and comparison.get("winner") == "tie"),
                "improves_profitability": improves_profitability,
                "protects_fragility": protects_fragility,
                "tactical_clean": tactical_clean,
                "comparison_fit": {
                    "expected_direction": expected_direction,
                    "fragility_direction": fragility_direction,
                    "scenario_direction": scenario_direction,
                    "improves_profitability": improves_profitability,
                    "protects_fragility": protects_fragility,
                    "tactical_clean": tactical_clean,
                    "baseline_headline": baseline_trace.get("headline") or "",
                },
            }
        )

    better_count = sum(1 for item in comparisons if item["beats_baseline"])
    worse_count = sum(1 for item in comparisons if item["loses_vs_baseline"])
    tie_count = sum(1 for item in comparisons if item["ties_baseline"])
    comparable_items = [item for item in comparisons if item.get("comparison")]
    best_candidate = None
    if comparable_items:
        best_candidate = sorted(
            comparable_items,
            key=lambda item: (
                1 if item.get("improves_profitability") else 0,
                1 if item.get("protects_fragility") else 0,
                1 if item.get("tactical_clean") else 0,
                1 if item["beats_baseline"] else 0,
                1 if item["ties_baseline"] else 0,
                item.get("score_difference")
                if item.get("score_difference") is not None
                else float("-inf"),
            ),
            reverse=True,
        )[0]

    return {
        "baseline": baseline,
        "items": comparisons,
        "count": len(comparisons),
        "pending_count": pending_history.get("decision_counts", {}).get("pending", len(comparisons)),
        "decision_counts": dict(pending_history.get("decision_counts", {})),
        "has_baseline": baseline is not None,
        "has_pending_backlog": bool(pending_items),
        "has_comparable_items": bool(comparable_items),
        "better_count": better_count,
        "worse_count": worse_count,
        "tie_count": tie_count,
        "best_candidate": best_candidate,
        "headline": _build_incremental_pending_backlog_headline(
            baseline,
            pending_history,
            better_count,
            worse_count,
            tie_count,
        ),
        "explanation": _build_incremental_pending_backlog_explanation(
            baseline,
            pending_history,
            best_candidate,
            better_count,
            worse_count,
        ),
    }
