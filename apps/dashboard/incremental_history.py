from __future__ import annotations

from typing import Dict

from apps.dashboard.incremental_followup import _format_incremental_followup_status


def _normalize_incremental_history_priority_filter(priority_filter: str | None) -> str | None:
    normalized = str(priority_filter or "").strip().lower()
    return normalized if normalized in {"high", "medium", "watch", "low"} else None


def _normalize_incremental_history_deferred_fit_filter(deferred_fit_filter: str | None) -> str | None:
    normalized = str(deferred_fit_filter or "").strip().lower()
    return normalized if normalized in {"reactivable", "archivable"} else None


def _normalize_incremental_future_purchase_source_filter(source_filter: str | None) -> str | None:
    normalized = str(source_filter or "").strip().lower()
    return normalized if normalized in {"backlog_nuevo", "reactivadas"} else None


def _normalize_incremental_history_sort_mode(sort_mode: str | None) -> str:
    normalized = str(sort_mode or "").strip().lower()
    if normalized in {"priority", "future_purchase"}:
        return normalized
    return "newest"


def _format_incremental_backlog_priority(priority: str) -> str:
    mapping = {
        "high": "Alta",
        "medium": "Recuperable",
        "watch": "Observación",
        "low": "Baja",
    }
    return mapping.get(priority, "Baja")


def _format_incremental_history_priority_filter_label(priority_filter: str | None) -> str:
    if not priority_filter:
        return "Todas las prioridades"
    return _format_incremental_backlog_priority(priority_filter)


def _format_incremental_history_deferred_fit_filter_label(deferred_fit_filter: str | None) -> str:
    if not deferred_fit_filter:
        return "Todas las diferidas"
    if deferred_fit_filter == "reactivable":
        return "Diferidas reactivables"
    return "Diferidas archivables"


def _format_incremental_future_purchase_source_filter_label(source_filter: str | None) -> str:
    if not source_filter:
        return "Todas las fuentes"
    if source_filter == "backlog_nuevo":
        return "Backlog nuevo"
    return "Reactivadas"


def _format_incremental_history_sort_mode_label(sort_mode: str | None) -> str:
    if str(sort_mode or "").strip().lower() == "future_purchase":
        return "Futuras compras"
    if str(sort_mode or "").strip().lower() == "priority":
        return "Prioridad operativa"
    return "Mas recientes"


def _format_incremental_manual_decision_status(status: str) -> str:
    mapping = {
        "accepted": "Aceptada",
        "deferred": "Diferida",
        "rejected": "Rechazada",
        "pending": "Pendiente",
    }
    return mapping.get(status, "Pendiente")


def _build_incremental_manual_decision_headline(item: Dict | None) -> str:
    if item is None:
        return "Todavia no registraste una decision manual sobre snapshots incrementales guardados."

    decision_label = _format_incremental_manual_decision_status(str(item.get("manual_decision_status") or "pending")).lower()
    note = str(item.get("manual_decision_note") or "").strip()
    base = f"La ultima decision manual registrada es {decision_label} sobre {item.get('proposal_label') or 'la propuesta seleccionada'}."
    if note:
        return f"{base} Nota: {note}"
    return base


def _normalize_incremental_history_decision_filter(decision_status: str | None) -> str | None:
    normalized = str(decision_status or "").strip().lower()
    if normalized in {"pending", "accepted", "deferred", "rejected"}:
        return normalized
    return None


def _format_incremental_history_decision_filter_label(decision_status: str | None) -> str:
    if decision_status is None:
        return "Todos"
    return _format_incremental_manual_decision_status(decision_status)


def _build_incremental_history_available_filters(active_filter: str | None, counts: Dict) -> list[Dict]:
    options = [None, "pending", "accepted", "deferred", "rejected"]
    items = []
    for option in options:
        key = option or "all"
        items.append(
            {
                "key": key,
                "label": _format_incremental_history_decision_filter_label(option),
                "count": int(counts.get("total", 0) if option is None else counts.get(option, 0)),
                "selected": (active_filter or "all") == key,
            }
        )
    return items


