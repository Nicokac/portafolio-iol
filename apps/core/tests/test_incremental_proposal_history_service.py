import pytest
from django.contrib.auth.models import AnonymousUser, User

from apps.core.models import IncrementalProposalSnapshot
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService


@pytest.mark.django_db
def test_save_preferred_proposal_persists_snapshot():
    user = User.objects.create_user(username="history-user", password="testpass123")
    service = IncrementalProposalHistoryService()

    saved = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan manual A",
            "selected_context": "Plan manual enviado por el usuario",
            "comparison_score": 4.5,
            "purchase_plan": [{"symbol": "ko", "amount": 200000}, {"symbol": "mcd", "amount": 200000}],
            "simulation": {
                "delta": {"expected_return_change": 0.12, "fragility_change": -0.3},
                "interpretation": "Mejora el balance defensivo.",
            },
        },
        explanation="Sintesis preferida.",
        capital_amount=600000,
    )

    snapshot = IncrementalProposalSnapshot.objects.get()
    assert saved["proposal_label"] == "Plan manual A"
    assert saved["label"] == "Plan manual A"
    assert snapshot.user == user
    assert snapshot.purchase_plan[0]["symbol"] == "KO"
    assert float(snapshot.capital_amount) == 600000.0
    assert snapshot.simulation_delta["fragility_change"] == -0.3
    assert saved["purchase_summary"] == "KO (200000.0), MCD (200000.0)"
    assert saved["simulation"]["delta"]["fragility_change"] == -0.3
    assert saved["simulation"]["interpretation"] == "Mejora el balance defensivo."


@pytest.mark.django_db
def test_save_preferred_proposal_prunes_old_history():
    user = User.objects.create_user(username="history-prune", password="testpass123")
    service = IncrementalProposalHistoryService()

    for index in range(12):
        service.save_preferred_proposal(
            user=user,
            preferred_payload={
                "source_key": "automatic_variants",
                "source_label": "Comparador automatico",
                "proposal_key": f"plan_{index}",
                "proposal_label": f"Plan {index}",
                "purchase_plan": [{"symbol": "SPY", "amount": 100000}],
                "simulation": {"delta": {}, "interpretation": ""},
            },
            capital_amount=100000,
        )

    labels = list(
        IncrementalProposalSnapshot.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("proposal_label", flat=True)
    )
    assert len(labels) == service.MAX_SNAPSHOTS_PER_USER
    assert "Plan 11" in labels
    assert "Plan 1" not in labels


@pytest.mark.django_db
def test_list_recent_returns_empty_for_anonymous_user():
    service = IncrementalProposalHistoryService()

    assert service.list_recent(user=AnonymousUser(), limit=5) == []


@pytest.mark.django_db
def test_serialize_exposes_common_incremental_contract():
    user = User.objects.create_user(username="history-contract", password="testpass123")
    snapshot = IncrementalProposalSnapshot.objects.create(
        user=user,
        source_key="manual_plan",
        source_label="Comparador manual",
        proposal_key="plan_a",
        proposal_label="Plan manual A",
        selected_context="Plan manual enviado por el usuario",
        capital_amount="600000.00",
        comparison_score="4.5000",
        purchase_plan=[{"symbol": "KO", "amount": 200000.0}, {"symbol": "MCD", "amount": 200000.0}],
        simulation_delta={"expected_return_change": 0.12, "fragility_change": -0.3},
        simulation_interpretation="Mejora el balance defensivo.",
    )

    serialized = IncrementalProposalHistoryService().serialize(snapshot)

    assert serialized["proposal_label"] == "Plan manual A"
    assert serialized["label"] == "Plan manual A"
    assert serialized["purchase_summary"] == "KO (200000.0), MCD (200000.0)"
    assert serialized["simulation"]["delta"]["expected_return_change"] == 0.12
    assert serialized["simulation"]["interpretation"] == "Mejora el balance defensivo."
    assert serialized["simulation_delta"]["fragility_change"] == -0.3


