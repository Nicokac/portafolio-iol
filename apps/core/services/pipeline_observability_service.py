from __future__ import annotations

from datetime import date

from apps.core.services.analytics_v2 import CovarianceAwareRiskContributionService
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.data_quality.historical_coverage_health import HistoricalCoverageHealthService
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService


class PipelineObservabilityService:
    """Consolida métricas operativas del pipeline de datos para Ops."""

    def __init__(
        self,
        sync_audit_service: IOLSyncAuditService | None = None,
        coverage_health_service: HistoricalCoverageHealthService | None = None,
        snapshot_integrity_service: SnapshotIntegrityService | None = None,
        benchmark_service: BenchmarkSeriesService | None = None,
        local_macro_service: LocalMacroSeriesService | None = None,
    ):
        self.sync_audit_service = sync_audit_service or IOLSyncAuditService()
        self.coverage_health_service = coverage_health_service or HistoricalCoverageHealthService()
        self.snapshot_integrity_service = snapshot_integrity_service or SnapshotIntegrityService()
        self.benchmark_service = benchmark_service or BenchmarkSeriesService()
        self.local_macro_service = local_macro_service or LocalMacroSeriesService()

    def build_summary(self, lookback_days: int = 30, integrity_days: int = 120) -> dict:
        sync_audit = self.sync_audit_service.run_audit(freshness_hours=24)
        coverage = self.coverage_health_service.build_summary(lookback_days=lookback_days)
        snapshot_integrity = self.snapshot_integrity_service.run_checks(days=integrity_days)
        benchmark_status_rows = self.benchmark_service.get_status_summary()
        local_macro_status_rows = self.local_macro_service.get_status_summary()

        latest_portfolio_snapshot_date = coverage.get("latest_portfolio_snapshot_date")
        days_since_last_portfolio_snapshot = None
        if latest_portfolio_snapshot_date:
            days_since_last_portfolio_snapshot = (
                date.today() - date.fromisoformat(latest_portfolio_snapshot_date)
            ).days

        latest_successful_iol_sync = None
        snapshots_info = sync_audit.get("snapshots", {})
        if snapshots_info.get("status") == "ok" and snapshots_info.get("latest_sync") is not None:
            latest_sync = snapshots_info["latest_sync"]
            latest_successful_iol_sync = (
                latest_sync.isoformat() if hasattr(latest_sync, "isoformat") else str(latest_sync)
            )

        usable_observations_count = int(coverage.get("usable_observations_count") or 0)
        available_price_dates_count = int(coverage.get("available_price_dates_count") or 0)

        return {
            "last_successful_iol_sync": latest_successful_iol_sync,
            "iol_sync_status": sync_audit.get("status"),
            "latest_asset_snapshot_at": coverage.get("latest_asset_snapshot_at"),
            "latest_account_snapshot_at": coverage.get("latest_account_snapshot_at"),
            "latest_portfolio_snapshot_date": latest_portfolio_snapshot_date,
            "days_since_last_portfolio_snapshot": days_since_last_portfolio_snapshot,
            "covariance_readiness": self._build_covariance_readiness(
                usable_observations_count=usable_observations_count,
            ),
            "usable_observations_count": usable_observations_count,
            "available_price_dates_count": available_price_dates_count,
            "benchmark_status_summary": self._build_benchmark_status_summary(benchmark_status_rows),
            "local_macro_status_summary": self._build_local_macro_status_summary(local_macro_status_rows),
            "snapshot_integrity_issues_count": int(snapshot_integrity.get("issues_count") or 0),
            "required_periodic_tasks": coverage.get("required_periodic_tasks", []),
            "benchmark_status_rows": benchmark_status_rows,
            "local_macro_status_rows": local_macro_status_rows,
        }

    @staticmethod
    def _build_covariance_readiness(*, usable_observations_count: int) -> dict:
        minimum = CovarianceAwareRiskContributionService.MIN_RETURN_OBSERVATIONS
        if usable_observations_count >= minimum:
            status = "ready"
            label = "Listo para covarianza"
        elif usable_observations_count > 0:
            status = "partial"
            label = "Historia parcial"
        else:
            status = "missing"
            label = "Sin historia util"
        return {
            "status": status,
            "label": label,
            "minimum_required": minimum,
        }

    @staticmethod
    def _build_benchmark_status_summary(rows: list[dict]) -> dict:
        total = len(rows)
        ready_count = sum(1 for row in rows if row.get("is_ready"))
        if total == 0:
            overall_status = "missing"
        elif ready_count == total:
            overall_status = "ready"
        elif ready_count > 0:
            overall_status = "partial"
        else:
            overall_status = "missing"
        return {
            "total_series": total,
            "ready_count": ready_count,
            "missing_count": max(total - ready_count, 0),
            "overall_status": overall_status,
        }

    @staticmethod
    def _build_local_macro_status_summary(rows: list[dict]) -> dict:
        counts = {
            "ready": sum(1 for row in rows if row.get("status") == "ready"),
            "stale": sum(1 for row in rows if row.get("status") == "stale"),
            "missing": sum(1 for row in rows if row.get("status") == "missing"),
            "not_configured": sum(1 for row in rows if row.get("status") == "not_configured"),
        }
        if counts["missing"] or counts["stale"]:
            overall_status = "warning"
        elif counts["not_configured"]:
            overall_status = "partial"
        else:
            overall_status = "ready" if rows else "missing"
        return {
            "total_series": len(rows),
            **counts,
            "overall_status": overall_status,
        }
