from __future__ import annotations

from typing import Dict
import unicodedata

from apps.parametros.models import ParametroActivo
from apps.core.services.incremental_proposal_contracts import build_incremental_purchase_plan_summary
from apps.dashboard.decision_engine_utils import _coerce_optional_float


def _normalize_decision_block_label(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_only.replace("/", " ").split())


def _has_block_overlap(target_block: str | None, candidate_blocks: list[Dict] | list[str] | None) -> bool:
    target = _normalize_decision_block_label(target_block)
    if not target:
        return False
    for item in candidate_blocks or []:
        if isinstance(item, dict):
            candidate = _normalize_decision_block_label(item.get("label"))
        else:
            candidate = _normalize_decision_block_label(item)
        if candidate and (candidate == target or candidate in target or target in candidate):
            return True
    return False


def _is_parking_overlap_with_recommendation(recommendation_block: str | None, parking_blocks: list[Dict] | None) -> bool:
    return _has_block_overlap(recommendation_block, parking_blocks)


def _is_market_history_overlap_with_recommendation(
    recommendation_block: str | None,
    weak_blocks: list[Dict] | list[str] | None,
) -> bool:
    return _has_block_overlap(recommendation_block, weak_blocks)


def _should_promote_clean_recommendation_alternative(primary_block: dict, alternative_block: dict) -> bool:
    primary_amount = _coerce_optional_float(primary_block.get("suggested_amount")) or 0.0
    alternative_amount = _coerce_optional_float(alternative_block.get("suggested_amount")) or 0.0
    if primary_amount <= 0:
        return alternative_amount > 0
    return alternative_amount >= (primary_amount * 0.5)


