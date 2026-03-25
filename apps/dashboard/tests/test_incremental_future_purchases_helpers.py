from apps.dashboard.incremental_future_purchases import (
    _build_incremental_backlog_conviction,
    _build_incremental_backlog_followup,
    _build_incremental_backlog_shortlist_item,
)


def test_build_incremental_backlog_shortlist_item_enriches_edges_and_followup():
    result = _build_incremental_backlog_shortlist_item(
        index=1,
        item={
            "priority": "high",
            "priority_label": "Alta",
            "next_action": "Revisar hoy",
            "score_difference": 2.4,
            "improves_profitability": True,
            "protects_fragility": True,
            "tactical_clean": True,
            "snapshot": {
                "id": 7,
                "proposal_label": "KO defensivo",
                "selected_context": "Defensivos USD",
                "simulation_delta": {
                    "expected_return_change": 0.5,
                    "fragility_change": -1.2,
                    "scenario_loss_change": 0.3,
                },
                "reapply_querystring": "a=1",
                "is_backlog_front": True,
                "is_tracking_baseline": False,
            },
        },
    )

    assert result["economic_edge"] is True
    assert result["tactical_edge"] is True
    assert result["conviction"]["level"] == "high"
    assert result["followup"]["status"] == "review_now"


def test_build_incremental_backlog_conviction_falls_back_to_medium():
    result = _build_incremental_backlog_conviction(
        {"priority": "medium"},
        economic_edge=True,
        tactical_edge=False,
    )

    assert result["level"] == "medium"
    assert result["label"] == "Convicción media"


def test_build_incremental_backlog_followup_uses_hold_for_low_conviction():
    result = _build_incremental_backlog_followup(conviction_level="low")

    assert result["status"] == "hold"
    assert result["label"] == "En espera"
