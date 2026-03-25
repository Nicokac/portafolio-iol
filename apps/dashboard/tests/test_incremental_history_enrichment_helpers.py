from apps.dashboard.incremental_history_enrichment import (
    _build_incremental_future_purchase_source_summary,
    _build_incremental_history_baseline_trace,
    _build_incremental_tactical_trace,
    _sort_incremental_history_items,
)


def test_build_incremental_tactical_trace_detects_alternative_promotion():
    trace = _build_incremental_tactical_trace(
        {
            "decision_explanation": [
                "La propuesta fue reemplazada por una alternativa mas limpia.",
                "Liquidez reciente insuficiente para el simbolo lider.",
            ]
        }
    )

    assert trace["has_trace"] is True
    assert trace["headline"] == "Se promovio una alternativa mas limpia por liquidez reciente."
    assert any(badge["key"] == "alternative_promoted" for badge in trace["badges"])


def test_build_incremental_future_purchase_source_summary_respects_active_filter():
    summary = _build_incremental_future_purchase_source_summary(
        {"backlog_nuevo": 1, "reactivadas": 3},
        active_filter="backlog_nuevo",
    )

    assert summary["dominant_source"] == "backlog_nuevo"
    assert summary["dominant_label"] == "Domina backlog nuevo"


def test_build_incremental_history_baseline_trace_marks_better_than_baseline():
    trace = _build_incremental_history_baseline_trace(
        {
            "id": 1,
            "comparison_score": 4.0,
            "simulation_delta": {
                "expected_return_change": 0.2,
                "fragility_change": -1.0,
                "scenario_loss_change": 0.1,
            },
        },
        {
            "id": 2,
            "comparison_score": 4.6,
            "simulation_delta": {
                "expected_return_change": 0.5,
                "fragility_change": -1.3,
                "scenario_loss_change": 0.4,
            },
        },
        tactical_trace={"has_trace": False, "badges": []},
    )

    assert trace["has_trace"] is True
    assert trace["headline"] == "Supera al baseline en rentabilidad esperada y balance global."
    assert trace["badges"][0]["label"] == "Mejor que baseline"


def test_sort_incremental_history_items_respects_future_purchase_preferred_source():
    items = [
        {
            "proposal_label": "Backlog",
            "future_purchase_context": {"source": "backlog_nuevo"},
            "is_backlog_front": False,
            "history_priority": {"priority": "medium"},
            "comparison_score": 4.0,
        },
        {
            "proposal_label": "Reactivada",
            "future_purchase_context": {"source": "reactivadas"},
            "is_backlog_front": False,
            "history_priority": {"priority": "medium"},
            "comparison_score": 3.5,
        },
    ]

    sorted_items = _sort_incremental_history_items(
        items,
        sort_mode="future_purchase",
        preferred_source="reactivadas",
    )

    assert sorted_items[0]["proposal_label"] == "Reactivada"
