from __future__ import annotations

from typing import Dict

from apps.core.services.incremental_proposal_contracts import normalize_incremental_proposal_payload
from apps.dashboard.decision_engine import _manual_execution_readiness_rank
from apps.dashboard.incremental_comparator_ui import (
    _coerce_manual_amount,
    _build_incremental_comparator_activity_summary,
    _build_incremental_comparator_hidden_inputs,
    _build_incremental_comparator_summary,
    _build_incremental_readiness_filter_metadata,
    _build_incremental_readiness_filter_options,
    _build_manual_incremental_comparison_form_state,
    _build_planeacion_aportes_reset_url,
    _ensure_incremental_comparator_display_summary,
    _format_incremental_readiness_filter_label,
    _normalize_incremental_readiness_filter,
    _query_param_value,
)


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