def _build_incremental_history_headline(
    decision_status: str | None,
    counts: Dict,
    visible_count: int,
    *,
    priority_filter: str | None = None,
    deferred_fit_filter: str | None = None,
    future_purchase_source_filter: str | None = None,
    sort_mode: str | None = None,
) -> str:
    total = int(counts.get("total", 0))
    if total == 0:
        return "Todavia no guardaste propuestas incrementales para seguimiento manual."
    if decision_status is None:
        base = f"Se muestran {visible_count} snapshots recientes sobre un total de {total} propuestas guardadas."
    else:
        label = _format_incremental_history_decision_filter_label(decision_status).lower()
        base = f"Se muestran {visible_count} snapshots con decision {label}."

    suffix = []
    if priority_filter:
        suffix.append(f"Prioridad: {_format_incremental_history_priority_filter_label(priority_filter)}")
    if deferred_fit_filter:
        suffix.append(f"Diferidas: {_format_incremental_history_deferred_fit_filter_label(deferred_fit_filter)}")
    if future_purchase_source_filter:
        suffix.append(f"Fuente: {_format_incremental_future_purchase_source_filter_label(future_purchase_source_filter)}")
    if str(sort_mode or "").strip().lower() == "priority":
        suffix.append("Ordenados por prioridad operativa")
    if str(sort_mode or "").strip().lower() == "future_purchase":
        suffix.append("Ordenados para futuras compras")
    if suffix:
        return f"{base} {' · '.join(suffix)}."
    return base


def _build_incremental_pending_backlog_headline(
    baseline_item: Dict | None,
    pending_history: Dict,
    better_count: int,
    worse_count: int,
    tie_count: int,
) -> str:
    pending_count = int(pending_history.get("decision_counts", {}).get("pending", pending_history.get("count", 0)))
    if baseline_item is None and pending_count == 0:
        return "No hay baseline activo ni backlog pendiente para seguimiento operativo."
    if baseline_item is None:
        return "Hay backlog incremental pendiente, pero todavia no existe baseline activo para compararlo."
    if pending_count == 0:
        return "No hay snapshots pendientes en el backlog incremental contra el baseline activo."
    return (
        f"Hay {pending_count} snapshot(s) pendientes: {better_count} superan el baseline, "
        f"{worse_count} quedan por debajo y {tie_count} empatan."
    )


def _build_incremental_pending_backlog_explanation(
    baseline_item: Dict | None,
    pending_history: Dict,
    best_candidate: Dict | None,
    better_count: int,
    worse_count: int,
) -> str:
    pending_count = int(pending_history.get("decision_counts", {}).get("pending", pending_history.get("count", 0)))
    if baseline_item is None and pending_count == 0:
        return "Todavia no hay baseline incremental activo ni snapshots pendientes para comparar."
    if baseline_item is None:
        return "Conviene fijar un baseline incremental activo antes de priorizar el backlog pendiente."
    if pending_count == 0:
        return (
            f"El baseline activo ({baseline_item.get('proposal_label') or 'sin etiqueta'}) no tiene backlog pendiente "
            "contra el cual compararse."
        )
    if best_candidate and best_candidate.get("beats_baseline"):
        snapshot = best_candidate["snapshot"]
        return (
            f"El backlog pendiente ya contiene al menos una alternativa superior al baseline activo: "
            f"{snapshot.get('proposal_label') or 'snapshot pendiente'}."
        )
    if worse_count == pending_count:
        return (
            f"Todas las propuestas pendientes quedan por debajo del baseline activo "
            f"({baseline_item.get('proposal_label') or 'sin etiqueta'})."
        )
    return (
        f"El backlog pendiente frente al baseline activo ({baseline_item.get('proposal_label') or 'sin etiqueta'}) "
        "muestra resultados mixtos y conviene revisar primero las alternativas con mejor score."
    )


def _classify_incremental_backlog_priority(item: Dict) -> str:
    if item.get("beats_baseline") and item.get("improves_profitability") and item.get("protects_fragility") and item.get("tactical_clean"):
        return "high"
    if item.get("beats_baseline"):
        return "medium"
    if item.get("ties_baseline"):
        return "watch"
    return "low"


def _incremental_backlog_priority_order(priority: str) -> int:
    mapping = {
        "high": 0,
        "medium": 1,
        "watch": 2,
        "low": 3,
    }
    return mapping.get(priority, 4)


