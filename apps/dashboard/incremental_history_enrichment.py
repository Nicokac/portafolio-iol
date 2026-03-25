from typing import Dict

from apps.dashboard.incremental_followup import _build_incremental_snapshot_comparison
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_next_action,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
    _incremental_backlog_priority_order,
)


def _build_incremental_tactical_trace(item: Dict | None) -> Dict:
    explanation_items = [str(bullet).strip() for bullet in list((item or {}).get("decision_explanation") or []) if str(bullet).strip()]
    badges = []

    if any("parking" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "parking", "label": "Parking", "tone": "warning"})
    if any("liquidez reciente" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "market_history", "label": "Liquidez reciente", "tone": "info"})
    if any("reemplazada por una alternativa" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "alternative_promoted", "label": "Alternativa promovida", "tone": "primary"})
    if any("repriorizada" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "reprioritized", "label": "Repriorizada", "tone": "secondary"})
    if any("condicionada" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "conditioned", "label": "Condicionada", "tone": "secondary"})

    if any(badge["key"] == "market_history" for badge in badges) and any(
        badge["key"] == "alternative_promoted" for badge in badges
    ):
        headline = "Se promovio una alternativa mas limpia por liquidez reciente."
    elif any(badge["key"] == "parking" for badge in badges) and any(
        badge["key"] == "alternative_promoted" for badge in badges
    ):
        headline = "Se promovio una alternativa mas limpia por parking visible."
    elif any(badge["key"] == "market_history" for badge in badges):
        headline = "La propuesta quedo bajo revision por liquidez reciente."
    elif any(badge["key"] == "parking" for badge in badges):
        headline = "La propuesta quedo bajo revision por parking visible."
    else:
        headline = ""

    compact_reasons = []
    for bullet in explanation_items:
        lowered = bullet.lower()
        if "parking" in lowered or "liquidez reciente" in lowered or "repriorizada" in lowered or "reemplazada por una alternativa" in lowered:
            compact_reasons.append(bullet)
    compact_reasons = compact_reasons[:3]

    return {
        "has_trace": bool(badges or compact_reasons or headline),
        "headline": headline,
        "badges": badges[:4],
        "reasons": compact_reasons,
    }


def _build_incremental_history_baseline_trace(
    baseline_item: Dict | None,
    current_item: Dict | None,
    *,
    tactical_trace: Dict | None = None,
) -> Dict:
    current_item = current_item or {}
    baseline_item = baseline_item or {}
    tactical_trace = tactical_trace or {}

    current_id = current_item.get("id")
    baseline_id = baseline_item.get("id")
    if not baseline_item or (current_id is not None and baseline_id is not None and current_id == baseline_id):
        return {
            "has_trace": False,
            "headline": "",
            "badges": [],
            "metrics": [],
        }

    comparison = _build_incremental_snapshot_comparison(baseline_item, current_item)
    winner = comparison.get("winner")
    badges = []
    metrics = []

    expected_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "expected_return_change"),
        None,
    )
    fragility_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "fragility_change"),
        None,
    )
    scenario_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "scenario_loss_change"),
        None,
    )

    if winner == "current":
        badges.append({"label": "Mejor que baseline", "tone": "success"})
    elif winner == "saved":
        badges.append({"label": "Peor que baseline", "tone": "danger"})
    elif winner == "tie":
        badges.append({"label": "Empata baseline", "tone": "secondary"})

    if expected_metric and expected_metric.get("direction") == "favorable":
        badges.append({"label": "Mejor retorno", "tone": "success"})
        metrics.append("Mejora retorno esperado vs baseline.")
    elif expected_metric and expected_metric.get("direction") == "unfavorable":
        badges.append({"label": "Menor retorno", "tone": "warning"})
        metrics.append("Pierde retorno esperado vs baseline.")

    if fragility_metric and fragility_metric.get("direction") == "favorable":
        badges.append({"label": "Menor fragilidad", "tone": "info"})
        metrics.append("Reduce fragilidad vs baseline.")
    elif fragility_metric and fragility_metric.get("direction") == "unfavorable":
        metrics.append("Aumenta fragilidad vs baseline.")

    if scenario_metric and scenario_metric.get("direction") == "favorable":
        metrics.append("Mejora peor escenario vs baseline.")
    elif scenario_metric and scenario_metric.get("direction") == "unfavorable":
        metrics.append("Debilita peor escenario vs baseline.")

    if tactical_trace.get("has_trace"):
        badges.append({"label": "Mas ejecutable tacticamente", "tone": "primary"})
        metrics.append("La propuesta incorpora gobierno tactico explicito frente a friccion de ejecucion.")

    if winner == "current" and expected_metric and expected_metric.get("direction") == "favorable":
        headline = "Supera al baseline en rentabilidad esperada y balance global."
    elif winner == "current":
        headline = "Supera al baseline en score comparativo."
    elif winner == "saved":
        headline = "Queda por detras del baseline actual."
    elif tactical_trace.get("has_trace"):
        headline = "No mejora claramente al baseline, pero deja una lectura tactica mas ejecutable."
    else:
        headline = ""

    return {
        "has_trace": bool(headline or badges or metrics),
        "headline": headline,
        "badges": badges[:4],
        "metrics": metrics[:4],
    }


