from apps.dashboard.incremental_followup import (
    _build_incremental_adoption_checklist_headline,
    _build_incremental_baseline_drift_summary,
    _build_incremental_snapshot_comparison,
    _build_incremental_snapshot_reapply_payload,
)


def test_build_incremental_snapshot_comparison_detects_favorable_current_variant():
    comparison = _build_incremental_snapshot_comparison(
        {
            "comparison_score": 4.0,
            "simulation_delta": {
                "expected_return_change": 0.3,
                "fragility_change": -1.0,
                "scenario_loss_change": 0.2,
            },
        },
        {
            "comparison_score": 4.8,
            "simulation_delta": {
                "expected_return_change": 0.5,
                "fragility_change": -1.8,
                "scenario_loss_change": 0.4,
            },
        },
    )

    assert comparison["winner"] == "current"
    assert comparison["score_difference"] == 0.8
    expected_metric = next(metric for metric in comparison["metrics"] if metric["key"] == "expected_return_change")
    fragility_metric = next(metric for metric in comparison["metrics"] if metric["key"] == "fragility_change")
    assert expected_metric["direction"] == "favorable"
    assert fragility_metric["direction"] == "favorable"


def test_build_incremental_baseline_drift_summary_marks_unfavorable_when_only_negative_metrics_change():
    summary = _build_incremental_baseline_drift_summary(
        {
            "metrics": [
                {"key": "expected_return_change", "direction": "unfavorable"},
                {"key": "fragility_change", "direction": "unfavorable"},
                {"key": "scenario_loss_change", "direction": "neutral"},
            ]
        }
    )

    assert summary["status"] == "unfavorable"
    assert summary["favorable_count"] == 0
    assert summary["unfavorable_count"] == 2
    assert summary["changed_count"] == 2


def test_build_incremental_snapshot_reapply_payload_truncates_after_three_lines_and_keeps_guidance():
    payload = _build_incremental_snapshot_reapply_payload(
        {
            "capital_amount": 600000,
            "purchase_plan": [
                {"symbol": "ko", "amount": 200000},
                {"symbol": "mcd", "amount": 200000},
                {"symbol": "xlu", "amount": 200000},
                {"symbol": "spy", "amount": 1000},
            ],
            "execution_quality": {
                "execution_order_label": "Ejecutar primero",
                "execution_order_summary": "Arrancar por KO y dejar MCD para una validacion adicional.",
            },
        }
    )

    assert payload["reapply_truncated"] is True
    assert "plan_a_symbol_1=KO" in payload["reapply_querystring"]
    assert "plan_a_symbol_4" not in payload["reapply_querystring"]
    assert "plan_a_execution_order_label=Ejecutar+primero" in payload["reapply_querystring"]


def test_build_incremental_adoption_checklist_headline_uses_ready_copy():
    headline = _build_incremental_adoption_checklist_headline(
        "ready",
        {"headline": "fallback"},
        {"proposal_label": "Propuesta actual"},
        {"proposal_label": "Baseline activo"},
    )

    assert "supera el checklist operativo" in headline
