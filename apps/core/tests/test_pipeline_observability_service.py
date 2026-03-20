import pytest

from datetime import date, datetime, timezone as dt_timezone

from django.utils import timezone

from apps.core.models import SensitiveActionAudit
from apps.core.services.pipeline_observability_service import PipelineObservabilityService


@pytest.mark.django_db
def test_pipeline_observability_service_builds_unified_summary():
    SensitiveActionAudit.objects.create(
        user=None,
        action="sync_iol_historical_prices",
        status="success",
        details={
            "result": {
                "results": {
                    "NASDAQ:AAPL": {"success": True, "rows_received": 10},
                }
            }
        },
    )
    SensitiveActionAudit.objects.create(
        user=None,
        action="sync_iol_historical_prices",
        status="success",
        details={
            "result": {
                "results": {
                    "NASDAQ:AAPL": {"success": True, "rows_received": 30},
                }
            }
        },
    )
    SensitiveActionAudit.objects.create(
        user=None,
        action="sync_iol_historical_prices_partial",
        status="success",
        details={
            "result": {
                "results": {
                    "BCBA:GGAL": {"success": True, "rows_received": 12},
                }
            }
        },
    )
    SensitiveActionAudit.objects.create(
        user=None,
        action="sync_iol_historical_prices_retry_metadata",
        status="success",
        details={
            "result": {
                "results": {
                    "NASDAQ:MSFT": {"success": True, "rows_received": 18},
                    "NASDAQ:AAPL": {"success": True, "rows_received": 7},
                }
            }
        },
    )

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

    class DummyIOLHistoricalPriceService:
        def get_current_portfolio_coverage_rows(self):
            return [
                {"simbolo": "GGAL", "mercado": "BCBA", "rows_count": 12, "latest_date": "2026-03-17", "status": "ready"},
                {"simbolo": "AAPL", "mercado": "NASDAQ", "rows_count": 3, "latest_date": "2026-03-17", "status": "partial"},
                {"simbolo": "MSFT", "mercado": "NASDAQ", "rows_count": 0, "latest_date": None, "status": "missing"},
                {
                    "simbolo": "ADBAICA",
                    "mercado": "BCBA",
                    "rows_count": 0,
                    "latest_date": None,
                    "status": "unsupported",
                    "eligibility_status": "unsupported_fci",
                    "eligibility_reason_key": "fci_confirmed_by_iol",
                    "eligibility_reason": "Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos",
                },
                {
                    "simbolo": "CAUCION",
                    "mercado": "BCBA",
                    "rows_count": 0,
                    "latest_date": None,
                    "status": "unsupported",
                    "eligibility_status": "unsupported",
                    "eligibility_reason_key": "caucion_not_title_series",
                    "eligibility_reason": "La caución no expone serie histórica de cotización como un título estándar",
                },
            ]

    class DummyLocalMacroService:
        def get_status_summary(self):
            return [
                {"series_key": "usdars_oficial", "status": "ready"},
                {"series_key": "usdars_mep", "status": "not_configured"},
                {"series_key": "badlar_privada", "status": "stale"},
            ]

    class DummyArgentinaDatosClient:
        def fetch_status(self):
            return {"status": "ok", "message": "healthy"}

    summary = PipelineObservabilityService(
        sync_audit_service=DummySyncAuditService(),
        coverage_health_service=DummyCoverageService(),
        snapshot_integrity_service=DummySnapshotIntegrityService(),
        benchmark_service=DummyBenchmarkService(),
        iol_historical_price_service=DummyIOLHistoricalPriceService(),
        local_macro_service=DummyLocalMacroService(),
        argentina_datos_client=DummyArgentinaDatosClient(),
    ).build_summary(lookback_days=30, integrity_days=120)

    assert summary["last_successful_iol_sync"] == "2026-03-17 10:00"
    assert summary["iol_sync_status"] == "ok"
    assert summary["latest_asset_snapshot_at"] == "2026-03-17 10:00"
    assert summary["latest_account_snapshot_at"] == "2026-03-17 10:00"
    assert summary["latest_portfolio_snapshot_date"] == "2026-03-16"
    assert summary["days_since_last_portfolio_snapshot"] == (timezone.localdate() - date(2026, 3, 16)).days
    assert summary["usable_observations_count"] == 21
    assert summary["available_price_dates_count"] == 28
    assert summary["covariance_readiness"]["status"] == "ready"
    assert summary["benchmark_status_summary"]["ready_count"] == 1
    assert summary["benchmark_status_summary"]["overall_status"] == "partial"
    assert summary["iol_historical_price_summary"]["total_symbols"] == 5
    assert summary["iol_historical_price_summary"]["ready_count"] == 1
    assert summary["iol_historical_price_summary"]["partial_count"] == 1
    assert summary["iol_historical_price_summary"]["missing_count"] == 1
    assert summary["iol_historical_price_summary"]["unsupported_count"] == 2
    assert summary["iol_historical_price_summary"]["unsupported_fci_count"] == 1
    assert summary["iol_historical_price_summary"]["unsupported_other_count"] == 1
    assert summary["iol_historical_price_summary"]["overall_status"] == "partial"
    assert summary["iol_historical_price_rows"][0]["simbolo"] == "GGAL"
    assert summary["iol_historical_price_symbol_groups"]["ready"] == ["GGAL (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["partial"] == ["AAPL (NASDAQ)"]
    assert summary["iol_historical_price_symbol_groups"]["missing"] == ["MSFT (NASDAQ)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported"] == ["ADBAICA (BCBA)", "CAUCION (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported_fci"] == ["ADBAICA (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported_other"] == ["CAUCION (BCBA)"]
    assert summary["iol_historical_exclusion_rows"][0]["reason_key"] == "caucion_not_title_series"
    assert summary["iol_historical_exclusion_rows"][0]["count"] == 1
    assert summary["iol_historical_exclusion_rows"][1]["reason_key"] == "fci_confirmed_by_iol"
    assert summary["iol_historical_exclusion_rows"][1]["symbols"] == ["ADBAICA (BCBA)"]
    assert len(summary["iol_historical_recent_sync_rows"]) == 4
    assert {row["scope"] for row in summary["iol_historical_recent_sync_rows"]} == {"missing", "partial", "metadata"}
    assert {row["action_label"] for row in summary["iol_historical_recent_sync_rows"]} == {"Sync faltantes", "Reforzar parciales", "Reintentar metadata"}
    assert {row["user_label"] for row in summary["iol_historical_recent_sync_rows"]} == {"system"}
    rows_by_scope_symbol = {(row["scope"], row["symbol_key"]): row for row in summary["iol_historical_recent_sync_rows"]}
    assert rows_by_scope_symbol[("missing", "NASDAQ:AAPL")]["rows_received"] == 30
    assert rows_by_scope_symbol[("partial", "BCBA:GGAL")]["rows_received"] == 12
    assert rows_by_scope_symbol[("metadata", "NASDAQ:MSFT")]["rows_received"] == 18
    assert rows_by_scope_symbol[("metadata", "NASDAQ:AAPL")]["rows_received"] == 7
    assert summary["local_macro_status_summary"]["ready"] == 1
    assert summary["local_macro_status_summary"]["stale"] == 1
    assert summary["local_macro_status_summary"]["not_configured"] == 1
    assert summary["local_macro_status_summary"]["overall_status"] == "warning"
    assert summary["critical_local_macro_summary"]["total_series"] == 7
    assert summary["critical_local_macro_summary"]["ready_count"] == 1
    assert summary["critical_local_macro_summary"]["attention_count"] == 6
    assert summary["critical_local_macro_summary"]["overall_status"] == "warning"
    assert summary["critical_local_macro_rows"][0]["label"] == "USDARS oficial"
    assert summary["critical_local_macro_rows"][1]["status"] == "not_configured"
    assert summary["critical_local_macro_rows"][-1]["series_key"] == "riesgo_pais_arg"
    assert summary["critical_local_macro_rows"][-1]["status"] == "missing"
    assert summary["external_sources_status_summary"]["ready_count"] == 1
    assert summary["external_sources_status_summary"]["overall_status"] == "ready"
    assert summary["external_source_status_rows"][0]["label"] == "ArgentinaDatos"
    assert summary["external_source_status_rows"][0]["reported_status"] == "ok"
    assert summary["snapshot_integrity_issues_count"] == 2


@pytest.mark.django_db
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

    class DummyIOLHistoricalPriceService:
        def get_current_portfolio_coverage_rows(self):
            return []

    class DummyLocalMacroService:
        def get_status_summary(self):
            return []

    class DummyArgentinaDatosClient:
        def fetch_status(self):
            raise ConnectionError("service unavailable")

    summary = PipelineObservabilityService(
        sync_audit_service=DummySyncAuditService(),
        coverage_health_service=DummyCoverageService(),
        snapshot_integrity_service=DummySnapshotIntegrityService(),
        benchmark_service=DummyBenchmarkService(),
        iol_historical_price_service=DummyIOLHistoricalPriceService(),
        local_macro_service=DummyLocalMacroService(),
        argentina_datos_client=DummyArgentinaDatosClient(),
    ).build_summary()

    assert summary["last_successful_iol_sync"] is None
    assert summary["days_since_last_portfolio_snapshot"] is None
    assert summary["covariance_readiness"]["status"] == "missing"
    assert summary["benchmark_status_summary"]["overall_status"] == "missing"
    assert summary["iol_historical_price_summary"]["overall_status"] == "missing"
    assert summary["iol_historical_price_symbol_groups"]["ready"] == []
    assert summary["iol_historical_price_symbol_groups"]["partial"] == []
    assert summary["iol_historical_price_symbol_groups"]["missing"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported_fci"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported_other"] == []
    assert summary["iol_historical_exclusion_rows"] == []
    assert summary["iol_historical_recent_sync_rows"] == []
    assert summary["local_macro_status_summary"]["overall_status"] == "missing"
    assert summary["critical_local_macro_summary"]["overall_status"] == "missing"
    assert summary["critical_local_macro_summary"]["attention_count"] == 7
    assert summary["external_sources_status_summary"]["overall_status"] == "failed"
    assert summary["external_source_status_rows"][0]["detail"] == "service unavailable"
