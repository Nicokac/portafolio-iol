from apps.dashboard.incremental_comparators import (
    _build_incremental_readiness_filter_metadata,
    _build_manual_incremental_comparison_form_state,
    _resolve_manual_incremental_operational_tiebreak,
)


def test_build_incremental_readiness_filter_metadata_filters_visible_proposals():
    metadata = _build_incremental_readiness_filter_metadata(
        proposals=[
            {"proposal_key": "a", "execution_readiness": {"status": "ready"}},
            {"proposal_key": "b", "execution_readiness": {"status": "review_execution"}},
            {"proposal_key": "c", "execution_readiness": {"status": "ready"}},
        ],
        readiness_filter="ready",
    )

    assert metadata["active_readiness_filter"] == "ready"
    assert metadata["visible_count"] == 2
    assert metadata["total_count"] == 3
    assert [item["proposal_key"] for item in metadata["filtered_proposals"]] == ["a", "c"]


def test_build_manual_incremental_comparison_form_state_preserves_execution_guidance():
    form_state = _build_manual_incremental_comparison_form_state(
        {
            "manual_compare": "1",
            "plan_a_capital": "600000",
            "plan_a_symbol_1": "KO",
            "plan_a_amount_1": "300000",
            "plan_a_symbol_2": "MCD",
            "plan_a_amount_2": "300000",
            "plan_a_execution_order_label": "Ejecutar primero",
            "plan_a_execution_order_summary": "Arrancar por KO y dejar MCD para una validacion adicional.",
        }
    )

    assert form_state["submitted"] is True
    assert form_state["plans"][0]["has_execution_order_guidance"] is True
    assert form_state["normalized_plans"][0]["execution_order_label"] == "Ejecutar primero"
    assert "Arrancar por KO" in form_state["normalized_plans"][0]["execution_order_summary"]


def test_resolve_manual_incremental_operational_tiebreak_promotes_cleaner_execution():
    ranked, best, tiebreak = _resolve_manual_incremental_operational_tiebreak(
        [
            {
                "proposal_key": "plan_a",
                "proposal_label": "Plan manual A",
                "comparison_score": 5.0,
                "execution_readiness": {"status": "review_execution"},
            },
            {
                "proposal_key": "plan_b",
                "proposal_label": "Plan manual B",
                "comparison_score": 4.9,
                "execution_readiness": {"status": "ready"},
            },
        ]
    )

    assert best["proposal_key"] == "plan_b"
    assert ranked[0]["proposal_key"] == "plan_b"
    assert tiebreak["has_tiebreak"] is True
    assert tiebreak["used_operational_tiebreak"] is True
