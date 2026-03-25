from typing import Dict

from apps.core.models import IncrementalProposalSnapshot, SensitiveActionAudit
from apps.dashboard.incremental_history import _format_incremental_manual_decision_status


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
            "summary": "No hay backlog nuevo priorizable por delante y las reactivaciones siguen siendo la mejor fuente de revision.",
        }
    if acceptance_rate >= 50.0 and accepted_count >= max(backlog_high, 1):
        return {
            "preferred_source": "reactivadas",
            "label": "Priorizar reactivadas",
            "headline": "Las reactivaciones recientes estan cerrando mejor que el backlog nuevo.",
            "summary": "La tasa de aceptacion post-reactivacion ya justifica revisar primero propuestas rescatadas.",
        }
    if backlog_high > 0 and (acceptance_rate < 25.0 or accepted_count == 0):
        return {
            "preferred_source": "backlog_nuevo",
            "label": "Priorizar backlog nuevo",
            "headline": "El backlog nuevo hoy parece mas prometedor que reactivar diferidas.",
            "summary": (
                f"Hay {backlog_high} propuesta(s) de alta prioridad"
                + (f", con {backlog_top_label} al frente." if backlog_top_label else ".")
            ),
        }
    return {
        "preferred_source": "mixto",
        "label": "Priorizar mixto",
        "headline": "Conviene combinar backlog nuevo y reactivadas segun el caso.",
        "summary": (
            f"Las reactivaciones muestran {accepted_count} cierre(s) positivo(s) y {active_count} siguen vigentes; "
            f"el backlog nuevo aporta {backlog_high} alta(s) y {backlog_medium} recuperable(s)."
        ),
    }
