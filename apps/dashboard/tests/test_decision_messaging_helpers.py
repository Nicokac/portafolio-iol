from apps.dashboard.decision_messaging import (
    _build_decision_explanation,
    _build_decision_tracking_payload,
)


def test_build_decision_explanation_adds_partial_execution_note():
    bullets = _build_decision_explanation(
        macro_state={"label": "Normal", "summary": "no invalida nada"},
        recommendation={"block": "Defensivos USD", "reason": "mejora resiliencia"},
        expected_impact={"status": "mixed"},
        confidence="Media",
        preferred_proposal={"proposal_label": "Top candidato"},
        operation_execution_signal={"status": "partial"},
    )

    assert any("cobertura operativa parcial" in bullet for bullet in bullets)


def test_build_decision_tracking_payload_includes_governance_statuses():
    payload = _build_decision_tracking_payload(
        preferred_proposal={"proposal_label": "Top candidato", "purchase_plan": [], "simulation_delta": {}},
        recommendation={"block": "Defensivos USD", "amount": 600000, "priority_label": "Prioritaria"},
        expected_impact={"status": "positive"},
        score=72,
        confidence="Alta",
        macro_state={"key": "normal"},
        portfolio_state={"key": "ok"},
        operation_execution_signal={"has_signal": True, "status": "watch_cost", "tracked_symbols": ["KO"]},
        execution_gate={"key": "ready"},
    )

    assert payload["governance"]["execution_gate_key"] == "ready"
    assert payload["governance"]["operation_execution_signal_status"] == "watch_cost"
