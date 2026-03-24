from __future__ import annotations

from typing import Dict
from urllib.parse import urlencode

from apps.core.services.incremental_proposal_contracts import build_incremental_purchase_plan_summary
from apps.dashboard.decision_engine import _coerce_optional_float


def _build_incremental_snapshot_comparison(saved_item: Dict, current_item: Dict) -> Dict:
    saved_score = _coerce_optional_float(saved_item.get("comparison_score"))
    current_score = _coerce_optional_float(current_item.get("comparison_score"))
    saved_delta = dict(saved_item.get("simulation_delta") or (saved_item.get("simulation") or {}).get("delta") or {})
    current_delta = dict(current_item.get("simulation_delta") or (current_item.get("simulation") or {}).get("delta") or {})

    metrics = []
    for key, label in (
        ("expected_return_change", "Expected return"),
        ("real_expected_return_change", "Real expected return"),
        ("fragility_change", "Fragility"),
        ("scenario_loss_change", "Worst scenario loss"),
        ("risk_concentration_change", "Top risk concentration"),
    ):
        saved_value = _coerce_optional_float(saved_delta.get(key))
        current_value = _coerce_optional_float(current_delta.get(key))
        direction = _classify_incremental_metric_direction(key, saved_value, current_value)
        metrics.append(
            {
                "key": key,
                "label": label,
                "saved_value": saved_value,
                "current_value": current_value,
                "difference": None if saved_value is None or current_value is None else round(current_value - saved_value, 4),
                "direction": direction,
            }
        )

    return {
        "score_saved": saved_score,
        "score_current": current_score,
        "score_difference": None if saved_score is None or current_score is None else round(current_score - saved_score, 4),
        "metrics": metrics,
        "winner": _resolve_incremental_snapshot_winner(saved_score, current_score),
    }


def _build_incremental_baseline_drift_summary(comparison: Dict | None) -> Dict:
    if comparison is None:
        return {
            "status": "unavailable",
            "favorable_count": 0,
            "unfavorable_count": 0,
            "changed_count": 0,
            "material_metrics": [],
        }

    material_metrics = []
    favorable_count = 0
    unfavorable_count = 0
    for metric in comparison.get("metrics", []):
        direction = metric.get("direction") or "neutral"
        if direction == "neutral":
            continue
        enriched_metric = dict(metric)
        enriched_metric["direction"] = direction
        material_metrics.append(enriched_metric)
        if direction == "favorable":
            favorable_count += 1
        elif direction == "unfavorable":
            unfavorable_count += 1

    if favorable_count and not unfavorable_count:
        status = "favorable"
    elif unfavorable_count and not favorable_count:
        status = "unfavorable"
    elif favorable_count or unfavorable_count:
        status = "mixed"
    else:
        status = "stable"

    return {
        "status": status,
        "favorable_count": favorable_count,
        "unfavorable_count": unfavorable_count,
        "changed_count": len(material_metrics),
        "material_metrics": material_metrics,
    }


def _classify_incremental_metric_direction(metric_key: str, saved_value: float | None, current_value: float | None) -> str:
    if saved_value is None or current_value is None:
        return "neutral"
    diff = round(current_value - saved_value, 4)
    if abs(diff) < 0.0001:
        return "neutral"

    higher_is_better = metric_key in {
        "expected_return_change",
        "real_expected_return_change",
        "scenario_loss_change",
    }
    if higher_is_better:
        return "favorable" if diff > 0 else "unfavorable"
    return "favorable" if diff < 0 else "unfavorable"


def _resolve_incremental_snapshot_winner(saved_score: float | None, current_score: float | None) -> str | None:
    if saved_score is None and current_score is None:
        return None
    if saved_score is None:
        return "current"
    if current_score is None:
        return "saved"
    if current_score > saved_score:
        return "current"
    if current_score < saved_score:
        return "saved"
    return "tie"


