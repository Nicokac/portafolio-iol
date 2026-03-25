from typing import Dict


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
