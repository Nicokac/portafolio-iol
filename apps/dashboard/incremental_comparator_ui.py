from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode

from django.urls import reverse


def _build_incremental_comparator_summary(
    *,
    lead_label: str,
    best_label: str | None,
    selected_label: str | None = None,
    best_execution_readiness: Dict | None = None,
    operational_tiebreak: Dict | None = None,
) -> Dict:
    best_execution_readiness = best_execution_readiness or {}
    operational_tiebreak = operational_tiebreak or {}
    has_best = bool(str(best_label or "").strip())
    context = f" para {selected_label}" if selected_label else ""
    headline = f"{lead_label}{context}: {best_label}" if has_best else ""
    return {
        "has_best_label": has_best,
        "headline": headline,
        "best_label": best_label or "",
        "selected_label": selected_label or "",
        "best_execution_readiness": best_execution_readiness,
        "operational_tiebreak": operational_tiebreak,
        "has_execution_summary": bool(best_execution_readiness.get("has_summary")),
        "has_tiebreak": bool(operational_tiebreak.get("has_tiebreak")),
    }


def _ensure_incremental_comparator_display_summary(
    comparator_detail: Dict | None,
    *,
    lead_label: str,
) -> Dict:
    comparator_detail = dict(comparator_detail or {})
    if comparator_detail.get("display_summary"):
        return comparator_detail

    comparator_detail["display_summary"] = _build_incremental_comparator_summary(
        lead_label=lead_label,
        best_label=comparator_detail.get("best_label"),
        selected_label=comparator_detail.get("selected_label"),
        best_execution_readiness=comparator_detail.get("best_execution_readiness"),
        operational_tiebreak=comparator_detail.get("operational_tiebreak"),
    )
    return comparator_detail


def _normalize_incremental_readiness_filter(value) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ready", "review_execution", "monitor"}:
        return normalized
    return "all"


def _format_incremental_readiness_filter_label(value: str) -> str:
    labels = {
        "all": "Todas",
        "ready": "Listo para ejecutar",
        "review_execution": "Validar ejecucion",
        "monitor": "Seguir observando",
    }
    return labels.get(value or "all", "Todas")


def _build_incremental_readiness_filter_options(active_filter: str) -> List[Dict]:
    options = []
    for value in ("all", "ready", "review_execution", "monitor"):
        options.append(
            {
                "value": value,
                "label": _format_incremental_readiness_filter_label(value),
                "is_selected": value == active_filter,
            }
        )
    return options


def _apply_incremental_readiness_filter(proposals: List[Dict], readiness_filter: str) -> List[Dict]:
    normalized_filter = _normalize_incremental_readiness_filter(readiness_filter)
    if normalized_filter == "all":
        return list(proposals)
    return [
        item
        for item in proposals
        if str((item.get("execution_readiness") or {}).get("status") or "pending") == normalized_filter
    ]


def _build_incremental_readiness_filter_metadata(
    *,
    proposals: List[Dict],
    readiness_filter: str,
) -> Dict:
    normalized_filter = _normalize_incremental_readiness_filter(readiness_filter)
    filtered = _apply_incremental_readiness_filter(proposals, normalized_filter)
    return {
        "active_readiness_filter": normalized_filter,
        "active_readiness_filter_label": _format_incremental_readiness_filter_label(normalized_filter),
        "available_readiness_filters": _build_incremental_readiness_filter_options(normalized_filter),
        "filtered_proposals": filtered,
        "visible_count": len(filtered),
        "total_count": len(proposals),
        "has_active_readiness_filter": normalized_filter != "all",
    }


def _query_param_value(query_params, key: str, default=""):
    getter = getattr(query_params, "get", None)
    if callable(getter):
        return getter(key, default)
    if isinstance(query_params, dict):
        return query_params.get(key, default)
    return default


def _build_incremental_comparator_hidden_inputs(query_params, *, exclude_keys: set[str] | None = None) -> List[Dict]:
    exclude_keys = set(exclude_keys or set())
    preserved_keys = [
        "comparison_readiness_filter",
        "candidate_compare",
        "candidate_compare_block",
        "candidate_compare_readiness_filter",
        "candidate_split_compare",
        "candidate_split_block",
        "candidate_split_readiness_filter",
        "manual_compare",
        "manual_compare_readiness_filter",
    ]
    for plan_key in ("plan_a", "plan_b"):
        preserved_keys.extend(
            [
                f"{plan_key}_capital",
                f"{plan_key}_execution_order_label",
                f"{plan_key}_execution_order_summary",
            ]
        )
        for index in range(1, 4):
            preserved_keys.extend(
                [
                    f"{plan_key}_symbol_{index}",
                    f"{plan_key}_amount_{index}",
                ]
            )

    hidden_inputs = []
    for key in preserved_keys:
        if key in exclude_keys:
            continue
        value = _query_param_value(query_params, key, "")
        if value in ("", None):
            continue
        hidden_inputs.append({"name": key, "value": value})
    return hidden_inputs


