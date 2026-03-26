from typing import Dict

from apps.dashboard.incremental_history import _incremental_backlog_priority_order


def _build_incremental_future_purchase_source_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "backlog_nuevo": sum(
            1 for item in items if str((item.get("future_purchase_context") or {}).get("source") or "") == "backlog_nuevo"
        ),
        "reactivadas": sum(
            1 for item in items if str((item.get("future_purchase_context") or {}).get("source") or "") == "reactivadas"
        ),
    }


def _build_incremental_future_purchase_source_summary(
    counts: Dict[str, int],
    *,
    active_filter: str | None = None,
) -> Dict:
    backlog_count = int(counts.get("backlog_nuevo", 0))
    reactivated_count = int(counts.get("reactivadas", 0))
    total = backlog_count + reactivated_count

    if active_filter == "backlog_nuevo":
        dominant_source = "backlog_nuevo"
    elif active_filter == "reactivadas":
        dominant_source = "reactivadas"
    elif backlog_count > reactivated_count:
        dominant_source = "backlog_nuevo"
    elif reactivated_count > backlog_count:
        dominant_source = "reactivadas"
    elif total > 0:
        dominant_source = "mixto"
    else:
        dominant_source = "none"

    if dominant_source == "backlog_nuevo":
        headline = "Hoy domina backlog nuevo dentro del historial filtrado."
        dominant_label = "Domina backlog nuevo"
    elif dominant_source == "reactivadas":
        headline = "Hoy dominan reactivadas dentro del historial filtrado."
        dominant_label = "Dominan reactivadas"
    elif dominant_source == "mixto":
        headline = "El historial filtrado hoy queda equilibrado entre backlog nuevo y reactivadas."
        dominant_label = "Lectura mixta"
    else:
        headline = "Todavia no hay futuras compras visibles para resumir por fuente."
        dominant_label = "Sin futuras compras"

    if total == 0:
        summary = "No hay snapshots visibles clasificados como backlog nuevo o reactivadas."
    else:
        summary = (
            f"{backlog_count} provienen de backlog nuevo y {reactivated_count} de reactivadas dentro del historial filtrado."
        )

    return {
        "backlog_nuevo_count": backlog_count,
        "reactivadas_count": reactivated_count,
        "total_count": total,
        "dominant_source": dominant_source,
        "dominant_label": dominant_label,
        "headline": headline,
        "summary": summary,
        "has_visible_sources": total > 0,
    }


def _is_incremental_history_tactical_clean(item: Dict) -> bool:
    tactical_trace = dict(item.get("tactical_trace") or {})
    if not tactical_trace.get("has_trace"):
        return True
    return any(
        str(badge.get("label") or "").strip() == "Alternativa promovida"
        for badge in list(tactical_trace.get("badges") or [])
    )


def _build_incremental_future_purchase_source_quality_item(source: str, items: list[Dict]) -> Dict:
    relevant_items = [
        item
        for item in items
        if str((item.get("future_purchase_context") or {}).get("source") or "") == source
    ]
    count = len(relevant_items)
    label = "Backlog nuevo" if source == "backlog_nuevo" else "Reactivadas"

    if count == 0:
        return {
            "source": source,
            "label": label,
            "count": 0,
            "priority_fit_pct": 0.0,
            "economic_fit_pct": 0.0,
            "tactical_clean_pct": 0.0,
            "average_comparison_score": None,
            "quality_score": 0.0,
            "has_items": False,
        }

    priority_fit_count = sum(
        1
        for item in relevant_items
        if str((item.get("history_priority") or {}).get("priority") or "") in {"high", "medium"}
    )
    economic_fit_count = sum(
        1
        for item in relevant_items
        if (item.get("simulation_delta") or {}).get("expected_return_change") is not None
        and float((item.get("simulation_delta") or {}).get("expected_return_change") or 0.0) > 0
        and float((item.get("simulation_delta") or {}).get("fragility_change") or 0.0) <= 0
    )
    tactical_clean_count = sum(1 for item in relevant_items if _is_incremental_history_tactical_clean(item))
    comparable_scores = [
        float(item.get("comparison_score"))
        for item in relevant_items
        if item.get("comparison_score") is not None
    ]

    priority_fit_pct = round((priority_fit_count / count) * 100, 1)
    economic_fit_pct = round((economic_fit_count / count) * 100, 1)
    tactical_clean_pct = round((tactical_clean_count / count) * 100, 1)
    average_comparison_score = round(sum(comparable_scores) / len(comparable_scores), 2) if comparable_scores else None
    quality_score = round(priority_fit_pct + economic_fit_pct + tactical_clean_pct, 1)

    return {
        "source": source,
        "label": label,
        "count": count,
        "priority_fit_pct": priority_fit_pct,
        "economic_fit_pct": economic_fit_pct,
        "tactical_clean_pct": tactical_clean_pct,
        "average_comparison_score": average_comparison_score,
        "quality_score": quality_score,
        "has_items": True,
    }


