from apps.dashboard.decision_execution import (
    _build_decision_execution_gate,
    _build_decision_recommendation,
)


def test_build_decision_recommendation_reprioritizes_clean_alternative_when_market_history_is_weak():
    result = _build_decision_recommendation(
        {
            "recommended_blocks": [
                {
                    "label": "Defensivos USD",
                    "suggested_amount": 600000,
                    "reason": "bloque original",
                },
                {
                    "label": "Calidad global",
                    "suggested_amount": 400000,
                    "reason": "alternativa limpia",
                },
            ]
        },
        market_history_feature={
            "weak_blocks": [{"label": "Defensivos USD"}],
        },
    )

    assert result["block"] == "Calidad global"
    assert result["was_reprioritized_by_market_history"] is True


def test_build_decision_execution_gate_blocks_when_execution_signal_is_partial():
    result = _build_decision_execution_gate(
        parking_signal={"has_signal": False},
        operation_execution_signal={"status": "partial", "summary": "Cobertura parcial."},
        preferred_proposal={"proposal_label": "Top candidato"},
    )

    assert result["has_blocker"] is True
    assert result["status"] == "review_execution"