def _build_planeacion_aportes_reset_url(query_params, *, exclude_keys: set[str] | None = None) -> str:
    exclude_keys = set(exclude_keys or set())
    hidden_inputs = _build_incremental_comparator_hidden_inputs(query_params, exclude_keys=exclude_keys)
    base_url = reverse("dashboard:planeacion")
    if hidden_inputs:
        return f"{base_url}?{urlencode([(item['name'], item['value']) for item in hidden_inputs])}#planeacion-aportes"
    return f"{base_url}#planeacion-aportes"


def _build_incremental_comparator_activity_summary(
    *,
    auto: Dict,
    candidate: Dict,
    split: Dict,
    manual: Dict,
) -> Dict:
    items = []

    if auto.get("has_active_readiness_filter"):
        items.append(
            {
                "key": "general",
                "label": "Comparador general",
                "summary": f"Filtro activo: {auto.get('active_readiness_filter_label') or 'Todas'}.",
            }
        )

    if candidate.get("submitted") or candidate.get("has_active_readiness_filter") or candidate.get("selected_block"):
        candidate_label = candidate.get("selected_label") or candidate.get("selected_block") or "bloque actual"
        summary = f"Bloque: {candidate_label}."
        if candidate.get("has_active_readiness_filter"):
            summary = f"{summary} Filtro: {candidate.get('active_readiness_filter_label') or 'Todas'}."
        items.append(
            {
                "key": "candidate",
                "label": "Comparador por candidato",
                "summary": summary,
            }
        )

    if split.get("submitted") or split.get("has_active_readiness_filter") or split.get("selected_block"):
        split_label = split.get("selected_label") or split.get("selected_block") or "bloque actual"
        summary = f"Bloque: {split_label}."
        if split.get("has_active_readiness_filter"):
            summary = f"{summary} Filtro: {split.get('active_readiness_filter_label') or 'Todas'}."
        items.append(
            {
                "key": "split",
                "label": "Comparador por split",
                "summary": summary,
            }
        )

    if manual.get("submitted") or manual.get("has_active_readiness_filter"):
        summary = "Planes manuales cargados."
        if manual.get("has_active_readiness_filter"):
            summary = f"{summary} Filtro: {manual.get('active_readiness_filter_label') or 'Todas'}."
        items.append(
            {
                "key": "manual",
                "label": "Comparador manual",
                "summary": summary,
            }
        )

    if not items:
        headline = "Sin comparadores activos."
    elif len(items) == 1:
        headline = "1 comparador activo."
    else:
        headline = f"{len(items)} comparadores activos."

    return {
        "has_active_context": bool(items),
        "active_count": len(items),
        "headline": headline,
        "items": items,
    }


def _coerce_manual_amount(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_manual_incremental_comparison_form_state(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    submitted = str(_query_param_value(query_params, "manual_compare", "")).strip() == "1"
    plans = []
    normalized_plans = []

    for plan_key, label in (("plan_a", "Plan manual A"), ("plan_b", "Plan manual B")):
        capital_raw = str(_query_param_value(query_params, f"{plan_key}_capital", "")).strip()
        execution_order_label = str(
            _query_param_value(query_params, f"{plan_key}_execution_order_label", "")
        ).strip()
        execution_order_summary = str(
            _query_param_value(query_params, f"{plan_key}_execution_order_summary", "")
        ).strip()
        rows = []
        for index in range(1, 4):
            rows.append(
                {
                    "symbol": str(_query_param_value(query_params, f"{plan_key}_symbol_{index}", "")).strip().upper(),
                    "amount_raw": str(_query_param_value(query_params, f"{plan_key}_amount_{index}", "")).strip(),
                }
            )

        warnings = []
        purchase_plan = []
        total_amount = 0.0
        touched_rows = 0
        for row in rows:
            symbol = row["symbol"]
            amount = _coerce_manual_amount(row["amount_raw"])
            if symbol or row["amount_raw"]:
                touched_rows += 1
            if not symbol and not row["amount_raw"]:
                continue
            if not symbol:
                warnings.append("missing_symbol")
                continue
            if amount <= 0:
                warnings.append(f"invalid_amount:{symbol}")
                continue
            amount = round(amount, 2)
            purchase_plan.append({"symbol": symbol, "amount": amount})
            total_amount += amount

        capital_amount = _coerce_manual_amount(capital_raw)
        if capital_amount <= 0:
            capital_amount = total_amount if total_amount > 0 else float(default_capital_amount)
        capital_amount = round(capital_amount, 2)

        plan_state = {
            "plan_key": plan_key,
            "label": label,
            "capital_raw": capital_raw or str(int(default_capital_amount)),
            "rows": rows,
            "warnings": warnings,
            "has_input": touched_rows > 0 or bool(capital_raw),
            "execution_order_label": execution_order_label,
            "execution_order_summary": execution_order_summary,
            "has_execution_order_guidance": bool(execution_order_label and execution_order_summary),
        }
        plans.append(plan_state)

        if purchase_plan:
            normalized_plans.append(
                {
                    "proposal_key": plan_key,
                    "label": label,
                    "capital_amount": capital_amount,
                    "purchase_plan": purchase_plan,
                    "warnings": warnings,
                    "execution_order_label": execution_order_label,
                    "execution_order_summary": execution_order_summary,
                }
            )

    return {
        "submitted": submitted,
        "plans": plans,
        "normalized_plans": normalized_plans,
    }
