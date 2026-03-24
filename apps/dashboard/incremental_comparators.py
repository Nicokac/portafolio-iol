from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode

from django.urls import reverse

from apps.core.services.incremental_proposal_contracts import normalize_incremental_proposal_payload
from apps.dashboard.decision_engine import _manual_execution_readiness_rank


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


def _candidate_blocks_map(candidate_ranking: Dict) -> Dict[str, Dict]:
    return {
        str(item.get("block") or ""): item
        for item in candidate_ranking.get("by_block", [])
    }


def _resolve_manual_incremental_operational_tiebreak(
    proposals: list[Dict],
    *,
    score_gap_threshold: float = 0.25,
) -> tuple[list[Dict], Dict | None, Dict]:
    ranked = sorted(
        proposals,
        key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
        reverse=True,
    )
    leader = next((item for item in ranked if item.get("comparison_score") is not None), None)
    if leader is None:
        return ranked, None, {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }

    leader_score = float(leader.get("comparison_score") or 0.0)
    contenders = [
        item
        for item in ranked
        if item.get("comparison_score") is not None
        and abs(float(item.get("comparison_score") or 0.0) - leader_score) <= float(score_gap_threshold)
    ]
    if len(contenders) < 2:
        return ranked, leader, {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }

    selected = sorted(
        contenders,
        key=lambda item: (
            _manual_execution_readiness_rank(str((item.get("execution_readiness") or {}).get("status") or "pending")),
            float(item.get("comparison_score") or float("-inf")),
        ),
        reverse=True,
    )[0]
    used_operational_tiebreak = selected.get("proposal_key") != leader.get("proposal_key") and (
        _manual_execution_readiness_rank(str((selected.get("execution_readiness") or {}).get("status") or "pending"))
        > _manual_execution_readiness_rank(str((leader.get("execution_readiness") or {}).get("status") or "pending"))
    )
    if used_operational_tiebreak:
        reordered = [selected] + [item for item in ranked if item.get("proposal_key") != selected.get("proposal_key")]
        headline = "Desempate operativo aplicado"
        summary = (
            f"{selected.get('proposal_label') or selected.get('label') or 'El plan seleccionado'} queda primero porque "
            "su ejecucion real reciente se ve mas limpia dentro de una brecha corta de score."
        )
        return reordered, selected, {
            "has_tiebreak": True,
            "used_operational_tiebreak": True,
            "headline": headline,
            "summary": summary,
            "leader_label": leader.get("proposal_label") or leader.get("label") or "",
            "selected_label": selected.get("proposal_label") or selected.get("label") or "",
        }

    return ranked, leader, {
        "has_tiebreak": True,
        "used_operational_tiebreak": False,
        "headline": "Empate corto sin cambio de liderazgo",
        "summary": (
            f"{leader.get('proposal_label') or leader.get('label') or 'El plan lider'} sigue arriba por score y no necesit? desempate operativo adicional."
        ),
        "leader_label": leader.get("proposal_label") or leader.get("label") or "",
        "selected_label": leader.get("proposal_label") or leader.get("label") or "",
    }


def _extract_best_incremental_proposal(payload: Dict) -> Dict | None:
    best_key = payload.get("best_proposal_key")
    if not best_key:
        return None
    for proposal in payload.get("proposals", []):
        if proposal.get("proposal_key") == best_key:
            return proposal
    return None


def _normalize_incremental_proposal_item(item: Dict | None) -> Dict:
    return normalize_incremental_proposal_payload(item)


def _preferred_source_priority_rank(source_key: str, payload: Dict) -> int:
    if source_key == "manual_plan" and payload.get("submitted") and payload.get("proposals"):
        return 4
    if source_key == "candidate_split":
        return 3
    if source_key == "candidate_block":
        return 2
    return 1


def _build_preferred_proposal_context(source_key: str, payload: Dict) -> str | None:
    if source_key == "candidate_block":
        return payload.get("selected_label")
    if source_key == "candidate_split":
        return payload.get("selected_label")
    if source_key == "manual_plan":
        return "Plan manual enviado por el usuario" if payload.get("submitted") else None
    return None


def _build_preferred_incremental_explanation(best: Dict | None, manual_payload: Dict) -> str:
    if best is None:
        return "Todavia no hay una propuesta incremental preferida construible con los comparadores actuales."
    if best["source_key"] == "manual_plan" and manual_payload.get("submitted"):
        return (
            f"La propuesta preferida actual sale del comparador manual: {best['proposal_label']}. "
            "Se prioriza porque refleja una intencion explicita del usuario y ademas lidera el score comparativo disponible."
        )
    context = f" para {best['selected_context']}" if best.get("selected_context") else ""
    return (
        f"La propuesta preferida actual surge de {best['source_label']}{context}: {best['proposal_label']}. "
        "Se selecciona por score comparativo y desempate de prioridad entre comparadores."
    )


def _build_comparable_candidate_blocks(monthly_plan: Dict, candidate_ranking: Dict) -> list[Dict]:
    by_block = _candidate_blocks_map(candidate_ranking)
    comparable_blocks = []
    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if not candidates:
            continue
        comparable_blocks.append(
            {
                "bucket": bucket,
                "label": block.get("label", bucket),
                "suggested_amount": float(block.get("suggested_amount") or 0.0),
                "candidates": [
                    {
                        "asset": candidate.get("asset"),
                        "score": candidate.get("score"),
                        "main_reason": candidate.get("main_reason"),
                    }
                    for candidate in candidates[:3]
                ],
            }
        )
    return comparable_blocks


def _build_purchase_plan_variant(monthly_plan: Dict, candidate_ranking: Dict, *, candidate_index: int) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        block_candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not block_candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue
        idx = candidate_index if len(block_candidates) > candidate_index else 0
        candidate = block_candidates[idx]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _build_top_candidate_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=0)


def _build_runner_up_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=1)


def _build_split_largest_block_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    recommended_blocks = sorted(
        monthly_plan.get("recommended_blocks", []),
        key=lambda item: float(item.get("suggested_amount") or 0.0),
        reverse=True,
    )
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    split_bucket = None
    for block in recommended_blocks:
        bucket = str(block.get("bucket") or "")
        if len(by_block.get(bucket, {}).get("candidates", [])) >= 2:
            split_bucket = bucket
            break

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue

        if bucket == split_bucket:
            first = candidates[0]
            second = candidates[1]
            first_amount = round(amount / 2.0, 2)
            second_amount = round(amount - first_amount, 2)
            for candidate, candidate_amount in ((first, first_amount), (second, second_amount)):
                symbol = candidate.get("asset")
                purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + candidate_amount
                selected_candidates.append(
                    {
                        "symbol": symbol,
                        "block": bucket,
                        "block_label": block.get("label", bucket),
                        "amount": candidate_amount,
                        "candidate_score": candidate.get("score"),
                        "candidate_reason": candidate.get("main_reason"),
                    }
                )
            continue

        candidate = candidates[0]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _score_incremental_simulation(simulation: Dict) -> float:
    delta = simulation.get("delta", {})
    score = 0.0
    score += float(delta.get("expected_return_change") or 0.0)
    score += float(delta.get("real_expected_return_change") or 0.0) * 0.5
    score += float(delta.get("scenario_loss_change") or 0.0) * 0.75
    score -= float(delta.get("fragility_change") or 0.0)
    score -= float(delta.get("risk_concentration_change") or 0.0) * 0.5
    return round(score, 2)


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