def _build_incremental_future_purchase_source_quality_summary(items: list[Dict]) -> Dict:
    backlog_item = _build_incremental_future_purchase_source_quality_item("backlog_nuevo", items)
    reactivated_item = _build_incremental_future_purchase_source_quality_item("reactivadas", items)

    comparable = [item for item in [backlog_item, reactivated_item] if item.get("has_items")]
    if not comparable:
        dominant_source = "none"
        dominant_label = "Sin calidad comparable"
        headline = "Todavia no hay futuras compras visibles para comparar calidad promedio por fuente."
    elif len(comparable) == 1:
        dominant_source = str(comparable[0].get("source") or "none")
        dominant_label = f"Mejor calidad promedio: {comparable[0].get('label')}"
        headline = f"{comparable[0].get('label')} hoy concentra la mejor calidad promedio del historial visible."
    else:
        sorted_items = sorted(
            comparable,
            key=lambda item: (
                -float(item.get("quality_score") or 0.0),
                -float(item.get("average_comparison_score") or float("-inf")),
                str(item.get("label") or ""),
            ),
        )
        top = sorted_items[0]
        second = sorted_items[1]
        if abs(float(top.get("quality_score") or 0.0) - float(second.get("quality_score") or 0.0)) < 0.1:
            dominant_source = "mixto"
            dominant_label = "Calidad pareja"
            headline = "Backlog nuevo y reactivadas hoy muestran una calidad promedio muy similar."
        else:
            dominant_source = str(top.get("source") or "none")
            dominant_label = f"Mejor calidad promedio: {top.get('label')}"
            headline = f"{top.get('label')} hoy muestra mejor calidad promedio que la fuente alternativa."

    return {
        "backlog_nuevo": backlog_item,
        "reactivadas": reactivated_item,
        "dominant_source": dominant_source,
        "dominant_label": dominant_label,
        "headline": headline,
        "has_quality": bool(comparable),
    }


def _build_incremental_history_priority_filter_options(active_priority_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [{"key": "all", "label": "Todas las prioridades", "count": sum(int(value or 0) for value in counts.values())}]
    for key, label in (
        ("high", "Alta"),
        ("medium", "Recuperable"),
        ("watch", "Observacion"),
        ("low", "Baja"),
    ):
        options.append({"key": key, "label": label, "count": int(counts.get(key, 0))})
    for option in options:
        option["selected"] = (active_priority_filter or "all") == option["key"]
    return options


def _build_incremental_history_deferred_fit_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas las diferidas", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "reactivable", "label": "Diferidas reactivables", "count": int(counts.get("reactivable", 0))},
        {"key": "archivable", "label": "Diferidas archivables", "count": int(counts.get("archivable", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_future_purchase_source_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas las fuentes", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "backlog_nuevo", "label": "Backlog nuevo", "count": int(counts.get("backlog_nuevo", 0))},
        {"key": "reactivadas", "label": "Reactivadas", "count": int(counts.get("reactivadas", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_history_sort_options(active_sort_mode: str) -> list[Dict]:
    options = [
        {"key": "newest", "label": "Mas recientes"},
        {"key": "priority", "label": "Prioridad operativa"},
        {"key": "future_purchase", "label": "Futuras compras"},
    ]
    for option in options:
        option["selected"] = active_sort_mode == option["key"]
    return options


def _build_incremental_future_purchase_history_context(
    item: Dict,
    *,
    reactivated_snapshot_ids: set[int] | None = None,
) -> Dict:
    snapshot_id = item.get("id")
    try:
        normalized_snapshot_id = int(snapshot_id)
    except (TypeError, ValueError):
        normalized_snapshot_id = None

    is_pending = str(item.get("manual_decision_status") or "") == "pending"
    is_recently_reactivated = bool(
        normalized_snapshot_id is not None and normalized_snapshot_id in (reactivated_snapshot_ids or set())
    )
    if is_pending and is_recently_reactivated:
        return {
            "source": "reactivadas",
            "label": "Reactivada",
            "summary": "Sigue vigente tras reactivarse desde diferidas.",
            "is_relevant": True,
        }
    if is_pending:
        return {
            "source": "backlog_nuevo",
            "label": "Backlog nuevo",
            "summary": "Sigue pendiente como idea nueva dentro del backlog actual.",
            "is_relevant": True,
        }
    return {
        "source": "other",
        "label": "",
        "summary": "",
        "is_relevant": False,
    }


def _sort_incremental_history_items(
    items: list[Dict],
    *,
    sort_mode: str,
    preferred_source: str | None = None,
) -> list[Dict]:
    if sort_mode not in {"priority", "future_purchase"}:
        return items
    if sort_mode == "future_purchase":
        normalized_preferred_source = str(preferred_source or "mixto")
        if normalized_preferred_source == "reactivadas":
            source_order = {"reactivadas": 0, "backlog_nuevo": 1, "other": 2}
        elif normalized_preferred_source == "backlog_nuevo":
            source_order = {"backlog_nuevo": 0, "reactivadas": 1, "other": 2}
        else:
            source_order = {"backlog_nuevo": 0, "reactivadas": 0, "other": 1}
        return sorted(
            items,
            key=lambda item: (
                int(source_order.get(str((item.get("future_purchase_context") or {}).get("source") or "other"), 2)),
                0 if item.get("is_backlog_front") else 1,
                _incremental_backlog_priority_order(str((item.get("history_priority") or {}).get("priority") or "low")),
                -(float(item.get("comparison_score")) if item.get("comparison_score") is not None else float("-inf")),
                str(item.get("proposal_label") or ""),
            ),
        )
    return sorted(
        items,
        key=lambda item: (
            0 if item.get("is_backlog_front") else 1,
            _incremental_backlog_priority_order(str((item.get("history_priority") or {}).get("priority") or "low")),
            -(float(item.get("comparison_score")) if item.get("comparison_score") is not None else float("-inf")),
            str(item.get("proposal_label") or ""),
        ),
    )