def test_normalize_serialized_snapshot_adds_common_aliases():
    service = IncrementalProposalHistoryService()

    normalized = service.normalize_serialized_snapshot(
        {
            "proposal_label": "Plan manual A",
            "purchase_plan": [{"symbol": "ko", "amount": 200000}, {"symbol": "mcd", "amount": 200000}],
            "simulation_delta": {"expected_return_change": 0.12},
        }
    )

    assert normalized["proposal_label"] == "Plan manual A"
    assert normalized["label"] == "Plan manual A"
    assert normalized["purchase_summary"] == "ko (200000), mcd (200000)"
    assert normalized["simulation"]["delta"]["expected_return_change"] == 0.12
    assert normalized["simulation"]["interpretation"] == ""


@pytest.mark.django_db
def test_save_preferred_proposal_rejects_empty_purchase_plan():
    user = User.objects.create_user(username="history-empty", password="testpass123")
    service = IncrementalProposalHistoryService()

    with pytest.raises(ValueError):
        service.save_preferred_proposal(
            user=user,
            preferred_payload={"proposal_label": "Sin compra", "purchase_plan": []},
            capital_amount=0,
        )


@pytest.mark.django_db
def test_promote_to_tracking_baseline_sets_unique_active_snapshot():
    user = User.objects.create_user(username="history-baseline", password="testpass123")
    service = IncrementalProposalHistoryService()

    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    promoted = service.promote_to_tracking_baseline(user=user, snapshot_id=first["id"])
    assert promoted["is_tracking_baseline"] is True

    promoted = service.promote_to_tracking_baseline(user=user, snapshot_id=second["id"])
    assert promoted["proposal_label"] == "Plan B"
    assert service.get_tracking_baseline(user=user)["proposal_label"] == "Plan B"

    flags = list(
        IncrementalProposalSnapshot.objects.filter(user=user).order_by("id").values_list("proposal_label", "is_tracking_baseline")
    )
    assert flags == [("Plan A", False), ("Plan B", True)]


@pytest.mark.django_db
def test_promote_to_backlog_front_sets_unique_pending_snapshot():
    user = User.objects.create_user(username="history-front", password="testpass123")
    service = IncrementalProposalHistoryService()

    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    promoted = service.promote_to_backlog_front(user=user, snapshot_id=first["id"])
    assert promoted["is_backlog_front"] is True

    promoted = service.promote_to_backlog_front(user=user, snapshot_id=second["id"])
    assert promoted["proposal_label"] == "Plan B"
    assert service.get_backlog_front(user=user)["proposal_label"] == "Plan B"

    flags = list(
        IncrementalProposalSnapshot.objects.filter(user=user).order_by("id").values_list("proposal_label", "is_backlog_front")
    )
    assert flags == [("Plan A", False), ("Plan B", True)]


@pytest.mark.django_db
def test_promote_to_backlog_front_rejects_non_pending_snapshot():
    user = User.objects.create_user(username="history-front-reject", password="testpass123")
    service = IncrementalProposalHistoryService()
    saved = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    service.decide_snapshot(user=user, snapshot_id=saved["id"], decision_status="accepted")

    with pytest.raises(ValueError):
        service.promote_to_backlog_front(user=user, snapshot_id=saved["id"])


@pytest.mark.django_db
def test_decide_snapshot_persists_manual_decision():
    user = User.objects.create_user(username="history-decision", password="testpass123")
    service = IncrementalProposalHistoryService()
    saved = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    decided = service.decide_snapshot(user=user, snapshot_id=saved["id"], decision_status="accepted", note="Lista para ejecutar")

    snapshot = IncrementalProposalSnapshot.objects.get(pk=saved["id"])
    assert decided["manual_decision_status"] == "accepted"
    assert decided["manual_decision_note"] == "Lista para ejecutar"
    assert snapshot.manual_decision_status == "accepted"
    assert snapshot.manual_decision_note == "Lista para ejecutar"
    assert snapshot.manual_decided_at is not None
    assert snapshot.is_backlog_front is False


