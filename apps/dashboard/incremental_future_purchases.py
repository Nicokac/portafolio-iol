from typing import Dict, List

from apps.core.models import IncrementalProposalSnapshot, SensitiveActionAudit
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.dashboard.incremental_followup import _build_incremental_snapshot_comparison
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_next_action,
    _build_incremental_manual_decision_headline,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
    _format_incremental_manual_decision_status,
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
        headline = "Todavía no hay futuras compras visibles para resumir por fuente."
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
    if source == "backlog_nuevo":
        label = "Backlog nuevo"
    else:
        label = "Reactivadas"

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
        headline = "Todavía no hay futuras compras visibles para comparar calidad promedio por fuente."
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
        ("watch", "Observación"),
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
        shortlist_item["focus_label"] = "L?der econ?mico"
        shortlist_item["focus_summary"] = "Mejora retorno esperado sin deterioro material de fragilidad."
    else:
        shortlist_item["focus_label"] = "L?der t?ctico"
        shortlist_item["focus_summary"] = "Conserva la ejecutabilidad m?s limpia para reconsiderar una compra."
    return shortlist_item


def _build_incremental_backlog_conviction(item: Dict, *, economic_edge: bool, tactical_edge: bool) -> Dict:
    priority = str(item.get("priority") or "low")
    if priority == "high" and economic_edge and tactical_edge:
        return {
            "level": "high",
            "label": "Convicci?n alta",
            "summary": "Mejora la ecuaci?n econ?mica y conserva una ejecutabilidad t?ctica limpia.",
        }
    if priority in {"high", "medium"} and (economic_edge or tactical_edge):
        return {
            "level": "medium",
            "label": "Convicci?n media",
            "summary": "Tiene m?rito para reabrir la compra, pero no domina ambos frentes al mismo tiempo.",
        }
    return {
        "level": "low",
        "label": "Convicci?n baja",
        "summary": "Conviene mantenerla en observaci?n hasta que mejore retorno, fragilidad o ejecutabilidad.",
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
        headline = "Todavía hay propuestas vigentes para futuras compras dentro del backlog."
    elif reviewed_count > 0:
        headline = "El backlog vigente ya fue revisado manualmente y hoy no quedan propuestas pendientes."
    else:
        headline = "Todavía no hay decisiones manuales suficientes para leer cobertura operativa del backlog."
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


def get_incremental_reactivation_summary(*, user, limit: int = 3) -> Dict:
    """Resume reactivaciones recientes de snapshots diferidos dentro del backlog incremental."""

    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return {
            "items": [],
            "count": 0,
            "active_count": 0,
            "front_count": 0,
            "acceptance_rate": 0.0,
            "redeferral_rate": 0.0,
            "rejection_rate": 0.0,
            "effectiveness_label": "Sin datos",
            "has_reactivations": False,
            "headline": "Todavia no hay reactivaciones recientes para revisar.",
        }

    audits = list(
        SensitiveActionAudit.objects.filter(
            user=user,
            action="reactivate_incremental_deferred_snapshot",
            status="success",
        ).order_by("-created_at", "-id")[: max(int(limit), 0)]
    )
    snapshot_ids = []
    for audit in audits:
        raw_snapshot_id = (audit.details or {}).get("snapshot_id")
        try:
            snapshot_ids.append(int(raw_snapshot_id))
        except (TypeError, ValueError):
            continue

    snapshots = {
        snapshot.id: snapshot
        for snapshot in IncrementalProposalSnapshot.objects.filter(user=user, id__in=snapshot_ids)
    }
    items = []
    active_count = 0
    front_count = 0
    accepted_count = 0
    deferred_count = 0
    rejected_count = 0
    for audit in audits:
        raw_snapshot_id = (audit.details or {}).get("snapshot_id")
        try:
            snapshot_id = int(raw_snapshot_id)
        except (TypeError, ValueError):
            snapshot_id = None
        snapshot = snapshots.get(snapshot_id)
        current_status = str(getattr(snapshot, "manual_decision_status", "") or "")
        is_backlog_front = bool(getattr(snapshot, "is_backlog_front", False))
        if current_status == "pending":
            active_count += 1
        if current_status == "pending" and is_backlog_front:
            front_count += 1
        if current_status == "accepted":
            accepted_count += 1
        elif current_status == "deferred":
            deferred_count += 1
        elif current_status == "rejected":
            rejected_count += 1
        items.append(
            {
                "snapshot_id": snapshot_id,
                "proposal_label": str((audit.details or {}).get("proposal_label") or getattr(snapshot, "proposal_label", "") or "-"),
                "reactivated_at": audit.created_at,
                "user_label": audit.user.username if audit.user else "system",
                "current_status": current_status or "missing",
                "current_status_label": _format_incremental_manual_decision_status(current_status) if current_status else "Sin snapshot",
                "is_backlog_front": is_backlog_front,
                "is_active": current_status == "pending",
                "is_accepted": current_status == "accepted",
                "is_deferred_again": current_status == "deferred",
                "is_rejected": current_status == "rejected",
                "current_summary": (
                    "Sigue al frente del backlog incremental."
                    if current_status == "pending" and is_backlog_front
                    else "Sigue vigente como candidata pendiente."
                    if current_status == "pending"
                    else "Termino aceptada despues de reactivarse."
                    if current_status == "accepted"
                    else "Volvio a diferirse despues de reactivarse."
                    if current_status == "deferred"
                    else "Se descarto despues de reactivarse."
                    if current_status == "rejected"
                    else "Ya no sigue pendiente en el backlog actual."
                ),
            }
        )

    if items:
        headline = (
            f"Se registraron {len(items)} reactivaciones recientes; {active_count} siguen vigentes, {accepted_count} terminaron aceptadas y {front_count} quedaron al frente del backlog."
        )
    else:
        headline = "Todavia no hay reactivaciones recientes para revisar."

    total_count = len(items)
    acceptance_rate = round((accepted_count / total_count) * 100, 1) if total_count else 0.0
    redeferral_rate = round((deferred_count / total_count) * 100, 1) if total_count else 0.0
    rejection_rate = round((rejected_count / total_count) * 100, 1) if total_count else 0.0
    if total_count == 0:
        effectiveness_label = "Sin datos"
    elif acceptance_rate >= 50 and rejection_rate == 0:
        effectiveness_label = "Alta"
    elif acceptance_rate >= 25:
        effectiveness_label = "Media"
    else:
        effectiveness_label = "Baja"

    return {
        "items": items,
        "count": len(items),
        "active_count": active_count,
        "front_count": front_count,
        "accepted_count": accepted_count,
        "deferred_count": deferred_count,
        "rejected_count": rejected_count,
        "acceptance_rate": acceptance_rate,
        "redeferral_rate": redeferral_rate,
        "rejection_rate": rejection_rate,
        "effectiveness_label": effectiveness_label,
        "has_reactivations": bool(items),
        "headline": headline,
    }


def _build_incremental_reactivation_vs_backlog_summary(
    reactivation_summary: Dict,
    backlog_prioritization: Dict,
) -> Dict:
    reactivation_count = int(reactivation_summary.get("count", 0) or 0)
    accepted_count = int(reactivation_summary.get("accepted_count", 0) or 0)
    active_count = int(reactivation_summary.get("active_count", 0) or 0)
    acceptance_rate = float(reactivation_summary.get("acceptance_rate", 0.0) or 0.0)
    backlog_high = int((backlog_prioritization.get("counts") or {}).get("high", 0) or 0)
    backlog_medium = int((backlog_prioritization.get("counts") or {}).get("medium", 0) or 0)
    backlog_top_label = str((((backlog_prioritization.get("top_item") or {}).get("snapshot") or {}).get("proposal_label")) or "")
    has_backlog = bool(backlog_prioritization.get("has_priorities"))

    if reactivation_count == 0 and has_backlog:
        return {
            "preferred_source": "backlog_nuevo",
            "label": "Priorizar backlog nuevo",
            "headline": "Hoy conviene priorizar ideas nuevas del backlog antes que rescatar diferidas.",
            "summary": "No hay evidencia reciente de reactivaciones como para desplazar el backlog pendiente actual.",
        }
    if has_backlog is False and reactivation_count > 0:
        return {
            "preferred_source": "reactivadas",
            "label": "Priorizar reactivadas",
            "headline": "Hoy conviene volver primero sobre propuestas ya reactivadas.",
            "summary": "No hay backlog nuevo priorizable por delante y las reactivaciones siguen siendo la mejor fuente de revisión.",
        }
    if acceptance_rate >= 50.0 and accepted_count >= max(backlog_high, 1):
        return {
            "preferred_source": "reactivadas",
            "label": "Priorizar reactivadas",
            "headline": "Las reactivaciones recientes están cerrando mejor que el backlog nuevo.",
            "summary": "La tasa de aceptación post-reactivación ya justifica revisar primero propuestas rescatadas.",
        }
    if backlog_high > 0 and (acceptance_rate < 25.0 or accepted_count == 0):
        return {
            "preferred_source": "backlog_nuevo",
            "label": "Priorizar backlog nuevo",
            "headline": "El backlog nuevo hoy parece más prometedor que reactivar diferidas.",
            "summary": (
                f"Hay {backlog_high} propuesta(s) de alta prioridad"
                + (f", con {backlog_top_label} al frente." if backlog_top_label else ".")
            ),
        }
    return {
        "preferred_source": "mixto",
        "label": "Priorizar mixto",
        "headline": "Conviene combinar backlog nuevo y reactivadas según el caso.",
        "summary": (
            f"Las reactivaciones muestran {accepted_count} cierre(s) positivo(s) y {active_count} siguen vigentes; "
            f"el backlog nuevo aporta {backlog_high} alta(s) y {backlog_medium} recuperable(s)."
        ),
    }


def _build_incremental_future_purchase_shortlist(
    reactivation_summary: Dict,
    backlog_prioritization: Dict,
    comparison_summary: Dict,
    quality_summary: Dict,
    *,
    limit: int = 3,
) -> Dict:
    backlog_items = []
    for item in list(backlog_prioritization.get("shortlist") or []):
        enriched = dict(item)
        enriched["source"] = "backlog_nuevo"
        enriched["source_label"] = "Backlog nuevo"
        enriched["source_priority"] = 0
        backlog_items.append(enriched)

    reactivated_items = []
    for index, item in enumerate(list(reactivation_summary.get("items") or []), start=1):
        if not item.get("is_active"):
            continue
        reactivated_items.append(
            {
                "rank": index,
                "proposal_label": item.get("proposal_label") or "-",
                "priority_label": item.get("current_status_label") or "Pendiente",
                "next_action": "Revisar reactivada vigente antes de perder contexto operativo.",
                "selected_context": "Reactivada desde diferidas",
                "expected_return_change": None,
                "fragility_change": None,
                "scenario_loss_change": None,
                "snapshot_id": item.get("snapshot_id"),
                "reapply_querystring": "",
                "reapply_truncated": False,
                "is_backlog_front": bool(item.get("is_backlog_front")),
                "is_tracking_baseline": bool(item.get("is_tracking_baseline")),
                "economic_edge": bool(item.get("is_accepted")),
                "tactical_edge": bool(item.get("is_active")),
                "conviction": {
                    "level": "medium" if item.get("is_backlog_front") else "low",
                    "label": "Conviccion reactivada",
                    "summary": item.get("current_summary") or "",
                },
                "followup": {
                    "status": "review_now" if item.get("is_backlog_front") else "monitor",
                    "label": "Revisar ya" if item.get("is_backlog_front") else "Monitorear",
                    "summary": item.get("current_summary") or "",
                },
                "source": "reactivadas",
                "source_label": "Reactivada",
                "source_priority": 0,
            }
        )

    comparison_preferred_source = str(comparison_summary.get("preferred_source") or "mixto")
    quality_preferred_source = str(quality_summary.get("dominant_source") or "none")
    effective_preferred_source = (
        quality_preferred_source
        if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
        else comparison_preferred_source
    )
    if effective_preferred_source == "reactivadas":
        for item in reactivated_items:
            item["source_priority"] = 0
        for item in backlog_items:
            item["source_priority"] = 1
    elif effective_preferred_source == "backlog_nuevo":
        for item in backlog_items:
            item["source_priority"] = 0
        for item in reactivated_items:
            item["source_priority"] = 1
    else:
        for item in backlog_items:
            item["source_priority"] = 0 if item.get("economic_edge") else 1
        for item in reactivated_items:
            item["source_priority"] = 0 if item.get("is_backlog_front") else 1

    combined_items = sorted(
        backlog_items + reactivated_items,
        key=lambda item: (
            int(item.get("source_priority", 1)),
            0 if item.get("is_backlog_front") else 1,
            0 if str((item.get("followup") or {}).get("status") or "") == "review_now" else 1,
            str(item.get("proposal_label") or ""),
        ),
    )
    shortlist = []
    for index, item in enumerate(combined_items[: max(int(limit), 0)], start=1):
        enriched = dict(item)
        enriched["rank"] = index
        shortlist.append(enriched)

    return {
        "items": shortlist,
        "count": len(shortlist),
        "has_items": bool(shortlist),
        "preferred_source": effective_preferred_source,
        "comparison_preferred_source": comparison_preferred_source,
        "quality_preferred_source": quality_preferred_source,
        "preferred_label": (
            quality_summary.get("dominant_label")
            if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
            else comparison_summary.get("label") or "Priorizar mixto"
        ),
        "headline": (
            quality_summary.get("headline")
            if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
            else comparison_summary.get("headline") or "Conviene revisar una shortlist mixta de futuras compras."
        ),
        "quality_label": quality_summary.get("dominant_label") or "",
        "quality_headline": quality_summary.get("headline") or "",
    }


def _build_incremental_future_purchase_source_guidance(
    quality_summary: Dict,
    shortlist: Dict,
    backlog_prioritization: Dict,
    reactivation_summary: Dict,
) -> Dict:
    source = str((shortlist or {}).get("preferred_source") or (quality_summary or {}).get("dominant_source") or "none")
    if source == "backlog_nuevo":
        top_item = dict((backlog_prioritization or {}).get("top_item") or {})
        snapshot = dict(top_item.get("snapshot") or {})
        proposal_label = str(snapshot.get("proposal_label") or "backlog nuevo prioritario")
        next_action = str(top_item.get("next_action") or f"Revisar primero {proposal_label}.")
        headline = str((quality_summary or {}).get("headline") or "Backlog nuevo hoy concentra la mejor fuente para revisar futuras compras.")
        return {
            "source": "backlog_nuevo",
            "label": "Salir desde backlog nuevo",
            "headline": headline,
            "next_action": next_action,
            "proposal_label": proposal_label,
            "has_guidance": True,
        }
    if source == "reactivadas":
        active_item = next(
            (item for item in list((reactivation_summary or {}).get("items") or []) if item.get("is_active")),
            None,
        ) or {}
        proposal_label = str(active_item.get("proposal_label") or "reactivada vigente")
        next_action = (
            "Revisar reactivada vigente antes de perder contexto operativo."
            if proposal_label == "reactivada vigente"
            else f"Revisar primero {proposal_label} entre las reactivadas vigentes."
        )
        headline = str((quality_summary or {}).get("headline") or "Reactivadas hoy concentra la mejor fuente para revisar futuras compras.")
        return {
            "source": "reactivadas",
            "label": "Salir desde reactivadas",
            "headline": headline,
            "next_action": next_action,
            "proposal_label": proposal_label,
            "has_guidance": True,
        }
    return {
        "source": "mixto",
        "label": "Lectura mixta",
        "headline": "Conviene mantener una lectura mixta entre backlog nuevo y reactivadas.",
        "next_action": "Revisar la shortlist unificada y priorizar el mejor fit visible del momento.",
        "proposal_label": "",
        "has_guidance": True,
    }


def _annotate_incremental_future_purchase_recommended_items(
    shortlist: Dict,
    history: Dict,
    guidance: Dict,
) -> tuple[Dict, Dict]:
    shortlist = dict(shortlist or {})
    history = dict(history or {})
    guidance = dict(guidance or {})

    recommended_label = str(guidance.get("proposal_label") or "").strip()
    recommended_source = str(guidance.get("source") or "").strip().lower()
    has_guidance = bool(guidance.get("has_guidance")) and bool(recommended_label) and recommended_source in {
        "backlog_nuevo",
        "reactivadas",
    }

    def _annotate_item(item: Dict, source_key: str) -> Dict:
        enriched = dict(item or {})
        is_recommended = has_guidance and str(enriched.get("proposal_label") or "").strip() == recommended_label and source_key == recommended_source
        enriched["is_future_purchase_recommended"] = is_recommended
        enriched["future_purchase_recommendation_label"] = "Recomendada ahora" if is_recommended else ""
        enriched["future_purchase_recommendation_summary"] = (
            str(guidance.get("next_action") or "").strip() if is_recommended else ""
        )
        enriched["future_purchase_recommendation_actions"] = {
            "can_reapply": bool(is_recommended and str(enriched.get("reapply_querystring") or "").strip()),
            "can_promote_front": bool(
                is_recommended
                and enriched.get("snapshot_id") is not None
                and not bool(enriched.get("is_backlog_front"))
            ),
            "can_promote_baseline": bool(
                is_recommended
                and enriched.get("snapshot_id") is not None
                and not bool(enriched.get("is_tracking_baseline"))
            ),
        }
        return enriched

    shortlist["items"] = [
        _annotate_item(item, str(item.get("source") or "").strip().lower())
        for item in list(shortlist.get("items") or [])
    ]
    history["items"] = [
        _annotate_item(item, str(((item.get("future_purchase_context") or {}).get("source") or "")).strip().lower())
        for item in list(history.get("items") or [])
    ]
    shortlist["recommended_label"] = recommended_label if has_guidance else ""
    shortlist["has_recommended_item"] = any(item.get("is_future_purchase_recommended") for item in shortlist["items"])
    history["has_future_purchase_recommended_item"] = any(
        item.get("is_future_purchase_recommended") for item in history["items"]
    )
    return shortlist, history


def _build_incremental_future_purchase_workflow_summary(
    shortlist: Dict,
    guidance: Dict,
) -> Dict:
    shortlist = dict(shortlist or {})
    guidance = dict(guidance or {})
    recommended_item = next(
        (item for item in list(shortlist.get("items") or []) if item.get("is_future_purchase_recommended")),
        None,
    ) or {}
    actions = dict(recommended_item.get("future_purchase_recommendation_actions") or {})
    proposal_label = str(recommended_item.get("proposal_label") or guidance.get("proposal_label") or "").strip()

    if not proposal_label:
        return {
            "status": "unavailable",
            "label": "Sin propuesta recomendada",
            "headline": "Todavia no hay una propuesta concreta marcada para el siguiente paso operativo.",
            "next_step": "",
            "has_summary": False,
        }

    if actions.get("can_promote_baseline"):
        return {
            "status": "ready_to_promote",
            "label": "Lista para promover",
            "headline": f"{proposal_label} ya tiene fit suficiente para evaluarla como nuevo baseline incremental.",
            "next_step": f"Promover a baseline {proposal_label} si queres convertirla en referencia operativa principal.",
            "has_summary": True,
        }
    if actions.get("can_promote_front") or actions.get("can_reapply"):
        return {
            "status": "ready_to_review",
            "label": "Lista para revisar",
            "headline": f"{proposal_label} ya esta en condiciones de revisarse como siguiente futura compra.",
            "next_step": str(guidance.get("next_action") or f"Revisar primero {proposal_label}."),
            "has_summary": True,
        }
    return {
        "status": "monitor",
        "label": "Lista para monitorear",
        "headline": f"{proposal_label} sigue siendo la referencia principal, pero por ahora conviene mantener seguimiento.",
        "next_step": str(guidance.get("next_action") or f"Monitorear {proposal_label} antes de mover el proximo aporte."),
        "has_summary": True,
    }