def _build_incremental_baseline_drift_explanation(
    baseline_item: Dict | None,
    current_item: Dict | None,
    comparison: Dict | None,
    summary: Dict,
) -> str:
    if not baseline_item and not current_item:
        return "Todavia no hay baseline incremental activo ni propuesta preferida actual para medir drift."
    if not baseline_item:
        return "Todavia no hay un baseline incremental activo para medir drift contra la propuesta preferida actual."
    if not current_item:
        return "Todavia no hay una propuesta preferida actual construible para medir drift contra el baseline activo."
    if comparison is None:
        return "No fue posible construir el drift entre el baseline incremental activo y la propuesta preferida actual."

    status = summary.get("status")
    if status == "favorable":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) mejora el baseline activo "
            f"({baseline_item['proposal_label']}) en las metricas incrementales relevantes."
        )
    if status == "unfavorable":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) empeora frente al baseline activo "
            f"({baseline_item['proposal_label']}) y conviene revisarla antes de reemplazar la referencia."
        )
    if status == "mixed":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) se desvia del baseline activo "
            f"({baseline_item['proposal_label']}) con mejoras y deterioros mezclados."
        )
    return (
        f"La propuesta preferida actual ({current_item['proposal_label']}) se mantiene alineada con el baseline activo "
        f"({baseline_item['proposal_label']}) sin drift material en los deltas principales."
    )


def _build_incremental_baseline_drift_alerts(
    baseline_item: Dict | None,
    current_item: Dict | None,
    summary: Dict,
) -> list[Dict]:
    if baseline_item is None or current_item is None:
        return []

    alerts: list[Dict] = []
    status = summary.get("status")
    if status == "unfavorable":
        alerts.append(
            {
                "severity": "critical" if summary.get("unfavorable_count", 0) >= 2 else "warning",
                "title": "La propuesta actual empeora frente al baseline",
                "message": (
                    f"{current_item['proposal_label']} queda por debajo de {baseline_item['proposal_label']} "
                    "en las metricas incrementales relevantes."
                ),
            }
        )
    elif status == "mixed":
        alerts.append(
            {
                "severity": "warning",
                "title": "Hay drift mixto respecto del baseline",
                "message": (
                    f"{current_item['proposal_label']} mejora algunas metricas pero deteriora otras frente a "
                    f"{baseline_item['proposal_label']}."
                ),
            }
        )
    elif status == "stable":
        alerts.append(
            {
                "severity": "info",
                "title": "No hay drift material",
                "message": (
                    f"{current_item['proposal_label']} se mantiene alineada con el baseline activo "
                    f"{baseline_item['proposal_label']}."
                ),
            }
        )

    for metric in summary.get("material_metrics", []):
        if metric.get("direction") != "unfavorable":
            continue
        alerts.append(
            {
                "severity": "warning",
                "title": f"Drift desfavorable en {metric['label']}",
                "message": (
                    f"El delta actual ({metric.get('current_value')}) queda peor que el baseline "
                    f"({metric.get('saved_value')}) en {metric['label']}."
                ),
            }
        )
    return alerts


def _build_incremental_followup_headline(status: str, preferred: Dict | None, baseline: Dict | None) -> str:
    if status == "pending":
        return "Todavia no hay una propuesta incremental preferida para seguimiento."
    if status == "no_baseline":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) ya esta lista para seguimiento, "
            "pero todavia no definiste un baseline activo."
        )
    if status == "review":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) se desvio en forma desfavorable respecto del baseline "
            f"({baseline['proposal_label']}) y conviene revisarla antes de adoptarla."
        )
    if status == "watch":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) muestra drift mixto frente al baseline "
            f"({baseline['proposal_label']}) y requiere seguimiento cercano."
        )
    return (
        f"La propuesta actual ({preferred['proposal_label']}) se mantiene alineada con el baseline "
        f"({baseline['proposal_label']})."
    )


