from typing import Dict

from apps.dashboard.incremental_followup import _build_incremental_snapshot_comparison
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_next_action,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
)
from apps.dashboard.incremental_history_sources import (
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_source_counts,
    _build_incremental_future_purchase_source_filter_options,
    _build_incremental_future_purchase_source_quality_item,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_history_deferred_fit_filter_options,
    _build_incremental_history_priority_filter_options,
    _build_incremental_history_sort_options,
    _is_incremental_history_tactical_clean,
    _sort_incremental_history_items,
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
        "tactical_clean": _is_incremental_history_tactical_clean(
            {"tactical_trace": tactical_trace or {}}
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
