from apps.dashboard.incremental_comparator_ui import (
    _build_incremental_comparator_activity_summary,
    _build_incremental_comparator_hidden_inputs,
    _build_planeacion_aportes_reset_url,
)


def test_build_incremental_comparator_hidden_inputs_preserves_manual_fields():
    inputs = _build_incremental_comparator_hidden_inputs(
        {
            "manual_compare": "1",
            "plan_a_symbol_1": "KO",
            "plan_a_amount_1": "100000",
            "plan_a_execution_order_label": "Primero KO",
        }
    )
    names = {item["name"] for item in inputs}
    assert "manual_compare" in names
    assert "plan_a_symbol_1" in names
    assert "plan_a_execution_order_label" in names


def test_build_planeacion_aportes_reset_url_excludes_requested_keys():
    url = _build_planeacion_aportes_reset_url(
        {
            "candidate_compare": "1",
            "candidate_compare_block": "defensive",
            "manual_compare": "1",
        },
        exclude_keys={"candidate_compare_block"},
    )
    assert "candidate_compare=1" in url
    assert "candidate_compare_block" not in url
    assert url.endswith("#planeacion-aportes")


def test_build_incremental_comparator_activity_summary_counts_active_sections():
    summary = _build_incremental_comparator_activity_summary(
        auto={"has_active_readiness_filter": True, "active_readiness_filter_label": "Listo"},
        candidate={"submitted": True, "selected_label": "Defensive", "has_active_readiness_filter": False},
        split={"submitted": False, "has_active_readiness_filter": False, "selected_block": None},
        manual={"submitted": True, "has_active_readiness_filter": True, "active_readiness_filter_label": "Validar"},
    )
    assert summary["active_count"] == 3
    assert summary["has_active_context"] is True