@pytest.mark.django_db
def test_get_latest_manual_decision_returns_last_decided_snapshot():
    user = User.objects.create_user(username="history-decision-latest", password="testpass123")
    service = IncrementalProposalHistoryService()
    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "automatic_variants",
            "source_label": "Comparador automatico",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "automatic_variants",
            "source_label": "Comparador automatico",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    service.decide_snapshot(user=user, snapshot_id=first["id"], decision_status="deferred")
    service.decide_snapshot(user=user, snapshot_id=second["id"], decision_status="accepted")

    latest = service.get_latest_manual_decision(user=user)

    assert latest["proposal_label"] == "Plan B"
    assert latest["manual_decision_status"] == "accepted"


@pytest.mark.django_db
def test_list_recent_can_filter_by_manual_decision_status():
    user = User.objects.create_user(username="history-filter", password="testpass123")
    service = IncrementalProposalHistoryService()
    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    service.decide_snapshot(user=user, snapshot_id=first["id"], decision_status="accepted")

    pending_items = service.list_recent(user=user, limit=10, decision_status="pending")
    accepted_items = service.list_recent(user=user, limit=10, decision_status="accepted")

    assert [item["proposal_label"] for item in pending_items] == ["Plan B"]
    assert [item["proposal_label"] for item in accepted_items] == ["Plan A"]


@pytest.mark.django_db
def test_get_decision_counts_returns_operational_summary():
    user = User.objects.create_user(username="history-counts", password="testpass123")
    service = IncrementalProposalHistoryService()
    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    third = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_c",
            "proposal_label": "Plan C",
            "purchase_plan": [{"symbol": "XLU", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )

    service.decide_snapshot(user=user, snapshot_id=first["id"], decision_status="accepted")
    service.decide_snapshot(user=user, snapshot_id=second["id"], decision_status="deferred")
    service.decide_snapshot(user=user, snapshot_id=third["id"], decision_status="rejected")

    counts = service.get_decision_counts(user=user)

    assert counts == {
        "total": 3,
        "pending": 0,
        "accepted": 1,
        "deferred": 1,
        "rejected": 1,
    }


@pytest.mark.django_db
def test_decide_many_snapshots_updates_visible_selection():
    user = User.objects.create_user(username="history-bulk", password="testpass123")
    service = IncrementalProposalHistoryService()
    first = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_a",
            "proposal_label": "Plan A",
            "purchase_plan": [{"symbol": "KO", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    second = service.save_preferred_proposal(
        user=user,
        preferred_payload={
            "source_key": "manual_plan",
            "source_label": "Comparador manual",
            "proposal_key": "plan_b",
            "proposal_label": "Plan B",
            "purchase_plan": [{"symbol": "MCD", "amount": 100000}],
            "simulation": {"delta": {}, "interpretation": ""},
        },
        capital_amount=100000,
    )
    service.promote_to_backlog_front(user=user, snapshot_id=first["id"])

    result = service.decide_many_snapshots(
        user=user,
        snapshot_ids=[first["id"], second["id"]],
        decision_status="deferred",
    )

    assert result["updated_count"] == 2
    statuses = list(
        IncrementalProposalSnapshot.objects.filter(user=user).order_by("id").values_list("manual_decision_status", flat=True)
    )
    assert statuses == ["deferred", "deferred"]
    assert service.get_backlog_front(user=user) is None


@pytest.mark.django_db
def test_decide_many_snapshots_rejects_empty_selection():
    user = User.objects.create_user(username="history-bulk-empty", password="testpass123")
    service = IncrementalProposalHistoryService()

    with pytest.raises(ValueError):
        service.decide_many_snapshots(user=user, snapshot_ids=[], decision_status="accepted")
