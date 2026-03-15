from __future__ import annotations

from collections import Counter

from apps.core.services.data_quality.snapshot_history_audit import SnapshotHistoryAuditService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class DailySnapshotContinuityService:
    """Resume continuidad diaria de snapshots crudos, cuentas y snapshot consolidado."""

    def __init__(self, audit_service: SnapshotHistoryAuditService | None = None):
        self.audit_service = audit_service or SnapshotHistoryAuditService()

    def build_report(self, lookback_days: int = 14) -> dict:
        audit = self.audit_service.audit_current_invested_history(lookback_days=lookback_days)
        rows = audit.get("rows", [])

        asset_days = Counter(
            dt.date().isoformat()
            for dt in ActivoPortafolioSnapshot.objects.values_list("fecha_extraccion", flat=True)
            if dt is not None
        )
        account_days = Counter(
            dt.date().isoformat()
            for dt in ResumenCuentaSnapshot.objects.values_list("fecha_extraccion", flat=True)
            if dt is not None
        )
        portfolio_days = {
            day.isoformat()
            for day in PortfolioSnapshot.objects.values_list("fecha", flat=True)
            if day is not None
        }

        continuity_rows = []
        for row in rows:
            raw_present = bool(row.get("assets_present"))
            account_present = account_days.get(row["date"], 0) > 0
            portfolio_present = row["date"] in portfolio_days
            usable = bool(row.get("usable"))

            if raw_present and account_present and portfolio_present and usable:
                status = "healthy"
            elif raw_present or account_present or portfolio_present:
                status = "warning"
            else:
                status = "broken"

            continuity_rows.append(
                {
                    "date": row["date"],
                    "raw_snapshots_present": raw_present,
                    "raw_assets_count": int(row.get("assets_present", 0)),
                    "account_snapshot_present": account_present,
                    "account_rows_count": int(account_days.get(row["date"], 0)),
                    "portfolio_snapshot_present": portfolio_present,
                    "usable_for_covariance": usable,
                    "status": status,
                }
            )

        overall_status = self._derive_overall_status(continuity_rows)

        return {
            "lookback_days": lookback_days,
            "expected_symbols_count": audit.get("expected_symbols_count", 0),
            "usable_observations_count": audit.get("usable_observations_count", 0),
            "rows": continuity_rows,
            "overall_status": overall_status,
            "status_counts": {
                "healthy": sum(1 for row in continuity_rows if row["status"] == "healthy"),
                "warning": sum(1 for row in continuity_rows if row["status"] == "warning"),
                "broken": sum(1 for row in continuity_rows if row["status"] == "broken"),
            },
        }

    @staticmethod
    def _derive_overall_status(rows: list[dict]) -> str:
        if not rows:
            return "broken"

        latest = rows[-1]
        if not (
            latest.get("raw_snapshots_present")
            and latest.get("account_snapshot_present")
            and latest.get("portfolio_snapshot_present")
        ):
            return "broken"

        if latest.get("usable_for_covariance") and latest.get("status") == "healthy":
            return "healthy"

        return "warning"