def _build_incremental_followup_summary_items(
    preferred: Dict | None,
    baseline: Dict | None,
    drift_payload: Dict,
) -> list[Dict]:
    summary = drift_payload.get("summary", {})
    preferred_score = _coerce_optional_float((preferred or {}).get("comparison_score"))
    baseline_score = _coerce_optional_float((baseline or {}).get("comparison_score"))
    score_diff = None if preferred_score is None or baseline_score is None else round(preferred_score - baseline_score, 4)
    return [
        {
            "label": "Propuesta actual",
            "value": (preferred or {}).get("proposal_label") or "-",
        },
        {
            "label": "Baseline activo",
            "value": (baseline or {}).get("proposal_label") or "-",
        },
        {
            "label": "Estado de drift",
            "value": _format_incremental_followup_status(summary.get("status", "unavailable")),
        },
        {
            "label": "Score actual - baseline",
            "value": score_diff if score_diff is not None else "-",
        },
        {
            "label": "Metricas favorables",
            "value": summary.get("favorable_count", 0),
        },
        {
            "label": "Metricas desfavorables",
            "value": summary.get("unfavorable_count", 0),
        },
    ]


def _format_incremental_followup_status(status: str) -> str:
    mapping = {
        "favorable": "Drift favorable",
        "unfavorable": "Drift desfavorable",
        "mixed": "Drift mixto",
        "stable": "Sin drift material",
        "unavailable": "Sin comparacion",
    }
    return mapping.get(status, "Sin clasificar")


def _build_incremental_adoption_check_item(*, key: str, label: str, passed: bool, detail: str) -> Dict:
    return {
        "key": key,
        "label": label,
        "passed": bool(passed),
        "detail": str(detail or "-"),
    }


def _format_incremental_purchase_plan_summary(purchase_plan: list[Dict]) -> str:
    summary = build_incremental_purchase_plan_summary(purchase_plan)
    if not summary:
        return "Sin compra resumida disponible."
    return summary


def _summarize_incremental_drift_alerts(alerts: list[Dict]) -> str:
    if not alerts:
        return "Sin alertas activas."
    critical_titles = [alert.get("title") for alert in alerts if alert.get("severity") == "critical"]
    if critical_titles:
        return ", ".join(str(title) for title in critical_titles if title)
    return f"{len(alerts)} alerta(s) de drift no criticas."


def _build_incremental_adoption_checklist_headline(
    status: str,
    executive_payload: Dict,
    preferred: Dict | None,
    baseline: Dict | None,
) -> str:
    if status == "pending":
        return "Todavia no hay una propuesta incremental lista para pasar por checklist de adopcion."
    if status == "ready":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) supera el checklist operativo y puede "
            "pasar a decision manual."
        )
    if baseline is None:
        return (
            f"La propuesta actual ({preferred['proposal_label']}) todavia requiere contexto adicional: "
            "conviene fijar un baseline antes de adoptarla."
        )
    return executive_payload.get("headline") or (
        f"La propuesta actual ({preferred['proposal_label']}) todavia requiere revision antes de adopcion."
    )


def _build_incremental_snapshot_reapply_payload(item: Dict) -> Dict:
    purchase_plan = list(item.get("purchase_plan") or [])
    query_items = [("manual_compare", "1")]
    capital_amount = item.get("capital_amount")
    if capital_amount:
        query_items.append(("plan_a_capital", _stringify_reapply_amount(capital_amount)))

    for index, purchase in enumerate(purchase_plan[:3], start=1):
        query_items.append((f"plan_a_symbol_{index}", str(purchase.get("symbol") or "").strip().upper()))
        query_items.append((f"plan_a_amount_{index}", _stringify_reapply_amount(purchase.get("amount") or 0)))

    execution_quality = item.get("execution_quality") or {}
    execution_order_label = str(execution_quality.get("execution_order_label") or "").strip()
    execution_order_summary = str(execution_quality.get("execution_order_summary") or "").strip()
    if execution_order_label and execution_order_summary:
        query_items.append(("plan_a_execution_order_label", execution_order_label))
        query_items.append(("plan_a_execution_order_summary", execution_order_summary))

    return {
        "reapply_querystring": urlencode(query_items),
        "reapply_truncated": len(purchase_plan) > 3,
    }


def _stringify_reapply_amount(value) -> str:
    amount = float(value or 0)
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}"