def _build_incremental_backlog_next_action(priority: str, item: Dict) -> str:
    proposal_label = item.get("snapshot", {}).get("proposal_label") or "este snapshot"
    if item.get("snapshot", {}).get("is_backlog_front"):
        return f"{proposal_label} ya esta marcado al frente del backlog para revision prioritaria."
    if priority == "high":
        return f"Revisar primero {proposal_label}: mejora baseline, cuida fragilidad y mantiene buena ejecutabilidad tactica."
    if priority == "medium":
        return f"Revisar {proposal_label} como candidata recuperable: mejora baseline, pero todavia no es la opcion mas limpia."
    if priority == "watch":
        return f"Mantener {proposal_label} en observacion; hoy empata con el baseline o mejora parcialmente."
    return f"Dejar {proposal_label} al final del backlog operativo mientras no mejore su comparacion."


def _build_incremental_backlog_prioritization_headline(backlog_payload: Dict, counts: Dict, top_item: Dict | None) -> str:
    if not backlog_payload.get("has_baseline") and not backlog_payload.get("has_pending_backlog"):
        return "Todavia no hay backlog pendiente priorizable ni baseline activo."
    if not backlog_payload.get("has_baseline"):
        return "Hay backlog pendiente, pero falta baseline activo para priorizarlo con criterio comparativo."
    if not backlog_payload.get("has_pending_backlog"):
        return "No hay snapshots pendientes para priorizar contra el baseline activo."
    if top_item is None:
        return "No fue posible priorizar el backlog pendiente contra el baseline activo."
    if top_item.get("snapshot", {}).get("is_backlog_front"):
        return (
            f"Backlog priorizado con frente manual: {top_item.get('snapshot', {}).get('proposal_label') or 'snapshot al frente'} "
            "queda primero para revision operativa."
        )
    return (
        f"Backlog priorizado: {counts.get('high', 0)} alta, {counts.get('medium', 0)} media y "
        f"{counts.get('low', 0)} baja. Primero revisar {top_item.get('snapshot', {}).get('proposal_label') or 'el snapshot prioritario'}."
    )


def _build_incremental_backlog_prioritization_explanation(backlog_payload: Dict, counts: Dict, top_item: Dict | None) -> str:
    if not backlog_payload.get("has_baseline") and not backlog_payload.get("has_pending_backlog"):
        return "Todavia no hay insumos para una priorizacion operativa del backlog incremental."
    if not backlog_payload.get("has_baseline"):
        return "La priorizacion explicita del backlog requiere primero un baseline incremental activo."
    if not backlog_payload.get("has_pending_backlog"):
        return "No hay backlog pendiente por ordenar en este momento."
    if top_item is not None and top_item.get("snapshot", {}).get("is_backlog_front"):
        return (
            f"{top_item.get('snapshot', {}).get('proposal_label') or 'El snapshot elegido'} fue promovido manualmente "
            "al frente del backlog y queda primero en la lectura operativa."
        )
    if counts.get("high", 0) > 0 and top_item is not None:
        return (
            f"El backlog ya contiene alternativas que superan el baseline activo con mejor retorno esperado, "
            f"sin deterioro material de fragilidad y con buena ejecutabilidad tactica; "
            f"{top_item.get('snapshot', {}).get('proposal_label') or 'la primera opcion'} queda arriba por prioridad."
        )
    if counts.get("medium", 0) > 0:
        return "El backlog incluye alternativas recuperables: mejoran baseline, pero todavia no muestran el balance tactico mas limpio."
    if counts.get("watch", 0) > 0:
        return "El backlog muestra alternativas en observacion: empatan baseline o mejoran solo una parte de la ecuacion riesgo-retorno."
    return "El backlog pendiente actual queda por debajo del baseline activo y puede revisarse al final."


def _build_incremental_backlog_front_summary_headline(status: str, baseline: Dict | None, front_item: Dict | None) -> str:
    if status == "empty":
        return "Todavia no hay baseline activo ni backlog incremental priorizable."
    if status == "no_baseline":
        return (
            f"El backlog incremental ya tiene un frente operativo ({front_item.get('snapshot', {}).get('proposal_label') or 'snapshot'}) "
            "pero falta baseline activo."
        )
    if status == "baseline_only":
        return (
            f"El baseline activo ({baseline.get('proposal_label') or 'sin etiqueta'}) no tiene backlog priorizable por delante."
        )
    if status == "manual_front":
        return (
            f"{front_item.get('snapshot', {}).get('proposal_label') or 'El snapshot al frente'} lidera el backlog por "
            f"marcacion manual frente al baseline {baseline.get('proposal_label') or 'activo'}."
        )
    if status == "candidate_over_baseline":
        return (
            f"{front_item.get('snapshot', {}).get('proposal_label') or 'El frente del backlog'} ya supera al baseline "
            f"{baseline.get('proposal_label') or 'activo'}."
        )
    if status == "watch":
        return (
            f"El frente del backlog ({front_item.get('snapshot', {}).get('proposal_label') or 'snapshot'}) empata con el "
            f"baseline {baseline.get('proposal_label') or 'activo'} y conviene seguirlo de cerca."
        )
    return (
        f"El baseline activo ({baseline.get('proposal_label') or 'sin etiqueta'}) sigue por delante del backlog incremental."
    )


