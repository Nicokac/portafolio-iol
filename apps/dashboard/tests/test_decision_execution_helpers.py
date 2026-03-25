from apps.dashboard.decision_execution import _build_decision_execution_gate


def test_build_decision_execution_gate_blocks_when_execution_signal_is_partial():
    result = _build_decision_execution_gate(
        parking_signal={"has_signal": False},
        operation_execution_signal={"status": "partial", "summary": "Cobertura parcial."},
        preferred_proposal={"proposal_label": "Top candidato"},
    )

    assert result["has_blocker"] is True
    assert result["status"] == "review_execution"
