from apps.dashboard.incremental_backlog_decision import (
    build_incremental_adoption_checklist,
    build_incremental_decision_executive_summary,
)


def test_build_incremental_adoption_checklist_marks_ready_when_all_checks_pass():
    result = build_incremental_adoption_checklist(
        preferred_payload={
            "preferred": {
                "proposal_label": "KO defensivo",
                "purchase_plan": [{"symbol": "KO", "amount": 600000}],
            }
        },
        baseline_payload={"item": {"proposal_label": "Baseline actual"}},
        drift_payload={
            "summary": {"status": "stable"},
            "alerts": [],
        },
        executive_payload={"status": "aligned"},
    )

    assert result["status"] == "ready"
    assert result["adoption_ready"] is True


def test_build_incremental_decision_executive_summary_prioritizes_review_backlog_when_yellow():
    result = build_incremental_decision_executive_summary(
        semaphore={"status": "yellow", "has_signal": True},
        followup={"has_summary": True},
        checklist={"status": "review", "total_count": 5},
        front_summary={"has_summary": True},
    )

    assert result["status"] == "review_backlog"
    assert result["has_summary"] is True