def _build_decision_recommendation(
    monthly_plan: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    monthly_plan = monthly_plan or {}
    recommended_blocks = list(monthly_plan.get("recommended_blocks") or [])
    primary_block = next(iter(recommended_blocks), None)
    if not primary_block:
        return {
            "block": None,
            "amount": None,
            "reason": "Todavia no hay un bloque dominante para este mes.",
            "has_recommendation": False,
            "priority_label": "Sin prioridad",
            "priority_tone": "secondary",
            "is_conditioned_by_parking": False,
        }
    block_label = primary_block.get("label")
    reason = str(primary_block.get("reason") or "").strip()
    parking_overlap = _is_parking_overlap_with_recommendation(
        block_label,
        (parking_feature or {}).get("parking_blocks") or [],
    )
    market_history_overlap = _is_market_history_overlap_with_recommendation(
        block_label,
        (market_history_feature or {}).get("weak_blocks") or [],
    )
    if market_history_overlap:
        clean_alternative = next(
            (
                block for block in recommended_blocks[1:]
                if not _is_market_history_overlap_with_recommendation(
                    str(block.get("label") or "").strip(),
                    (market_history_feature or {}).get("weak_blocks") or [],
                )
                and _should_promote_clean_recommendation_alternative(primary_block, block)
            ),
            None,
        )
        if clean_alternative is not None:
            alternative_label = str(clean_alternative.get("label") or "").strip()
            alternative_reason = str(clean_alternative.get("reason") or "").strip()
            return {
                "block": alternative_label,
                "amount": _coerce_optional_float(clean_alternative.get("suggested_amount")),
                "reason": (
                    f"Se prioriza {alternative_label} porque el bloque original {block_label} viene con liquidez reciente debil. "
                    f"{alternative_reason or 'La alternativa limpia conserva una asignacion razonable dentro del mismo plan mensual.'}"
                ).strip(),
                "has_recommendation": True,
                "priority_label": "Repriorizada por liquidez reciente",
                "priority_tone": "warning",
                "is_conditioned_by_parking": False,
                "is_conditioned_by_market_history": False,
                "was_reprioritized_by_market_history": True,
                "original_block_label": block_label,
            }
    if parking_overlap:
        reason = f"{reason} Hay parking visible dentro de este mismo bloque y conviene revisar la restriccion antes de ejecutar."
    elif market_history_overlap:
        reason = f"{reason} La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de tomarlo como prioridad limpia."
    return {
        "block": block_label,
        "amount": _coerce_optional_float(primary_block.get("suggested_amount")),
        "reason": reason,
        "has_recommendation": True,
        "priority_label": "Condicionada" if (parking_overlap or market_history_overlap) else "Prioritaria",
        "priority_tone": "warning" if (parking_overlap or market_history_overlap) else "success",
        "is_conditioned_by_parking": parking_overlap,
        "is_conditioned_by_market_history": market_history_overlap,
        "was_reprioritized_by_market_history": False,
        "original_block_label": block_label,
    }


def _build_decision_suggested_assets(
    ranking: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> list[Dict]:
    ranking = ranking or {}
    assets = []
    for item in (ranking.get("candidate_assets") or []):
        block_label = item.get("block_label")
        conditioned_by_parking = _is_parking_overlap_with_recommendation(
            block_label,
            (parking_feature or {}).get("parking_blocks") or [],
        )
        conditioned_by_market_history = _is_market_history_overlap_with_recommendation(
            block_label,
            (market_history_feature or {}).get("weak_blocks") or [],
        )
        if conditioned_by_parking:
            priority_label = "Condicionado por parking"
        elif conditioned_by_market_history:
            priority_label = "Condicionado por liquidez reciente"
        else:
            priority_label = ""
        assets.append(
            {
                "symbol": item.get("asset"),
                "block": block_label,
                "score": _coerce_optional_float(item.get("score")),
                "reason": item.get("main_reason"),
                "is_conditioned_by_parking": conditioned_by_parking,
                "is_conditioned_by_market_history": conditioned_by_market_history,
                "priority_label": priority_label,
                "market_history_note": (
                    "La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de usarlo como candidato principal."
                    if conditioned_by_market_history
                    else ""
                ),
            }
        )
    assets.sort(
        key=lambda item: (
            1 if item["is_conditioned_by_parking"] else 0,
            1 if item["is_conditioned_by_market_history"] else 0,
            -(item["score"] or 0),
        )
    )
    return assets[:3]


def _build_purchase_plan_blocks(purchase_plan: list[Dict]) -> list[str]:
    symbols = [str(item.get("symbol") or "").strip().upper() for item in purchase_plan if item.get("symbol")]
    if not symbols:
        return []
    parametros = ParametroActivo.objects.filter(simbolo__in=symbols)
    labels: list[str] = []
    for parametro in parametros:
        label = str(getattr(parametro, "bloque_estrategico", "") or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _annotate_decision_proposal_with_market_context(
    proposal: Dict,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    annotated = dict(proposal or {})
    purchase_plan = list(annotated.get("purchase_plan") or [])
    purchase_plan_blocks = _build_purchase_plan_blocks(purchase_plan)
    parking_overlap = any(
        _is_parking_overlap_with_recommendation(block_label, (parking_feature or {}).get("parking_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    market_history_overlap = any(
        _is_market_history_overlap_with_recommendation(block_label, (market_history_feature or {}).get("weak_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    if parking_overlap:
        priority_label = "Condicionada por parking"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con parking visible y conviene revisarla antes de tomarla como ejecucion directa."
    elif market_history_overlap:
        priority_label = "Condicionada por liquidez reciente"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con liquidez reciente debil y conviene revisar spread y actividad antes de ejecutarla."
    else:
        priority_label = "Lista"
        priority_tone = "success"
        note = ""
    annotated.update(
        {
            "purchase_plan": purchase_plan,
            "purchase_plan_blocks": purchase_plan_blocks,
            "is_conditioned_by_parking": parking_overlap,
            "is_conditioned_by_market_history": market_history_overlap,
            "priority_label": priority_label,
            "priority_tone": priority_tone,
            "parking_note": note,
            "was_reprioritized_by_parking": False,
            "was_reprioritized_by_market_history": False,
        }
    )
    return annotated


def _should_promote_clean_alternative(conditioned: Dict, clean: Dict) -> bool:
    conditioned_score = _coerce_optional_float(conditioned.get("comparison_score"))
    clean_score = _coerce_optional_float(clean.get("comparison_score"))
    if clean_score is None:
        return False
    if conditioned_score is None:
        return True
    return clean_score >= (conditioned_score - 0.25)


def _build_decision_preferred_proposal(
    preferred_payload: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict | None:
    preferred_payload = preferred_payload or {}
    preferred = preferred_payload.get("preferred")
    if not preferred:
        return None

    def normalize_candidate(item: Dict) -> Dict:
        simulation = item.get("simulation") or {}
        return {
            "proposal_key": item.get("proposal_key"),
            "proposal_label": item.get("proposal_label") or item.get("label"),
            "source_label": item.get("source_label"),
            "comparison_score": _coerce_optional_float(item.get("comparison_score")),
            "purchase_plan": list(item.get("purchase_plan") or []),
            "purchase_summary": item.get("purchase_summary") or build_incremental_purchase_plan_summary(
                list(item.get("purchase_plan") or [])
            ),
            "simulation_delta": dict(simulation.get("delta") or item.get("simulation_delta") or {}),
            "simulation_interpretation": str(simulation.get("interpretation") or item.get("simulation_interpretation") or ""),
            "priority_rank": int(item.get("priority_rank") or 0),
        }

    raw_candidates = [normalize_candidate(item) for item in (preferred_payload.get("candidates") or [])]
    if not raw_candidates:
        raw_candidates = [normalize_candidate(preferred)]

    annotated_candidates = [
        _annotate_decision_proposal_with_market_context(
            item,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        for item in raw_candidates
    ]

    selected = next(
        (
            item for item in annotated_candidates
            if item.get("proposal_key") == preferred.get("proposal_key")
        ),
        annotated_candidates[0],
    )

    if selected.get("is_conditioned_by_parking"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_parking"] = True
            selected["priority_label"] = "Repriorizada por parking"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con parking visible."
            )
    elif selected.get("is_conditioned_by_market_history"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_market_history"] = True
            selected["priority_label"] = "Repriorizada por liquidez reciente"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con liquidez reciente debil."
            )

    return selected
