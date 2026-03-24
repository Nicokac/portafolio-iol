from apps.dashboard.incremental_future_purchases import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_reactivation_vs_backlog_summary,
    _build_incremental_tactical_trace,
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


def test_build_incremental_reactivation_vs_backlog_summary_prefers_reactivated_when_effective():
    summary = _build_incremental_reactivation_vs_backlog_summary(
        {
            "count": 3,
            "accepted_count": 2,
            "active_count": 1,
            "acceptance_rate": 66.7,
        },
        {
            "counts": {"high": 1, "medium": 0},
            "top_item": {"snapshot": {"proposal_label": "PAMP tactica"}},
            "has_priorities": True,
        },
    )

    assert summary["preferred_source"] == "reactivadas"
    assert summary["label"] == "Priorizar reactivadas"