def _build_incremental_history_priority(
    baseline_item: Dict | None,
    current_item: Dict | None,
    *,
    tactical_trace: Dict | None = None,
) -> Dict:
    current_item = current_item or {}
    if not baseline_item:
        return {
            "has_priority": False,
            "priority": "",
            "priority_label": "",
            "next_action": "",
        }

    comparison = _build_incremental_snapshot_comparison(baseline_item, current_item)
    comparison_metrics = {metric.get("key"): metric for metric in (comparison or {}).get("metrics", [])}
    candidate = {
        "snapshot": current_item,
        "score_difference": None if comparison is None else comparison.get("score_difference"),
        "beats_baseline": bool(comparison and comparison.get("winner") == "current"),
        "loses_vs_baseline": bool(comparison and comparison.get("winner") == "saved"),
        "ties_baseline": bool(comparison and comparison.get("winner") == "tie"),
        "improves_profitability": str((comparison_metrics.get("expected_return_change") or {}).get("direction") or "neutral") == "favorable",
        "protects_fragility": str((comparison_metrics.get("fragility_change") or {}).get("direction") or "neutral") != "unfavorable",
        "tactical_clean": bool(
            not (tactical_trace or {}).get("has_trace")
            or any(str(badge.get("label") or "").strip() == "Alternativa promovida" for badge in (tactical_trace or {}).get("badges", []))
        ),
    }
    priority = _classify_incremental_backlog_priority(candidate)
    return {
        "has_priority": True,
        "priority": priority,
        "priority_label": _format_incremental_backlog_priority(priority),
        "next_action": _build_incremental_backlog_next_action(priority, candidate),
    }


def _build_incremental_history_priority_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "high": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "high"),
        "medium": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "medium"),
        "watch": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "watch"),
        "low": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "low"),
    }


def _build_incremental_history_deferred_fit(item: Dict) -> Dict:
    if str(item.get("manual_decision_status") or "") != "deferred":
        return {
            "status": "",
            "label": "",
            "summary": "",
            "is_deferred": False,
        }

    priority = str((item.get("history_priority") or {}).get("priority") or "")
    if priority in {"high", "medium"}:
        return {
            "status": "reactivable",
            "label": "Reactivable",
            "summary": "Sigue mostrando fit suficiente para reabrirse como futura compra.",
            "is_deferred": True,
        }
    return {
        "status": "archivable",
        "label": "Archivable",
        "summary": "Hoy ya no conserva suficiente fit economico o tactico para reactivarse primero.",
        "is_deferred": True,
    }


def _build_incremental_history_deferred_fit_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "reactivable": sum(1 for item in items if str((item.get("deferred_fit") or {}).get("status") or "") == "reactivable"),
        "archivable": sum(1 for item in items if str((item.get("deferred_fit") or {}).get("status") or "") == "archivable"),
    }


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