def _build_incremental_backlog_front_summary_items(
    baseline: Dict | None,
    front_item: Dict | None,
    prioritization_payload: Dict,
) -> list[Dict]:
    snapshot = (front_item or {}).get("snapshot", {})
    return [
        {
            "label": "Baseline activo",
            "value": (baseline or {}).get("proposal_label") or "-",
        },
        {
            "label": "Frente del backlog",
            "value": snapshot.get("proposal_label") or "-",
        },
        {
            "label": "Prioridad del frente",
            "value": (front_item or {}).get("priority_label") or "-",
        },
        {
            "label": "Score vs baseline",
            "value": (front_item or {}).get("score_difference") if front_item is not None else "-",
        },
        {
            "label": "Pendientes alta prioridad",
            "value": prioritization_payload.get("counts", {}).get("high", 0),
        },
    ]


def _format_incremental_operational_semaphore(status: str) -> str:
    mapping = {
        "green": "Verde",
        "yellow": "Amarillo",
        "red": "Rojo",
        "gray": "Sin señal",
    }
    return mapping.get(status, "Sin señal")


def _build_incremental_operational_semaphore_headline(status: str, front_summary: Dict, drift_payload: Dict) -> str:
    if status == "red":
        return "Semáforo rojo: la propuesta actual empeora frente al baseline y conviene frenar cambios."
    if status == "yellow":
        return front_summary.get("headline") or "Semáforo amarillo: hay backlog incremental que merece revisión."
    if status == "green":
        return "Semáforo verde: el baseline actual se mantiene sólido y no hay backlog urgente por delante."
    return drift_payload.get("explanation") or "Todavía no hay suficiente señal operativa incremental."


def _build_incremental_operational_semaphore_items(
    drift_payload: Dict,
    front_summary: Dict,
    prioritization: Dict,
) -> list[Dict]:
    return [
        {
            "label": "Drift vs baseline",
            "value": _format_incremental_followup_status(drift_payload.get("summary", {}).get("status", "unavailable")),
        },
        {
            "label": "Frente del backlog",
            "value": ((front_summary.get("front_item") or {}).get("snapshot") or {}).get("proposal_label") or "-",
        },
        {
            "label": "Pendientes alta prioridad",
            "value": prioritization.get("counts", {}).get("high", 0),
        },
    ]


def _build_incremental_decision_executive_headline(
    status: str,
    semaphore: Dict,
    followup: Dict,
    checklist: Dict,
    front_summary: Dict,
) -> str:
    if status == "adopt":
        return "La propuesta incremental actual queda lista para adopción y el baseline no muestra presión operativa."
    if status == "hold":
        return "Conviene sostener el baseline actual y frenar cambios hasta resolver el drift desfavorable."
    if status == "review_backlog":
        return front_summary.get("headline") or "Hay backlog incremental que merece revisión antes de adoptar."
    if status == "review_current":
        return checklist.get("headline") or "La propuesta actual todavía requiere revisión operativa."
    return followup.get("headline") or "Todavía no hay una señal ejecutiva suficiente para decidir."


def _build_incremental_decision_executive_items(
    semaphore: Dict,
    followup: Dict,
    checklist: Dict,
    front_summary: Dict,
) -> list[Dict]:
    return [
        {
            "label": "Semáforo operativo",
            "value": semaphore.get("label") or "Sin señal",
        },
        {
            "label": "Checklist de adopción",
            "value": f"{checklist.get('passed_count', 0)}/{checklist.get('total_count', 0)}",
        },
        {
            "label": "Estado ejecutivo actual",
            "value": followup.get("status") or "-",
        },
        {
            "label": "Frente del backlog",
            "value": ((front_summary.get("front_item") or {}).get("snapshot") or {}).get("proposal_label") or "-",
        },
    ]
