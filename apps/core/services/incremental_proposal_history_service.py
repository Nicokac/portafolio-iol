from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.core.models import IncrementalProposalSnapshot
from apps.core.services.incremental_proposal_contracts import normalize_incremental_proposal_payload


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
        decision_payload: dict | None = None,
        explanation: str = "",
        capital_amount: int | float | Decimal = 0,
    ) -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        payload = preferred_payload or {}
        purchase_plan = self._normalize_purchase_plan(payload.get("purchase_plan") or [])
        if not purchase_plan:
            raise ValueError("empty_purchase_plan")
        normalized_decision = self._normalize_decision_payload(decision_payload)

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
            decision_score=normalized_decision["decision_score"],
            decision_confidence=normalized_decision["decision_confidence"],
            decision_explanation=normalized_decision["decision_explanation"],
            macro_state=normalized_decision["macro_state"],
            portfolio_state=normalized_decision["portfolio_state"],
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

    def promote_to_backlog_front(self, *, user, snapshot_id: int | str) -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        snapshot = IncrementalProposalSnapshot.objects.filter(user=user, pk=snapshot_id).first()
        if snapshot is None:
            raise ValueError("snapshot_not_found")
        if snapshot.manual_decision_status != "pending":
            raise ValueError("snapshot_not_pending")

        IncrementalProposalSnapshot.objects.filter(user=user, is_backlog_front=True).exclude(pk=snapshot.pk).update(
            is_backlog_front=False
        )
        if not snapshot.is_backlog_front:
            snapshot.is_backlog_front = True
            snapshot.save(update_fields=["is_backlog_front"])
        return self.serialize(snapshot)

    def reactivate_snapshot_to_backlog(self, *, user, snapshot_id: int | str, note: str = "") -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        snapshot = IncrementalProposalSnapshot.objects.filter(user=user, pk=snapshot_id).first()
        if snapshot is None:
            raise ValueError("snapshot_not_found")

        snapshot.manual_decision_status = "pending"
        snapshot.manual_decision_note = str(note or "").strip()[:240]
        snapshot.manual_decided_at = timezone.now()
        snapshot.is_backlog_front = False
        snapshot.save(update_fields=["manual_decision_status", "manual_decision_note", "manual_decided_at", "is_backlog_front"])
        return self.promote_to_backlog_front(user=user, snapshot_id=snapshot.pk)

    def get_backlog_front(self, *, user) -> dict | None:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            return None
        snapshot = (
            IncrementalProposalSnapshot.objects.filter(user=user, is_backlog_front=True, manual_decision_status="pending")
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
        if normalized_status != "pending":
            snapshot.is_backlog_front = False
        snapshot.save(update_fields=["manual_decision_status", "manual_decision_note", "manual_decided_at", "is_backlog_front"])
        return self.serialize(snapshot)

    def decide_many_snapshots(self, *, user, snapshot_ids: list[int | str], decision_status: str, note: str = "") -> dict:
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            raise ValueError("authenticated_user_required")

        normalized_status = str(decision_status or "").strip().lower()
        if normalized_status not in self.MANUAL_DECISION_STATUSES:
            raise ValueError("invalid_decision_status")

        normalized_ids = []
        for raw_id in snapshot_ids or []:
            try:
                normalized_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        normalized_ids = list(dict.fromkeys(normalized_ids))
        if not normalized_ids:
            raise ValueError("empty_snapshot_selection")

        queryset = IncrementalProposalSnapshot.objects.filter(user=user, id__in=normalized_ids)
        matched_ids = list(queryset.values_list("id", flat=True))
        if not matched_ids:
            raise ValueError("snapshot_not_found")

        decided_at = timezone.now()
        updated = queryset.update(
            manual_decision_status=normalized_status,
            manual_decision_note=str(note or "").strip()[:240],
            manual_decided_at=decided_at,
            is_backlog_front=False,
        )
        return {
            "updated_count": int(updated),
            "snapshot_ids": matched_ids,
            "decision_status": normalized_status,
            "manual_decision_note": str(note or "").strip()[:240],
            "decided_at": decided_at,
        }

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
        return self.normalize_serialized_snapshot(
            {
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
                "decision_score": snapshot.decision_score,
                "decision_confidence": snapshot.decision_confidence,
                "decision_explanation": list(snapshot.decision_explanation or [])
                if snapshot.decision_explanation is not None
                else None,
                "macro_state": snapshot.macro_state,
                "portfolio_state": snapshot.portfolio_state,
                "is_tracking_baseline": bool(snapshot.is_tracking_baseline),
                "is_backlog_front": bool(snapshot.is_backlog_front),
                "manual_decision_status": snapshot.manual_decision_status,
                "manual_decision_note": snapshot.manual_decision_note,
                "manual_decided_at": snapshot.manual_decided_at,
                "created_at": snapshot.created_at,
            }
        )

    def normalize_serialized_snapshot(self, payload: dict | None) -> dict:
        return normalize_incremental_proposal_payload(payload)

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

    def _normalize_decision_payload(self, decision_payload: dict | None) -> dict:
        payload = dict(decision_payload or {})
        tracking = dict(payload.get("tracking_payload") or {})
        explanation = self._merge_decision_explanation(
            self._coerce_optional_explanation(payload.get("explanation")),
            self._build_governance_explanation_from_tracking(tracking),
        )
        return {
            "decision_score": self._coerce_optional_score(payload.get("score", tracking.get("score"))),
            "decision_confidence": self._coerce_optional_confidence(
                payload.get("confidence", tracking.get("confidence"))
            ),
            "decision_explanation": explanation,
            "macro_state": self._coerce_optional_state(
                payload.get("macro_state", tracking.get("macro_state"))
            ),
            "portfolio_state": self._coerce_optional_state(
                payload.get("portfolio_state", tracking.get("portfolio_state"))
            ),
        }

    def _merge_decision_explanation(self, explicit_items: list[str] | None, governance_items: list[str]) -> list[str] | None:
        merged = []
        for item in list(explicit_items or []) + list(governance_items or []):
            normalized = str(item or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        if not merged:
            return None if explicit_items is None else []
        return merged

    def _build_governance_explanation_from_tracking(self, tracking: dict | None) -> list[str]:
        governance = dict((tracking or {}).get("governance") or {})
        recommendation = dict(governance.get("recommendation") or {})
        preferred = dict(governance.get("preferred_proposal") or {})
        items = []

        if governance.get("parking_signal_active"):
            items.append("Hay parking visible en cartera y la decision quedo bajo revision tactica.")
        if governance.get("market_history_signal_active"):
            items.append("La liquidez reciente observada por IOL pide revisar la ejecucion antes de comprar.")

        if recommendation.get("reprioritized_by_parking"):
            original_label = str(recommendation.get("original_block_label") or "el bloque original").strip()
            items.append(f"La recomendacion principal fue repriorizada por parking visible sobre {original_label}.")
        elif recommendation.get("conditioned_by_parking"):
            items.append("La recomendacion principal quedo condicionada por parking visible en el mismo bloque.")

        if recommendation.get("reprioritized_by_market_history"):
            original_label = str(recommendation.get("original_block_label") or "el bloque original").strip()
            items.append(f"La recomendacion principal fue repriorizada por liquidez reciente debil en {original_label}.")
        elif recommendation.get("conditioned_by_market_history"):
            items.append("La recomendacion principal quedo condicionada por liquidez reciente debil.")

        if preferred.get("reprioritized_by_parking"):
            proposal_label = str(preferred.get("proposal_label") or "la propuesta original").strip()
            items.append(f"La propuesta preferida fue reemplazada por una alternativa mas limpia frente a parking visible sobre {proposal_label}.")
        elif preferred.get("conditioned_by_parking"):
            items.append("La propuesta preferida quedo condicionada por parking visible.")

        if preferred.get("reprioritized_by_market_history"):
            proposal_label = str(preferred.get("proposal_label") or "la propuesta original").strip()
            items.append(f"La propuesta preferida fue reemplazada por una alternativa con liquidez reciente mas limpia frente a {proposal_label}.")
        elif preferred.get("conditioned_by_market_history"):
            items.append("La propuesta preferida quedo condicionada por liquidez reciente debil.")

        return items

    def _coerce_optional_score(self, value) -> int | None:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= score <= 100:
            return score
        return None

    def _coerce_optional_confidence(self, value) -> str | None:
        confidence = str(value or "").strip()
        if confidence in {"Alta", "Media", "Baja"}:
            return confidence
        return None

    def _coerce_optional_explanation(self, value) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            return None
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized

    def _coerce_optional_state(self, value) -> str | None:
        if isinstance(value, dict):
            value = value.get("key") or value.get("label")
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        return normalized[:24]
