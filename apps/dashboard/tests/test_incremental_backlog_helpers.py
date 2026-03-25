from unittest.mock import MagicMock, patch

from apps.dashboard.incremental_backlog import (
    get_incremental_backlog_front_summary,
    get_incremental_backlog_operational_semaphore,
    get_incremental_decision_executive_summary,
    get_incremental_followup_executive_summary,
    get_incremental_adoption_checklist,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

_FAKE_USER = object()


def _baseline(label="baseline_a"):
    return {"proposal_label": label, "is_backlog_front": False}


def _front_item(priority="low", is_backlog_front=False):
    return {
        "priority": priority,
        "snapshot": {"is_backlog_front": is_backlog_front},
    }


# ---------------------------------------------------------------------------
# get_incremental_backlog_front_summary – rama de status
# ---------------------------------------------------------------------------

def _patch_front_summary_deps(baseline_item=None, top_item=None):
    return patch.multiple(
        "apps.dashboard.incremental_backlog",
        get_incremental_proposal_tracking_baseline=MagicMock(return_value={"item": baseline_item}),
        get_incremental_backlog_prioritization=MagicMock(return_value={"top_item": top_item, "counts": {}}),
        _build_incremental_backlog_front_summary_headline=MagicMock(return_value=""),
        _build_incremental_backlog_front_summary_items=MagicMock(return_value=[]),
    )


def test_front_summary_status_empty():
    with _patch_front_summary_deps(baseline_item=None, top_item=None):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "empty"


def test_front_summary_status_no_baseline():
    with _patch_front_summary_deps(baseline_item=None, top_item=_front_item()):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "no_baseline"


def test_front_summary_status_baseline_only():
    with _patch_front_summary_deps(baseline_item=_baseline(), top_item=None):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "baseline_only"


def test_front_summary_status_manual_front():
    with _patch_front_summary_deps(baseline_item=_baseline(), top_item=_front_item(is_backlog_front=True)):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "manual_front"


def test_front_summary_status_candidate_over_baseline():
    with _patch_front_summary_deps(baseline_item=_baseline(), top_item=_front_item(priority="high")):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "candidate_over_baseline"


def test_front_summary_status_watch():
    with _patch_front_summary_deps(baseline_item=_baseline(), top_item=_front_item(priority="medium")):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "watch"


def test_front_summary_status_baseline_holds():
    with _patch_front_summary_deps(baseline_item=_baseline(), top_item=_front_item(priority="low")):
        result = get_incremental_backlog_front_summary(user=_FAKE_USER)
    assert result["status"] == "baseline_holds"


# ---------------------------------------------------------------------------
# get_incremental_backlog_operational_semaphore – rama de status
# ---------------------------------------------------------------------------

def _patch_semaphore_deps(drift_status="unavailable", front_status="empty", high_count=0):
    return patch.multiple(
        "apps.dashboard.incremental_backlog",
        get_incremental_baseline_drift=MagicMock(return_value={"summary": {"status": drift_status}, "has_baseline": True}),
        get_incremental_backlog_front_summary=MagicMock(return_value={"status": front_status, "has_summary": True}),
        get_incremental_backlog_prioritization=MagicMock(return_value={"counts": {"high": high_count}}),
        _format_incremental_operational_semaphore=MagicMock(return_value=""),
        _build_incremental_operational_semaphore_headline=MagicMock(return_value=""),
        _build_incremental_operational_semaphore_items=MagicMock(return_value=[]),
    )


def test_semaphore_status_red_cuando_drift_unfavorable():
    with _patch_semaphore_deps(drift_status="unfavorable", front_status="baseline_only", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "red"


def test_semaphore_status_yellow_candidate_over_baseline():
    with _patch_semaphore_deps(drift_status="stable", front_status="candidate_over_baseline", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "yellow"


def test_semaphore_status_yellow_high_count():
    with _patch_semaphore_deps(drift_status="stable", front_status="baseline_holds", high_count=2):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "yellow"


def test_semaphore_status_yellow_manual_front():
    with _patch_semaphore_deps(drift_status="stable", front_status="manual_front", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "yellow"


def test_semaphore_status_green():
    with _patch_semaphore_deps(drift_status="favorable", front_status="baseline_only", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "green"


def test_semaphore_status_green_stable_empty():
    with _patch_semaphore_deps(drift_status="stable", front_status="empty", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "green"


def test_semaphore_status_gray_sin_sennal():
    with _patch_semaphore_deps(drift_status="unavailable", front_status="no_baseline", high_count=0):
        result = get_incremental_backlog_operational_semaphore({}, user=_FAKE_USER)
    assert result["status"] == "gray"


# ---------------------------------------------------------------------------
# get_incremental_followup_executive_summary – rama de status
# ---------------------------------------------------------------------------

def _patch_followup_deps(preferred=None, baseline_item=None, drift_status="unavailable"):
    return patch.multiple(
        "apps.dashboard.incremental_backlog",
        get_preferred_incremental_portfolio_proposal=MagicMock(return_value={"preferred": preferred}),
        get_incremental_proposal_tracking_baseline=MagicMock(return_value={"item": baseline_item}),
        get_incremental_baseline_drift=MagicMock(return_value={"summary": {"status": drift_status}, "has_baseline": True}),
        _build_incremental_followup_headline=MagicMock(return_value=""),
        _build_incremental_followup_summary_items=MagicMock(return_value=[]),
    )


_PREFERRED = {"proposal_label": "Plan A", "purchase_plan": []}


def test_followup_status_pending_sin_preferred():
    with _patch_followup_deps(preferred=None, baseline_item=_baseline()):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "pending"


def test_followup_status_no_baseline():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=None, drift_status="stable"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "no_baseline"


def test_followup_status_review_drift_unfavorable():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=_baseline(), drift_status="unfavorable"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "review"


def test_followup_status_watch_drift_mixed():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=_baseline(), drift_status="mixed"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "watch"


def test_followup_status_aligned_drift_favorable():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=_baseline(), drift_status="favorable"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "aligned"


def test_followup_status_aligned_drift_stable():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=_baseline(), drift_status="stable"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "aligned"


def test_followup_status_watch_drift_desconocido():
    with _patch_followup_deps(preferred=_PREFERRED, baseline_item=_baseline(), drift_status="unknown"):
        result = get_incremental_followup_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "watch"


# ---------------------------------------------------------------------------
# get_incremental_decision_executive_summary – rama de status
# ---------------------------------------------------------------------------

def _patch_decision_deps(semaphore_status="gray", checklist_status="pending"):
    return patch.multiple(
        "apps.dashboard.incremental_backlog",
        get_incremental_backlog_operational_semaphore=MagicMock(return_value={"status": semaphore_status, "has_signal": True}),
        get_incremental_followup_executive_summary=MagicMock(return_value={"status": "watch", "has_summary": True}),
        get_incremental_adoption_checklist=MagicMock(return_value={"status": checklist_status, "total_count": 5}),
        get_incremental_backlog_front_summary=MagicMock(return_value={"status": "baseline_only", "has_summary": True}),
        _build_incremental_decision_executive_headline=MagicMock(return_value=""),
        _build_incremental_decision_executive_items=MagicMock(return_value=[]),
    )


def test_decision_status_adopt():
    with _patch_decision_deps(semaphore_status="green", checklist_status="ready"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "adopt"


def test_decision_status_hold_semaforo_rojo():
    with _patch_decision_deps(semaphore_status="red", checklist_status="ready"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "hold"


def test_decision_status_review_backlog_semaforo_yellow():
    with _patch_decision_deps(semaphore_status="yellow", checklist_status="pending"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "review_backlog"


def test_decision_status_review_current_checklist_review():
    with _patch_decision_deps(semaphore_status="gray", checklist_status="review"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "review_current"


def test_decision_status_pending_todo_gris():
    with _patch_decision_deps(semaphore_status="gray", checklist_status="pending"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "pending"


def test_decision_status_red_gana_sobre_checklist_ready():
    """semaphore red tiene precedencia incluso si checklist es ready."""
    with _patch_decision_deps(semaphore_status="red", checklist_status="ready"):
        result = get_incremental_decision_executive_summary({}, user=_FAKE_USER)
    assert result["status"] == "hold"


# ---------------------------------------------------------------------------
# get_incremental_adoption_checklist – adoption_ready logic
# ---------------------------------------------------------------------------

def _make_check_item(passed: bool):
    return {"passed": passed, "label": "", "detail": "", "key": "x"}


def _patch_adoption_deps(preferred=None, baseline_item=None, drift_status="unavailable", drift_alerts=None):
    preferred_payload = {"preferred": preferred}
    baseline_payload = {"item": baseline_item}
    drift_payload = {
        "summary": {"status": drift_status},
        "alerts": drift_alerts or [],
        "has_baseline": baseline_item is not None,
    }
    executive_payload = {"status": "watch"}
    return patch.multiple(
        "apps.dashboard.incremental_backlog",
        get_preferred_incremental_portfolio_proposal=MagicMock(return_value=preferred_payload),
        get_incremental_proposal_tracking_baseline=MagicMock(return_value=baseline_payload),
        get_incremental_baseline_drift=MagicMock(return_value=drift_payload),
        get_incremental_followup_executive_summary=MagicMock(return_value=executive_payload),
        _build_incremental_adoption_check_item=MagicMock(side_effect=lambda key, label, passed, detail: {"key": key, "passed": passed, "label": label, "detail": detail}),
        _format_incremental_purchase_plan_summary=MagicMock(return_value=""),
        _summarize_incremental_drift_alerts=MagicMock(return_value=""),
        _format_incremental_followup_status=MagicMock(return_value=""),
        _build_incremental_adoption_checklist_headline=MagicMock(return_value=""),
    )


def test_adoption_checklist_status_pending_sin_preferred():
    with _patch_adoption_deps(preferred=None):
        result = get_incremental_adoption_checklist({}, user=_FAKE_USER)
    assert result["status"] == "pending"
    assert result["adoption_ready"] is False


def test_adoption_checklist_status_ready():
    preferred_item = {"proposal_label": "Plan A", "purchase_plan": [{"symbol": "AAPL", "amount": 100000}]}
    with _patch_adoption_deps(
        preferred=preferred_item,
        baseline_item=_baseline(),
        drift_status="favorable",
        drift_alerts=[],
    ):
        result = get_incremental_adoption_checklist({}, user=_FAKE_USER)
    assert result["status"] == "ready"
    assert result["adoption_ready"] is True


def test_adoption_checklist_status_review_sin_purchase_plan():
    # adoption_ready requiere items[:2] → el check de purchase_plan (items[1]) debe pasar.
    # Sin purchase_plan, items[1].passed=False → adoption_ready=False → "review".
    preferred_item = {"proposal_label": "Plan A", "purchase_plan": []}
    with _patch_adoption_deps(
        preferred=preferred_item,
        baseline_item=_baseline(),
        drift_status="favorable",
        drift_alerts=[],
    ):
        result = get_incremental_adoption_checklist({}, user=_FAKE_USER)
    assert result["status"] == "review"
    assert result["adoption_ready"] is False


def test_adoption_checklist_status_review_drift_unfavorable():
    preferred_item = {"proposal_label": "Plan A", "purchase_plan": [{"symbol": "AAPL", "amount": 100000}]}
    with _patch_adoption_deps(
        preferred=preferred_item,
        baseline_item=_baseline(),
        drift_status="unfavorable",
        drift_alerts=[{"severity": "high"}],
    ):
        result = get_incremental_adoption_checklist({}, user=_FAKE_USER)
    assert result["status"] == "review"
    assert result["adoption_ready"] is False
