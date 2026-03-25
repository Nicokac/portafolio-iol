from apps.dashboard.decision_engine import (
    _build_manual_incremental_execution_readiness_summary,
)
from apps.dashboard.decision_execution import (
    _build_decision_action_suggestions,
    _build_decision_operation_execution_signal,
)


def test_build_decision_operation_execution_signal_marks_high_observed_cost_as_costly():
    signal = _build_decision_operation_execution_signal(
        operation_execution_feature={
            "tracked_symbols": ["KO"],
            "matched_symbols_count": 1,
            "missing_symbols_count": 0,
            "coverage_pct": 100,
            "rows": [
                {
                    "simbolo": "KO",
                    "fee_over_amount_pct": 2.4,
                    "cost_status": "high",
                    "is_fragmented": False,
                }
            ],
            "execution_analytics": {
                "fragmented_pct": 0,
                "observed_cost_status": "high",
                "observed_cost_summary": "Costo observado alto en KO.",
            },
        },
        preferred_proposal={"proposal_label": "Top candidato por bloque"},
    )

    assert signal["status"] == "costly"
    assert signal["has_signal"] is True
    assert signal["tracked_symbols"] == ["KO"]
    assert "aranceles visibles" in signal["summary"]


def test_build_decision_action_suggestions_adds_operation_cost_message_for_costly_signal():
    suggestions = _build_decision_action_suggestions(
        "deploy_cash",
        operation_execution_signal={"status": "costly"},
    )

    assert suggestions == [
        {
            "type": "allocation",
            "message": "Tenés capital disponible para invertir",
            "suggestion": "Evaluar asignar entre 20% y 40% del cash.",
        },
        {
            "type": "operation_cost",
            "message": "La huella reciente muestra friccion operativa visible",
            "suggestion": "Conviene revisar aranceles observados y tamano de orden antes de priorizar esta compra.",
        },
    ]


def test_build_manual_incremental_execution_readiness_summary_handles_missing_best_proposal():
    summary = _build_manual_incremental_execution_readiness_summary(None)

    assert summary == {
        "has_summary": False,
        "status": "pending",
        "label": "",
        "tone": "secondary",
        "headline": "",
        "summary": "",
    }
