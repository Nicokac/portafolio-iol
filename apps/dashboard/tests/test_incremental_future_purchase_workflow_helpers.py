from apps.dashboard.incremental_future_purchase_workflow import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_workflow_summary,
)


def test_annotate_incremental_future_purchase_recommended_items_marks_matching_rows():
    shortlist, history = _annotate_incremental_future_purchase_recommended_items(
        {
            "items": [
                {
                    "proposal_label": "KO defensivo",
                    "source": "backlog_nuevo",
                    "snapshot_id": 10,
                    "reapply_querystring": "a=1",
                    "is_backlog_front": False,
                    "is_tracking_baseline": False,
                }
            ]
        },
        {
            "items": [
                {
                    "proposal_label": "KO defensivo",
                    "future_purchase_context": {"source": "backlog_nuevo"},
                    "snapshot_id": 10,
                    "reapply_querystring": "a=1",
                    "is_backlog_front": False,
                    "is_tracking_baseline": False,
                }
            ]
        },
        {
            "source": "backlog_nuevo",
            "proposal_label": "KO defensivo",
            "next_action": "Revisar primero KO defensivo.",
            "has_guidance": True,
        },
    )

    assert shortlist["has_recommended_item"] is True
    assert history["has_future_purchase_recommended_item"] is True
    assert shortlist["items"][0]["future_purchase_recommendation_actions"]["can_promote_baseline"] is True


def test_build_incremental_future_purchase_workflow_summary_prioritizes_promote_baseline():
    summary = _build_incremental_future_purchase_workflow_summary(
        {
            "items": [
                {
                    "proposal_label": "MCD calidad",
                    "is_future_purchase_recommended": True,
                    "future_purchase_recommendation_actions": {
                        "can_promote_baseline": True,
                        "can_promote_front": False,
                        "can_reapply": False,
                    },
                }
            ]
        },
        {"proposal_label": "MCD calidad"},
    )

    assert summary["status"] == "ready_to_promote"
    assert "MCD calidad" in summary["headline"]


def test_build_incremental_future_purchase_source_guidance_prefers_reactivated_item():
    guidance = _build_incremental_future_purchase_source_guidance(
        {"headline": "Reactivadas hoy concentra la mejor fuente."},
        {"preferred_source": "reactivadas"},
        {},
        {
            "items": [
                {
                    "proposal_label": "PAMP reactivada",
                    "is_active": True,
                }
            ]
        },
    )

    assert guidance["source"] == "reactivadas"
    assert guidance["proposal_label"] == "PAMP reactivada"
