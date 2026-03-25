from unittest.mock import patch

from apps.dashboard.incremental_backlog_analysis import (
    build_incremental_baseline_drift_payload,
    build_incremental_pending_backlog_vs_baseline_payload,
    build_incremental_proposal_history_payload,
)


class DummyService:
    MAX_SNAPSHOTS_PER_USER = 10

    def __init__(self, items=None, counts=None):
        self._items = items or []
        self._counts = counts or {}

    def list_recent(self, *, user, limit, decision_status):
        return list(self._items)

    def get_decision_counts(self, *, user):
        return dict(self._counts)

    def normalize_serialized_snapshot(self, item):
        return dict(item)


def test_build_incremental_proposal_history_payload_keeps_reactivated_source_context():
    item = {
        "id": 7,
        "proposal_label": "Plan A",
        "manual_decision_status": "pending",
        "is_backlog_front": False,
    }
    service = DummyService(items=[item], counts={"pending": 1})
    with (
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_snapshot_reapply_payload",
            return_value={"reapply_querystring": "snapshot=7"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_tactical_trace",
            return_value={"has_trace": False, "badges": []},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_baseline_trace",
            return_value={"headline": "Baseline"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_priority",
            return_value={"priority": "recoverable"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_deferred_fit",
            return_value={"status": "ready"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_future_purchase_history_context",
            return_value={"source": "reactivated", "reactivated": True},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_priority_counts",
            return_value={"recoverable": 1},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_deferred_fit_counts",
            return_value={"ready": 1},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_future_purchase_source_counts",
            return_value={"reactivated": 1},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._sort_incremental_history_items",
            side_effect=lambda items, **kwargs: items,
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_future_purchase_source_summary",
            return_value={"headline": "Reactivadas"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_future_purchase_source_quality_summary",
            return_value={"status": "good"},
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_available_filters",
            return_value=[],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_priority_filter_options",
            return_value=[],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_deferred_fit_filter_options",
            return_value=[],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_future_purchase_source_filter_options",
            return_value=[],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_sort_options",
            return_value=[],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_history_headline",
            return_value="Historial",
        ),
    ):
        payload = build_incremental_proposal_history_payload(
            service=service,
            user=object(),
            limit=5,
            normalized_filter="pending",
            normalized_priority_filter=None,
            normalized_deferred_fit_filter=None,
            normalized_future_purchase_source_filter=None,
            normalized_sort_mode="recent",
            preferred_source=None,
            baseline_payload={"item": {"proposal_label": "Base"}},
            reactivated_snapshot_ids=[7],
        )

    assert payload["count"] == 1
    assert payload["items"][0]["future_purchase_context"]["source"] == "reactivated"
    assert payload["future_purchase_source_counts"]["reactivated"] == 1


def test_build_incremental_baseline_drift_payload_marks_alerts_and_drift():
    baseline = {"proposal_label": "Base"}
    preferred = {"proposal_label": "Plan A"}
    comparison = {"winner": "current"}
    summary = {"status": "favorable"}
    alerts = [{"severity": "medium"}]
    with (
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_snapshot_comparison",
            return_value=comparison,
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_baseline_drift_summary",
            return_value=summary,
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_baseline_drift_alerts",
            return_value=alerts,
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_baseline_drift_explanation",
            return_value="Explicacion",
        ),
    ):
        payload = build_incremental_baseline_drift_payload(
            baseline_payload={"item": baseline},
            preferred_payload={"preferred": preferred},
        )

    assert payload["has_drift"] is True
    assert payload["alerts_count"] == 1
    assert payload["summary"]["status"] == "favorable"


def test_build_incremental_pending_backlog_vs_baseline_payload_picks_best_candidate():
    pending_history = {
        "items": [
            {
                "proposal_label": "Plan A",
                "baseline_trace": {"headline": "Mejora"},
                "tactical_trace": {"has_trace": False, "badges": []},
            },
            {
                "proposal_label": "Plan B",
                "baseline_trace": {"headline": "Peor"},
                "tactical_trace": {"has_trace": True, "badges": [{"label": "Otra cosa"}]},
            },
        ],
        "decision_counts": {"pending": 2},
    }
    comparisons = [
        {
            "winner": "current",
            "score_difference": 4,
            "metrics": [
                {"key": "expected_return_change", "direction": "favorable"},
                {"key": "fragility_change", "direction": "neutral"},
                {"key": "scenario_loss_change", "direction": "neutral"},
            ],
        },
        {
            "winner": "saved",
            "score_difference": -2,
            "metrics": [
                {"key": "expected_return_change", "direction": "unfavorable"},
                {"key": "fragility_change", "direction": "unfavorable"},
                {"key": "scenario_loss_change", "direction": "unfavorable"},
            ],
        },
    ]
    with (
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_snapshot_comparison",
            side_effect=comparisons,
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_baseline_drift_summary",
            side_effect=[{"status": "favorable"}, {"status": "unfavorable"}],
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._format_incremental_followup_status",
            side_effect=lambda status: status.upper(),
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_pending_backlog_headline",
            return_value="Backlog",
        ),
        patch(
            "apps.dashboard.incremental_backlog_analysis._build_incremental_pending_backlog_explanation",
            return_value="Explicacion",
        ),
    ):
        payload = build_incremental_pending_backlog_vs_baseline_payload(
            baseline_payload={"item": {"proposal_label": "Base"}},
            pending_history=pending_history,
        )

    assert payload["better_count"] == 1
    assert payload["worse_count"] == 1
    assert payload["best_candidate"]["snapshot"]["proposal_label"] == "Plan A"
