from typing import Dict

from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator
from apps.dashboard.decision_engine import (
    _build_manual_incremental_execution_readiness,
    _build_manual_incremental_execution_readiness_summary,
)
from apps.dashboard.decision_execution import (
    _annotate_preferred_proposal_with_execution_quality,
    _build_decision_operation_execution_signal,
)
from apps.dashboard.incremental_comparators import (
    _build_incremental_comparator_summary,
    _build_incremental_readiness_filter_metadata,
    _build_incremental_readiness_filter_options,
    _format_incremental_readiness_filter_label,
    _normalize_incremental_proposal_item,
    _resolve_manual_incremental_operational_tiebreak,
    _score_incremental_simulation,
)


def build_empty_operational_tiebreak() -> Dict:
    return {
        "has_tiebreak": False,
        "used_operational_tiebreak": False,
        "headline": "",
        "summary": "",
    }


def build_empty_incremental_comparison_payload(
    *,
    submitted: bool = False,
    readiness_filter: str,
    lead_label: str,
    available_blocks: list[dict] | None = None,
    selected_block: str | None = None,
    selected_label: str | None = None,
    block_amount: int | float | None = None,
    form_state: Dict | None = None,
) -> Dict:
    empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
    empty_tiebreak = build_empty_operational_tiebreak()
    payload = {
        "submitted": submitted,
        "proposals": [],
        "best_proposal_key": None,
        "best_label": None,
        "best_execution_readiness": empty_readiness,
        "operational_tiebreak": empty_tiebreak,
        "active_readiness_filter": readiness_filter,
        "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
        "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
        "visible_count": 0,
        "total_count": 0,
        "has_active_readiness_filter": readiness_filter != "all",
        "display_summary": _build_incremental_comparator_summary(
            lead_label=lead_label,
            best_label=None,
            best_execution_readiness=empty_readiness,
            operational_tiebreak=empty_tiebreak,
        ),
    }
    if available_blocks is not None:
        payload["available_blocks"] = available_blocks
        payload["selected_block"] = selected_block
        payload["selected_label"] = selected_label
        payload["block_amount"] = block_amount
    if form_state is not None:
        payload["form_state"] = form_state
    return payload


def build_simulated_incremental_proposal(
    *,
    base_payload: Dict,
    capital_amount: int | float,
    purchase_plan: list[dict],
    operation_execution_feature_getter,
    symbol_limit: int = 3,
    lookback_days: int = 180,
    simulator: IncrementalPortfolioSimulator | None = None,
) -> Dict:
    simulator = simulator or IncrementalPortfolioSimulator()
    simulation = simulator.simulate(
        {
            "capital_amount": capital_amount,
            "purchase_plan": purchase_plan,
        }
    )
    operation_execution_feature = operation_execution_feature_getter(
        purchase_plan=purchase_plan,
        lookback_days=lookback_days,
        symbol_limit=symbol_limit,
    )
    proposal = _annotate_preferred_proposal_with_execution_quality(
        _normalize_incremental_proposal_item(
            {
                **base_payload,
                "purchase_plan": purchase_plan,
                "simulation": {
                    "before": simulation["before"],
                    "after": simulation["after"],
                    "delta": simulation["delta"],
                    "interpretation": simulation["interpretation"],
                    "warnings": simulation.get("warnings", []),
                },
                "comparison_score": _score_incremental_simulation(simulation),
            }
        ),
        operation_execution_feature=operation_execution_feature,
    )
    operation_execution_signal = _build_decision_operation_execution_signal(
        operation_execution_feature=operation_execution_feature,
        preferred_proposal=proposal,
    )
    proposal["operation_execution_signal"] = operation_execution_signal
    proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
        proposal=proposal,
        operation_execution_signal=operation_execution_signal,
    )
    return proposal


def build_incremental_comparison_payload(
    *,
    proposals: list[dict],
    readiness_filter: str,
    lead_label: str,
    selected_label: str | None = None,
    submitted: bool = False,
    available_blocks: list[dict] | None = None,
    selected_block: str | None = None,
    block_amount: int | float | None = None,
    form_state: Dict | None = None,
    use_operational_tiebreak: bool = True,
) -> Dict:
    ranked = list(proposals)
    operational_tiebreak = build_empty_operational_tiebreak()
    if use_operational_tiebreak:
        ranked, _, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
    filter_metadata = _build_incremental_readiness_filter_metadata(
        proposals=ranked,
        readiness_filter=readiness_filter,
    )
    visible_ranked = filter_metadata["filtered_proposals"]
    best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
    if filter_metadata["has_active_readiness_filter"]:
        operational_tiebreak = build_empty_operational_tiebreak()
    best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
    payload = {
        "submitted": submitted,
        "proposals": visible_ranked,
        "best_proposal_key": best["proposal_key"] if best else None,
        "best_label": best["label"] if best else None,
        "best_execution_readiness": best_execution_readiness,
        "operational_tiebreak": operational_tiebreak,
        "active_readiness_filter": filter_metadata["active_readiness_filter"],
        "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
        "available_readiness_filters": filter_metadata["available_readiness_filters"],
        "visible_count": filter_metadata["visible_count"],
        "total_count": filter_metadata["total_count"],
        "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
        "display_summary": _build_incremental_comparator_summary(
            lead_label=lead_label,
            best_label=best["label"] if best else None,
            selected_label=selected_label,
            best_execution_readiness=best_execution_readiness,
            operational_tiebreak=operational_tiebreak,
        ),
    }
    if available_blocks is not None:
        payload["available_blocks"] = available_blocks
        payload["selected_block"] = selected_block
        payload["selected_label"] = selected_label
        payload["block_amount"] = block_amount
    if form_state is not None:
        payload["form_state"] = form_state
    return payload
