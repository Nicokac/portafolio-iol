from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from apps.core.services.pipeline_observability_service import PipelineObservabilityService


def test_pipeline_observability_service_builds_unified_summary():
    class DummySyncAuditService:
        def run_audit(self, freshness_hours=24):
            assert freshness_hours == 24
            return {
                "status": "ok",
                "snapshots": {
                    "status": "ok",
                    "latest_sync": datetime(2026, 3, 17, 13, 0, 0, tzinfo=dt_timezone.utc),
                },
            }

    class DummyCoverageService:
        def build_summary(self, lookback_days=30):
            assert lookback_days == 30
            return {
                "usable_observations_count": 21,
                "available_price_dates_count": 28,
                "latest_asset_snapshot_at": "2026-03-17T13:00:00+00:00",
                "latest_account_snapshot_at": "2026-03-17T13:00:00+00:00",
                "latest_portfolio_snapshot_date": "2026-03-16",
                "required_periodic_tasks": [{"name": "core.sync_portfolio_data", "enabled": True}],
            }

    class DummySnapshotIntegrityService:
        def run_checks(self, days=120):
            assert days == 120
            return {"issues_count": 2}

    class DummyBenchmarkService:
        def get_status_summary(self):
            return [
                {"benchmark_key": "cedear_usa", "is_ready": True},
                {"benchmark_key": "bonos_ar", "is_ready": False},
            ]

    class DummyLocalMacroService:
        def get_status_summary(self):
            return [
                {"series_key": "usdars_oficial", "status": "ready"},
                {"series_key": "usdars_mep", "status": "not_configured"},
                {"series_key": "badlar_privada", "status": "stale"},
            ]

    summary = PipelineObservabilityService(
        sync_audit_service=DummySyncAuditService(),
        coverage_health_service=DummyCoverageService(),
        snapshot_integrity_service=DummySnapshotIntegrityService(),
        benchmark_service=DummyBenchmarkService(),
        local_macro_service=DummyLocalMacroService(),
    ).build_summary(lookback_days=30, integrity_days=120)

    assert summary["last_successful_iol_sync"] == "2026-03-17 10:00"
    assert summary["iol_sync_status"] == "ok"
    assert summary["latest_asset_snapshot_at"] == "2026-03-17 10:00"
    assert summary["latest_account_snapshot_at"] == "2026-03-17 10:00"
    assert summary["latest_portfolio_snapshot_date"] == "2026-03-16"
    assert summary["days_since_last_portfolio_snapshot"] == 1
    assert summary["usable_observations_count"] == 21
    assert summary["available_price_dates_count"] == 28
    assert summary["covariance_readiness"]["status"] == "ready"
    assert summary["benchmark_status_summary"]["ready_count"] == 1
    assert summary["benchmark_status_summary"]["overall_status"] == "partial"
    assert summary["local_macro_status_summary"]["ready"] == 1
    assert summary["local_macro_status_summary"]["stale"] == 1
    assert summary["local_macro_status_summary"]["not_configured"] == 1
    assert summary["local_macro_status_summary"]["overall_status"] == "warning"
    assert summary["snapshot_integrity_issues_count"] == 2


def test_pipeline_observability_service_handles_missing_sync_and_history():
    class DummySyncAuditService:
        def run_audit(self, freshness_hours=24):
            return {"status": "warning", "snapshots": {"status": "warning", "latest_sync": None}}

    class DummyCoverageService:
        def build_summary(self, lookback_days=30):
            return {
                "usable_observations_count": 0,
                "available_price_dates_count": 0,
                "latest_asset_snapshot_at": None,
                "latest_account_snapshot_at": None,
                "latest_portfolio_snapshot_date": None,
                "required_periodic_tasks": [],
            }

    class DummySnapshotIntegrityService:
        def run_checks(self, days=120):
            return {"issues_count": 0}

    class DummyBenchmarkService:
        def get_status_summary(self):
            return []

    class DummyLocalMacroService:
        def get_status_summary(self):
            return []

    summary = PipelineObservabilityService(
        sync_audit_service=DummySyncAuditService(),
        coverage_health_service=DummyCoverageService(),
        snapshot_integrity_service=DummySnapshotIntegrityService(),
        benchmark_service=DummyBenchmarkService(),
        local_macro_service=DummyLocalMacroService(),
    ).build_summary()

    assert summary["last_successful_iol_sync"] is None
    assert summary["days_since_last_portfolio_snapshot"] is None
    assert summary["covariance_readiness"]["status"] == "missing"
    assert summary["benchmark_status_summary"]["overall_status"] == "missing"
    assert summary["local_macro_status_summary"]["overall_status"] == "missing"
