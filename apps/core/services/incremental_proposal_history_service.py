from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.core.models import IncrementalProposalSnapshot


class IncrementalProposalHistoryService:
    """Persistencia liviana de propuestas incrementales guardadas desde Planeacion."""

    MAX_SNAPSHOTS_PER_USER = 10
    MANUAL_DECISION_STATUSES = {"accepted", "deferred", "rejected"}
    HISTORY_FILTER_STATUSES = {"pending", "accepted", "deferred", "rejected"}

    def save_preferred_proposal(
        self,
        *,
        user,
        preferred_payload: dict | None,
        explanation: str = "",
        capital_amount: int | float | Decimal = 0,
    ) -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        payload = preferred_payload or {}
        purchase_plan = self._normalize_purchase_plan(payload.get("purchase_plan") or [])
        if not purchase_plan:
            raise ValueError("empty_purchase_plan")

        snapshot = IncrementalProposalSnapshot.objects.create(
            user=user,
            source_key=str(payload.get("source_key") or ""),
            source_label=str(payload.get("source_label") or ""),
            proposal_key=str(payload.get("proposal_key") or ""),
            proposal_label=str(payload.get("proposal_label") or ""),
            selected_context=str(payload.get("selected_context") or ""),
            capital_amount=self._coerce_decimal(capital_amount),
            comparison_score=self._coerce_optional_decimal(payload.get("comparison_score")),
            purchase_plan=purchase_plan,
            simulation_delta=dict((payload.get("simulation") or {}).get("delta") or {}),
            simulation_interpretation=str((payload.get("simulation") or {}).get("interpretation") or ""),
            explanation=str(explanation or ""),
        )
        self._prune_user_history(user_id=user.pk)
        return self.serialize(snapshot)

    def list_recent(self, *, user, limit: int = 5, decision_status: str | None = None) -> list[dict]:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return []
        queryset = IncrementalProposalSnapshot.objects.filter(user=user)
        normalized_status = str(decision_status or "").strip().lower()
        if normalized_status in self.HISTORY_FILTER_STATUSES:
            queryset = queryset.filter(manual_decision_status=normalized_status)
        queryset = queryset.order_by("-created_at", "-id")[: max(int(limit), 0)]
        return [self.serialize(item) for item in queryset]

    def get_decision_counts(self, *, user) -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return {"total": 0, "pending": 0, "accepted": 0, "deferred": 0, "rejected": 0}

        queryset = IncrementalProposalSnapshot.objects.filter(user=user)
        return {
            "total": queryset.count(),
            "pending": queryset.filter(manual_decision_status="pending").count(),
            "accepted": queryset.filter(manual_decision_status="accepted").count(),
            "deferred": queryset.filter(manual_decision_status="deferred").count(),
            "rejected": queryset.filter(manual_decision_status="rejected").count(),
        }

    def promote_to_tracking_baseline(self, *, user, snapshot_id: int | str) -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        snapshot = IncrementalProposalSnapshot.objects.filter(user=user, pk=snapshot_id).first()
        if snapshot is None:
            raise ValueError("snapshot_not_found")

        IncrementalProposalSnapshot.objects.filter(user=user, is_tracking_baseline=True).exclude(pk=snapshot.pk).update(
            is_tracking_baseline=False
        )
        if not snapshot.is_tracking_baseline:
            snapshot.is_tracking_baseline = True
            snapshot.save(update_fields=["is_tracking_baseline"])
        return self.serialize(snapshot)

    def get_tracking_baseline(self, *, user) -> dict | None:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return None
        snapshot = (
            IncrementalProposalSnapshot.objects.filter(user=user, is_tracking_baseline=True)
            .order_by("-created_at", "-id")
            .first()
        )
        if snapshot is None:
            return None
        return self.serialize(snapshot)

    def decide_snapshot(self, *, user, snapshot_id: int | str, decision_status: str, note: str = "") -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        normalized_status = str(decision_status or "").strip().lower()
        if normalized_status not in self.MANUAL_DECISION_STATUSES:
            raise ValueError("invalid_decision_status")

        snapshot = IncrementalProposalSnapshot.objects.filter(user=user, pk=snapshot_id).first()
        if snapshot is None:
            raise ValueError("snapshot_not_found")

        snapshot.manual_decision_status = normalized_status
        snapshot.manual_decision_note = str(note or "").strip()[:240]
        snapshot.manual_decided_at = timezone.now()
        snapshot.save(update_fields=["manual_decision_status", "manual_decision_note", "manual_decided_at"])
        return self.serialize(snapshot)

    def get_latest_manual_decision(self, *, user) -> dict | None:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return None
        snapshot = (
            IncrementalProposalSnapshot.objects.filter(user=user)
            .exclude(manual_decision_status="pending")
            .order_by("-manual_decided_at", "-id")
            .first()
        )
        if snapshot is None:
            return None
        return self.serialize(snapshot)

    def serialize(self, snapshot: IncrementalProposalSnapshot) -> dict:
        return {
            "id": snapshot.pk,
            "source_key": snapshot.source_key,
            "source_label": snapshot.source_label,
            "proposal_key": snapshot.proposal_key,
            "proposal_label": snapshot.proposal_label,
            "selected_context": snapshot.selected_context,
            "capital_amount": float(snapshot.capital_amount),
            "comparison_score": float(snapshot.comparison_score) if snapshot.comparison_score is not None else None,
            "purchase_plan": list(snapshot.purchase_plan or []),
            "simulation_delta": dict(snapshot.simulation_delta or {}),
            "simulation_interpretation": snapshot.simulation_interpretation,
            "explanation": snapshot.explanation,
            "is_tracking_baseline": bool(snapshot.is_tracking_baseline),
            "manual_decision_status": snapshot.manual_decision_status,
            "manual_decision_note": snapshot.manual_decision_note,
            "manual_decided_at": snapshot.manual_decided_at,
            "created_at": snapshot.created_at,
        }

    def _prune_user_history(self, *, user_id: int) -> None:
        stale_ids = list(
            IncrementalProposalSnapshot.objects.filter(user_id=user_id)
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)[self.MAX_SNAPSHOTS_PER_USER :]
        )
        if stale_ids:
            IncrementalProposalSnapshot.objects.filter(id__in=stale_ids).delete()

    def _normalize_purchase_plan(self, purchase_plan: list[dict]) -> list[dict]:
        normalized = []
        for item in purchase_plan:
            symbol = str(item.get("symbol") or "").strip().upper()
            amount = self._coerce_decimal(item.get("amount"))
            if not symbol or amount <= 0:
                continue
            normalized.append({"symbol": symbol, "amount": float(amount)})
        return normalized

    def _coerce_decimal(self, value) -> Decimal:
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0.00")

    def _coerce_optional_decimal(self, value) -> Decimal | None:
        try:
            return Decimal(str(value)).quantize(Decimal("0.0001"))
        except (InvalidOperation, ValueError, TypeError):
            return None
