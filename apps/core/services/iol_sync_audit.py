from datetime import timedelta

from django.utils import timezone

from apps.core.models import IOLToken
from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class IOLSyncAuditService:
    """Audita salud e integridad de sincronizacion con IOL."""

    def run_audit(self, freshness_hours: int = 24) -> dict:
        now = timezone.now()
        stale_limit = now - timedelta(hours=freshness_hours)
        issues = []

        token_info = self._audit_token(now)
        if token_info["status"] != "ok":
            issues.append("token")

        snapshots_info = self._audit_snapshots(stale_limit)
        if snapshots_info["status"] != "ok":
            issues.append("snapshots")

        operations_info = self._audit_operations(stale_limit)
        if operations_info["status"] != "ok":
            issues.append("operations")

        sync_status = "ok" if not issues else "warning"
        return {
            "status": sync_status,
            "issues_count": len(issues),
            "issues": issues,
            "token": token_info,
            "snapshots": snapshots_info,
            "operations": operations_info,
            "checked_at": now.isoformat(),
        }

    @staticmethod
    def _audit_token(now):
        latest_token = IOLToken.objects.order_by("-created_at").first()
        if not latest_token:
            return {"status": "warning", "reason": "missing_token"}
        if latest_token.expires_at <= now:
            return {"status": "warning", "reason": "expired_token", "expires_at": latest_token.expires_at}
        return {"status": "ok", "expires_at": latest_token.expires_at}

    @staticmethod
    def _audit_snapshots(stale_limit):
        latest_portfolio = ActivoPortafolioSnapshot.objects.order_by("-fecha_extraccion").first()
        latest_accounts = ResumenCuentaSnapshot.objects.order_by("-fecha_extraccion").first()

        if not latest_portfolio or not latest_accounts:
            return {"status": "warning", "reason": "missing_snapshots"}

        latest_sync = min(latest_portfolio.fecha_extraccion, latest_accounts.fecha_extraccion)
        status = "ok"
        reasons = []

        if latest_sync < stale_limit:
            status = "warning"
            reasons.append("stale_snapshots")

        same_portfolio_timestamp_count = ActivoPortafolioSnapshot.objects.filter(
            fecha_extraccion=latest_portfolio.fecha_extraccion
        ).count()
        same_accounts_timestamp_count = ResumenCuentaSnapshot.objects.filter(
            fecha_extraccion=latest_accounts.fecha_extraccion
        ).count()

        if same_portfolio_timestamp_count == 0 or same_accounts_timestamp_count == 0:
            status = "warning"
            reasons.append("incomplete_snapshots")

        return {
            "status": status,
            "reasons": reasons,
            "latest_sync": latest_sync,
            "portfolio_rows": same_portfolio_timestamp_count,
            "account_rows": same_accounts_timestamp_count,
        }

    @staticmethod
    def _audit_operations(stale_limit):
        latest_operation = OperacionIOL.objects.order_by("-fecha_orden").first()
        if not latest_operation:
            return {"status": "warning", "reason": "missing_operations"}

        # fecha_orden puede venir naive en algunos datos historicos.
        latest_dt = latest_operation.fecha_orden
        if timezone.is_naive(latest_dt):
            latest_dt = timezone.make_aware(latest_dt, timezone.get_current_timezone())

        if latest_dt < stale_limit:
            return {
                "status": "warning",
                "reason": "stale_operations",
                "latest_operation": latest_dt,
            }
        return {"status": "ok", "latest_operation": latest_dt}
