from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from apps.dashboard.dashboard_incremental_actions import (
    handle_bulk_decide_incremental_proposal,
    handle_save_preferred_incremental_proposal,
)


def _build_request(path="/dashboard/planeacion/", data=None):
    factory = RequestFactory()
    request = factory.post(path, data=data or {})
    request.session = {}
    setattr(request, "_messages", FallbackStorage(request))
    User = get_user_model()
    request.user = User(username="tester")
    return request


def test_handle_save_preferred_incremental_proposal_redirects_with_source_query():
    captured = {}

    class DummyHistoryService:
        def save_preferred_proposal(self, **kwargs):
            captured.update(kwargs)
            return {"proposal_label": "Plan A", "source_key": "manual_plan"}

    request = _build_request(
        data={"source_query": "decision_status_filter=pending"},
    )
    response = handle_save_preferred_incremental_proposal(
        request=request,
        get_preferred_incremental_portfolio_proposal=lambda query_params, capital_amount=600000: {
            "preferred": {"proposal_label": "Plan A"},
            "explanation": "ok",
        },
        get_decision_engine_summary=lambda user, query_params=None, capital_amount=600000: {"score": 80},
        history_service_factory=DummyHistoryService,
        record_sensitive_action=lambda *args, **kwargs: None,
    )

    assert response.status_code == 302
    assert response.url.endswith("?decision_status_filter=pending#planeacion-aportes")
    assert captured["capital_amount"] == 600000


def test_handle_bulk_decide_incremental_proposal_preserves_filters_in_redirect():
    captured = {}

    class DummyHistoryService:
        def decide_many_snapshots(self, **kwargs):
            captured.update(kwargs)
            return {"decision_status": kwargs["decision_status"], "updated_count": len(kwargs["snapshot_ids"])}

    request = _build_request(
        data={
            "decision_status": "accepted",
            "decision_status_filter": "pending",
            "history_priority_filter": "high",
            "history_deferred_fit_filter": "reactivable",
            "history_future_purchase_source_filter": "backlog_nuevo",
            "history_sort": "priority",
        }
    )
    response = handle_bulk_decide_incremental_proposal(
        request=request,
        history_service_factory=DummyHistoryService,
        get_incremental_proposal_history=lambda **kwargs: {"items": [{"id": 9}]},
        record_sensitive_action=lambda *args, **kwargs: None,
        build_redirect_url=lambda post_data: "/planeacion/?decision_status_filter=pending&history_priority_filter=high&history_deferred_fit_filter=reactivable&history_future_purchase_source_filter=backlog_nuevo&history_sort=priority#planeacion-aportes",
    )

    assert response.status_code == 302
    assert response.url.endswith(
        "?decision_status_filter=pending&history_priority_filter=high&history_deferred_fit_filter=reactivable&history_future_purchase_source_filter=backlog_nuevo&history_sort=priority#planeacion-aportes"
    )
    assert captured["snapshot_ids"] == [9]
