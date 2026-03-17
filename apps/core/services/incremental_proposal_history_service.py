from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import AnonymousUser

from apps.core.models import IncrementalProposalSnapshot


class IncrementalProposalHistoryService:
    """Persistencia liviana de propuestas incrementales guardadas desde Planeacion."""

    MAX_SNAPSHOTS_PER_USER = 10

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

    def list_recent(self, *, user, limit: int = 5) -> list[dict]:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return []
        queryset = IncrementalProposalSnapshot.objects.filter(user=user).order_by("-created_at", "-id")[: max(int(limit), 0)]
        return [self.serialize(item) for item in queryset]

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
