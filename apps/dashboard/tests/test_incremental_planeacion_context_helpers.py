from apps.dashboard.incremental_planeacion_context import (
    build_incremental_comparator_form_state,
    build_planeacion_incremental_context_payload,
)


def test_build_incremental_comparator_form_state_preserves_manual_reset_contract():
    form_state = build_incremental_comparator_form_state(
        {
            "manual_compare": "1",
            "plan_a_symbol_1": "KO",
            "plan_a_amount_1": "100000",
            "candidate_compare": "1",
        }
    )
    assert "candidate_compare=1" in form_state["manual_reset_url"]
    assert "plan_a_symbol_1" not in form_state["manual_reset_url"]


def test_build_planeacion_incremental_context_payload_adds_future_purchase_workflow():
    payload = build_planeacion_incremental_context_payload(
        query_params={},
        portfolio_scope_summary={"cash_ratio_total": 0.3},
        monthly_allocation_plan={"recommended_blocks": []},
        candidate_asset_ranking={"candidate_assets": []},
        incremental_portfolio_simulation={"delta": {}},
        incremental_portfolio_simulation_comparison={"best_label": None},
        candidate_incremental_portfolio_comparison={"best_label": None},
        candidate_split_incremental_portfolio_comparison={"best_label": None},
        manual_incremental_portfolio_simulation_comparison={"best_label": None},
        preferred_incremental_portfolio_proposal={"preferred": None},
        operation_execution_feature={"has_context": False},
        decision_engine_summary={"score": 50},
        incremental_backlog_prioritization={"items": []},
        incremental_reactivation_summary={"items": []},
        incremental_proposal_history={"future_purchase_source_quality_summary": {}},
        incremental_proposal_tracking_baseline={"item": None},
        incremental_manual_decision_summary={"has_decision": False},
        incremental_decision_executive_summary={"status": "pending"},
    )

    assert "incremental_comparator_form_state" in payload
    assert "incremental_future_purchase_workflow_summary" in payload
    assert "incremental_reactivation_vs_backlog_summary" in payload
