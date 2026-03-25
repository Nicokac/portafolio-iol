from unittest.mock import patch

from apps.dashboard.incremental_simulation_comparison import (
    build_empty_incremental_comparison_payload,
    build_incremental_comparison_payload,
    build_simulated_incremental_proposal,
)


class DummySimulator:
    def simulate(self, payload):
        return {
            "before": {"weight": 1},
            "after": {"weight": 2},
            "delta": {"expected_return_change": 1},
            "interpretation": "ok",
            "warnings": ["warn"],
        }


def test_build_empty_incremental_comparison_payload_marks_filter_state():
    payload = build_empty_incremental_comparison_payload(
        submitted=True,
        readiness_filter="ready",
        lead_label="Mejor balance manual",
        form_state={"submitted": True},
    )
    assert payload["submitted"] is True
    assert payload["has_active_readiness_filter"] is True
    assert payload["form_state"]["submitted"] is True


def test_build_simulated_incremental_proposal_enriches_execution_fields():
    with (
        patch(
            "apps.dashboard.incremental_simulation_comparison._score_incremental_simulation",
            return_value=0.75,
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._annotate_preferred_proposal_with_execution_quality",
            side_effect=lambda proposal, operation_execution_feature: {
                **proposal,
                "execution_quality": operation_execution_feature["summary"],
            },
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._build_decision_operation_execution_signal",
            return_value={"status": "strong"},
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._build_manual_incremental_execution_readiness",
            return_value={"status": "ready"},
        ),
    ):
        result = build_simulated_incremental_proposal(
            base_payload={"proposal_key": "plan_a", "label": "Plan A"},
            capital_amount=100000,
            purchase_plan=[{"symbol": "AAPL", "amount": 100000}],
            operation_execution_feature_getter=lambda **kwargs: {"summary": "usable"},
            simulator=DummySimulator(),
        )

    assert result["comparison_score"] == 0.75
    assert result["operation_execution_signal"]["status"] == "strong"
    assert result["execution_readiness"]["status"] == "ready"


def test_build_incremental_comparison_payload_clears_tiebreak_when_filter_active():
    proposals = [
        {
            "proposal_key": "plan_a",
            "label": "Plan A",
            "comparison_score": 0.8,
            "execution_readiness": {"status": "ready"},
        }
    ]
    with (
        patch(
            "apps.dashboard.incremental_simulation_comparison._build_incremental_readiness_filter_metadata",
            return_value={
                "filtered_proposals": proposals,
                "active_readiness_filter": "ready",
                "active_readiness_filter_label": "Listo",
                "available_readiness_filters": [],
                "visible_count": 1,
                "total_count": 1,
                "has_active_readiness_filter": True,
            },
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._build_manual_incremental_execution_readiness_summary",
            return_value={"status": "ready"},
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._build_incremental_comparator_summary",
            return_value="summary",
        ),
        patch(
            "apps.dashboard.incremental_simulation_comparison._resolve_manual_incremental_operational_tiebreak",
            return_value=(
                proposals,
                proposals[0],
                {"has_tiebreak": True, "used_operational_tiebreak": True, "headline": "x", "summary": "y"},
            ),
        ),
    ):
        payload = build_incremental_comparison_payload(
            proposals=proposals,
            readiness_filter="ready",
            lead_label="Mejor balance manual",
            submitted=True,
            use_operational_tiebreak=True,
        )

    assert payload["best_proposal_key"] == "plan_a"
    assert payload["operational_tiebreak"]["has_tiebreak"] is False
