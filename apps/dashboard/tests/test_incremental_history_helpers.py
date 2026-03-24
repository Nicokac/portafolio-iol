from apps.dashboard.incremental_history import (
    _build_incremental_decision_executive_headline,
    _build_incremental_history_headline,
    _classify_incremental_backlog_priority,
    _normalize_incremental_history_sort_mode,
)


def test_normalize_incremental_history_sort_mode_falls_back_to_newest():
    assert _normalize_incremental_history_sort_mode("priority") == "priority"
    assert _normalize_incremental_history_sort_mode("future_purchase") == "future_purchase"
    assert _normalize_incremental_history_sort_mode("anything-else") == "newest"


def test_classify_incremental_backlog_priority_marks_high_only_when_all_edges_hold():
    assert _classify_incremental_backlog_priority(
        {
            "beats_baseline": True,
            "improves_profitability": True,
            "protects_fragility": True,
            "tactical_clean": True,
            "ties_baseline": False,
        }
    ) == "high"
    assert _classify_incremental_backlog_priority(
        {
            "beats_baseline": True,
            "improves_profitability": True,
            "protects_fragility": True,
            "tactical_clean": False,
            "ties_baseline": False,
        }
    ) == "medium"


def test_build_incremental_history_headline_includes_active_suffixes():
    headline = _build_incremental_history_headline(
        "pending",
        {"total": 7, "pending": 3},
        2,
        priority_filter="high",
        deferred_fit_filter="reactivable",
        future_purchase_source_filter="backlog_nuevo",
        sort_mode="priority",
    )

    assert "snapshots con decision pendiente" in headline
    assert "Prioridad: Alta" in headline
    assert "Diferidas: Diferidas reactivables" in headline
    assert "Fuente: Backlog nuevo" in headline


def test_build_incremental_decision_executive_headline_prioritizes_backlog_review_copy():
    headline = _build_incremental_decision_executive_headline(
        "review_backlog",
        {"label": "Amarillo"},
        {"headline": "followup"},
        {"headline": "checklist"},
        {"headline": "backlog primero"},
    )

    assert headline == "backlog primero"
