from typing import Dict

from apps.dashboard.incremental_followup import (
    _build_incremental_adoption_check_item,
    _build_incremental_adoption_checklist_headline,
    _build_incremental_followup_headline,
    _build_incremental_followup_summary_items,
    _format_incremental_followup_status,
    _format_incremental_purchase_plan_summary,
    _summarize_incremental_drift_alerts,
)
from apps.dashboard.incremental_history import (
    _build_incremental_decision_executive_headline,
    _build_incremental_decision_executive_items,
)


def build_incremental_followup_executive_summary(
    *,
    preferred_payload: Dict,
    baseline_payload: Dict,
    drift_payload: Dict,
) -> Dict:
    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")

    if preferred is None:
        status = "pending"
    elif baseline is None:
        status = "no_baseline"
    elif drift_status == "unfavorable":
        status = "review"
    elif drift_status == "mixed":
        status = "watch"
    elif drift_status in {"favorable", "stable"}:
        status = "aligned"
    else:
        status = "watch"

    headline = _build_incremental_followup_headline(status, preferred, baseline)
    summary_items = _build_incremental_followup_summary_items(preferred, baseline, drift_payload)
    return {
        "status": status,
        "headline": headline,
        "summary_items": summary_items,
        "preferred": preferred,
        "baseline": baseline,
        "drift": drift_payload,
        "has_preferred": preferred is not None,
        "has_baseline": baseline is not None,
        "has_summary": bool(preferred or baseline),
    }


def build_incremental_adoption_checklist(
    *,
    preferred_payload: Dict,
    baseline_payload: Dict,
    drift_payload: Dict,
    executive_payload: Dict,
) -> Dict:
    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    drift_alerts = list(drift_payload.get("alerts") or [])

    items = [
        _build_incremental_adoption_check_item(
            key="preferred_available",
            label="Existe propuesta incremental preferida",
            passed=preferred is not None,
            detail=preferred.get("proposal_label") if preferred else "Todavia no hay propuesta incremental construible.",
        ),
        _build_incremental_adoption_check_item(
            key="purchase_plan_available",
            label="La propuesta tiene compra resumida",
            passed=bool((preferred or {}).get("purchase_plan")),
            detail=_format_incremental_purchase_plan_summary((preferred or {}).get("purchase_plan") or []),
        ),
        _build_incremental_adoption_check_item(
            key="baseline_defined",
            label="Existe baseline incremental activo",
            passed=baseline is not None,
            detail=baseline.get("proposal_label") if baseline else "Conviene fijar una referencia antes de adoptar.",
        ),
        _build_incremental_adoption_check_item(
            key="drift_not_unfavorable",
            label="El drift no es desfavorable frente al baseline",
            passed=drift_status != "unfavorable",
            detail=(
                _summarize_incremental_drift_alerts(drift_alerts)
                if drift_alerts
                else _format_incremental_followup_status(drift_status)
            ),
        ),
        _build_incremental_adoption_check_item(
            key="critical_drift_alerts",
            label="No hay alertas criticas de drift",
            passed=not any(str(alert.get("severity") or "") == "critical" for alert in drift_alerts),
            detail=_summarize_incremental_drift_alerts(drift_alerts),
        ),
    ]

    passed_count = sum(1 for item in items if item["passed"])
    adoption_ready = all(item["passed"] for item in items[:2]) and items[3]["passed"] and items[4]["passed"]
    status = "ready" if adoption_ready else "review"
    if preferred is None:
        status = "pending"

    return {
        "status": status,
        "adoption_ready": adoption_ready,
        "items": items,
        "passed_count": passed_count,
        "total_count": len(items),
        "headline": _build_incremental_adoption_checklist_headline(status, executive_payload, preferred, baseline),
    }


def build_incremental_decision_executive_summary(
    *,
    semaphore: Dict,
    followup: Dict,
    checklist: Dict,
    front_summary: Dict,
) -> Dict:
    semaphore_status = semaphore.get("status", "gray")
    checklist_status = checklist.get("status", "pending")
    if checklist_status == "ready" and semaphore_status == "green":
        status = "adopt"
    elif semaphore_status == "red":
        status = "hold"
    elif semaphore_status == "yellow":
        status = "review_backlog"
    elif checklist_status == "review":
        status = "review_current"
    else:
        status = "pending"

    return {
        "status": status,
        "headline": _build_incremental_decision_executive_headline(status, semaphore, followup, checklist, front_summary),
        "items": _build_incremental_decision_executive_items(semaphore, followup, checklist, front_summary),
        "has_summary": bool(
            semaphore.get("has_signal")
            or followup.get("has_summary")
            or checklist.get("total_count")
            or front_summary.get("has_summary")
        ),
    }
