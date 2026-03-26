from typing import Dict

from apps.dashboard.incremental_comparators import (
    _build_incremental_comparator_activity_summary,
    _build_incremental_comparator_hidden_inputs,
    _build_planeacion_aportes_reset_url,
)
from apps.dashboard.incremental_future_purchase_workflow import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_workflow_summary,
)
from apps.dashboard.incremental_reactivation_workflow import (
    _build_incremental_reactivation_vs_backlog_summary,
)


_MANUAL_COMPARATOR_EXCLUDE_KEYS = {
    "manual_compare",
    "manual_compare_readiness_filter",
    "plan_a_capital",
    "plan_a_execution_order_label",
    "plan_a_execution_order_summary",
    "plan_b_capital",
    "plan_b_execution_order_label",
    "plan_b_execution_order_summary",
    "plan_a_symbol_1",
    "plan_a_amount_1",
    "plan_a_symbol_2",
    "plan_a_amount_2",
    "plan_a_symbol_3",
    "plan_a_amount_3",
    "plan_b_symbol_1",
    "plan_b_amount_1",
    "plan_b_symbol_2",
    "plan_b_amount_2",
    "plan_b_symbol_3",
    "plan_b_amount_3",
}


def build_incremental_comparator_form_state(query_params) -> Dict:
    return {
        "general_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"comparison_readiness_filter"},
        ),
        "general_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"comparison_readiness_filter"},
        ),
        "candidate_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"candidate_compare", "candidate_compare_block", "candidate_compare_readiness_filter"},
        ),
        "candidate_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"candidate_compare", "candidate_compare_block", "candidate_compare_readiness_filter"},
        ),
        "split_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"candidate_split_compare", "candidate_split_block", "candidate_split_readiness_filter"},
        ),
        "split_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"candidate_split_compare", "candidate_split_block", "candidate_split_readiness_filter"},
        ),
        "manual_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys=_MANUAL_COMPARATOR_EXCLUDE_KEYS,
        ),
        "manual_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys=_MANUAL_COMPARATOR_EXCLUDE_KEYS,
        ),
    }


def build_planeacion_incremental_context_payload(
    *,
    query_params,
    portfolio_scope_summary: Dict,
    monthly_allocation_plan: Dict,
    candidate_asset_ranking: Dict,
    incremental_portfolio_simulation: Dict,
    incremental_portfolio_simulation_comparison: Dict,
    candidate_incremental_portfolio_comparison: Dict,
    candidate_split_incremental_portfolio_comparison: Dict,
    manual_incremental_portfolio_simulation_comparison: Dict,
    preferred_incremental_portfolio_proposal: Dict,
    operation_execution_feature: Dict,
    decision_engine_summary: Dict,
    incremental_backlog_prioritization: Dict,
    incremental_reactivation_summary: Dict,
    incremental_proposal_history: Dict,
    incremental_proposal_tracking_baseline: Dict,
    incremental_manual_decision_summary: Dict,
    incremental_decision_executive_summary: Dict,
) -> Dict:
    comparator_form_state = build_incremental_comparator_form_state(query_params)
    incremental_comparator_activity_summary = _build_incremental_comparator_activity_summary(
        auto=incremental_portfolio_simulation_comparison,
        candidate=candidate_incremental_portfolio_comparison,
        split=candidate_split_incremental_portfolio_comparison,
        manual=manual_incremental_portfolio_simulation_comparison,
    )
    incremental_reactivation_vs_backlog_summary = _build_incremental_reactivation_vs_backlog_summary(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
    )
    incremental_future_purchase_shortlist = _build_incremental_future_purchase_shortlist(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
        incremental_reactivation_vs_backlog_summary,
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        limit=3,
    )
    incremental_future_purchase_source_guidance = _build_incremental_future_purchase_source_guidance(
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        incremental_future_purchase_shortlist,
        incremental_backlog_prioritization,
        incremental_reactivation_summary,
    )
    (
        incremental_future_purchase_shortlist,
        incremental_proposal_history,
    ) = _annotate_incremental_future_purchase_recommended_items(
        incremental_future_purchase_shortlist,
        incremental_proposal_history,
        incremental_future_purchase_source_guidance,
    )
    incremental_future_purchase_workflow_summary = _build_incremental_future_purchase_workflow_summary(
        incremental_future_purchase_shortlist,
        incremental_future_purchase_source_guidance,
    )

    return {
        "portfolio_scope_summary": portfolio_scope_summary,
        "monthly_allocation_plan": monthly_allocation_plan,
        "candidate_asset_ranking": candidate_asset_ranking,
        "incremental_portfolio_simulation": incremental_portfolio_simulation,
        "incremental_portfolio_simulation_comparison": incremental_portfolio_simulation_comparison,
        "candidate_incremental_portfolio_comparison": candidate_incremental_portfolio_comparison,
        "candidate_split_incremental_portfolio_comparison": candidate_split_incremental_portfolio_comparison,
        "manual_incremental_portfolio_simulation_comparison": manual_incremental_portfolio_simulation_comparison,
        "incremental_comparator_form_state": comparator_form_state,
        "incremental_comparator_activity_summary": incremental_comparator_activity_summary,
        "preferred_incremental_portfolio_proposal": preferred_incremental_portfolio_proposal,
        "operation_execution_feature": operation_execution_feature,
        "decision_engine_summary": decision_engine_summary,
        "incremental_proposal_history": incremental_proposal_history,
        "incremental_proposal_tracking_baseline": incremental_proposal_tracking_baseline,
        "incremental_backlog_prioritization": incremental_backlog_prioritization,
        "incremental_manual_decision_summary": incremental_manual_decision_summary,
        "incremental_reactivation_summary": incremental_reactivation_summary,
        "incremental_reactivation_vs_backlog_summary": incremental_reactivation_vs_backlog_summary,
        "incremental_future_purchase_shortlist": incremental_future_purchase_shortlist,
        "incremental_future_purchase_source_guidance": incremental_future_purchase_source_guidance,
        "incremental_future_purchase_workflow_summary": incremental_future_purchase_workflow_summary,
        "incremental_decision_executive_summary": incremental_decision_executive_summary,
    }
