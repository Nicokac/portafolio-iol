from __future__ import annotations

from collections import Counter

from django_celery_beat.models import PeriodicTask

from apps.core.services.data_quality.snapshot_history_audit import SnapshotHistoryAuditService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class HistoricalCoverageHealthService:
    """Resume la salud operativa de la historia util para analytics avanzados."""

    REQUIRED_PERIODIC_TASKS = (
        "core.sync_portfolio_data",
        "core.generate_daily_snapshot",
    )

    def __init__(self, audit_service: SnapshotHistoryAuditService | None = None):
        self.audit_service = audit_service or SnapshotHistoryAuditService()

    def build_summary(self, lookback_days: int = 30) -> dict:
        audit = self.audit_service.audit_current_invested_history(lookback_days=lookback_days)
        rows = audit.get("rows", [])

        latest_asset_ts = ActivoPortafolioSnapshot.objects.order_by("-fecha_extraccion").values_list(
            "fecha_extraccion", flat=True
        ).first()
        latest_account_ts = ResumenCuentaSnapshot.objects.order_by("-fecha_extraccion").values_list(
            "fecha_extraccion", flat=True
        ).first()
        latest_portfolio_snapshot_date = PortfolioSnapshot.objects.order_by("-fecha").values_list(
            "fecha", flat=True
        ).first()

        asset_days = Counter(
            dt.date().isoformat()
            for dt in ActivoPortafolioSnapshot.objects.values_list("fecha_extraccion", flat=True)
            if dt is not None
        )
        portfolio_snapshot_days = {
            day.isoformat()
            for day in PortfolioSnapshot.objects.values_list("fecha", flat=True)
            if day is not None
        }
        recent_days_without_portfolio_snapshot = [
            day
            for day in sorted(asset_days.keys())
            if day not in portfolio_snapshot_days and any(row["date"] == day for row in rows)
        ]

        tasks = {
            row["name"]: row["enabled"]
            for row in PeriodicTask.objects.filter(name__in=self.REQUIRED_PERIODIC_TASKS).values("name", "enabled")
        }

        return {
            "lookback_days": lookback_days,
            "expected_symbols_count": audit.get("expected_symbols_count", 0),
            "available_price_dates_count": audit.get("available_price_dates_count", 0),
            "usable_observations_count": audit.get("usable_observations_count", 0),
            "missing_calendar_dates_count": len(audit.get("missing_calendar_dates", [])),
            "complete_price_dates_count": sum(1 for row in rows if row.get("complete_after_ffill")),
            "asset_days_without_portfolio_snapshot": recent_days_without_portfolio_snapshot,
            "latest_asset_snapshot_at": latest_asset_ts.isoformat() if latest_asset_ts else None,
            "latest_account_snapshot_at": latest_account_ts.isoformat() if latest_account_ts else None,
            "latest_portfolio_snapshot_date": (
                latest_portfolio_snapshot_date.isoformat() if latest_portfolio_snapshot_date else None
            ),
            "required_periodic_tasks": [
                {"name": task_name, "enabled": bool(tasks.get(task_name))}
                for task_name in self.REQUIRED_PERIODIC_TASKS
            ],
        }
