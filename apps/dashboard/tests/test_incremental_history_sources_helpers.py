from apps.dashboard.incremental_history_sources import (
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_history_sort_options,
)


def test_build_incremental_future_purchase_history_context_marks_reactivated_pending_snapshot():
    context = _build_incremental_future_purchase_history_context(
        {"id": 7, "manual_decision_status": "pending"},
        reactivated_snapshot_ids={7},
    )

    assert context["source"] == "reactivadas"
    assert context["is_relevant"] is True


def test_build_incremental_future_purchase_source_quality_summary_detects_best_source():
    summary = _build_incremental_future_purchase_source_quality_summary(
        [
            {
                "future_purchase_context": {"source": "backlog_nuevo"},
                "history_priority": {"priority": "high"},
                "simulation_delta": {"expected_return_change": 0.5, "fragility_change": -1.0},
                "tactical_trace": {"has_trace": False, "badges": []},
                "comparison_score": 5.0,
            },
            {
                "future_purchase_context": {"source": "reactivadas"},
                "history_priority": {"priority": "low"},
                "simulation_delta": {"expected_return_change": -0.2, "fragility_change": 0.5},
                "tactical_trace": {"has_trace": True, "badges": [{"label": "Parking"}]},
                "comparison_score": 1.0,
            },
        ]
    )

    assert summary["dominant_source"] == "backlog_nuevo"
    assert "Backlog nuevo" in summary["headline"]


def test_build_incremental_history_sort_options_marks_selected_option():
    options = _build_incremental_history_sort_options("future_purchase")

    assert options[2]["key"] == "future_purchase"
    assert options[2]["selected"] is True
