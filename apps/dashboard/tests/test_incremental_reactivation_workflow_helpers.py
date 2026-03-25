from apps.dashboard.incremental_reactivation_workflow import (
    _build_incremental_reactivation_vs_backlog_summary,
)

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
