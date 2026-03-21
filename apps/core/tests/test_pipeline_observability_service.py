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
    SensitiveActionAudit.objects.create(
        user=None,
        action="sync_iol_historical_prices_partial",
        status="failed",
        details={
            "result": {
                "results": {
                    "NYSE:KO": {"success": False, "rows_received": 0, "error": "provider timeout"},
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
                {"simbolo": "GGAL", "mercado": "BCBA", "rows_count": 12, "latest_date": "2026-03-17", "status": "ready", "eligibility_source_key": "title_metadata", "eligibility_source_label": "Metadata de titulo"},
                {"simbolo": "AAPL", "mercado": "NASDAQ", "rows_count": 3, "latest_date": "2026-03-17", "status": "partial", "eligibility_source_key": "market_snapshot", "eligibility_source_label": "Market snapshot"},
                {"simbolo": "MSFT", "mercado": "NASDAQ", "rows_count": 0, "latest_date": None, "status": "missing", "eligibility_source_key": "market_snapshot", "eligibility_source_label": "Market snapshot"},
                {
                    "simbolo": "ADBAICA",
                    "mercado": "BCBA",
                    "rows_count": 0,
                    "latest_date": None,
                    "status": "unsupported",
                    "eligibility_status": "unsupported_fci",
                    "eligibility_reason_key": "fci_confirmed_by_iol",
                    "eligibility_reason": "Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos",
                    "eligibility_source_key": "fci_confirmation",
                    "eligibility_source_label": "Confirmacion FCI",
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
                    "eligibility_source_key": "local_classification",
                    "eligibility_source_label": "Clasificacion local",
                },
            ]

        def get_current_portfolio_market_snapshot_rows(self, limit=8):
            assert limit == 8
            return [
                {
                    "simbolo": "GGAL",
                    "mercado": "bcba",
                    "descripcion": "Grupo Financiero Galicia",
                    "tipo": "acciones",
                    "snapshot_status": "available",
                    "snapshot_source_key": "cotizacion_detalle",
                    "snapshot_source_label": "CotizacionDetalle",
                    "snapshot_reason_key": "",
                    "snapshot_reason": "",
                    "fecha_hora": "2026-03-20T16:59:46.4181717-03:00",
                    "fecha_hora_label": "2026-03-20 16:59",
                    "ultimo_precio": 1000,
                    "variacion": 1.5,
                    "cantidad_operaciones": 321,
                    "puntas_count": 1,
                    "best_bid": 995,
                    "best_ask": 1000,
                    "spread_abs": 5,
                    "spread_pct": 0.5,
                    "plazo": "t1",
                },
                {
                    "simbolo": "AAPL",
                    "mercado": "NASDAQ",
                    "descripcion": "Apple Inc.",
                    "tipo": "acciones",
                    "snapshot_status": "missing",
                    "snapshot_source_key": "",
                    "snapshot_source_label": "",
                    "snapshot_reason_key": "market_snapshot_unavailable",
                    "snapshot_reason": "IOL no devolvio cotizacion puntual para el instrumento.",
                    "fecha_hora": None,
                    "fecha_hora_label": "",
                    "ultimo_precio": None,
                    "variacion": None,
                    "cantidad_operaciones": 0,
                    "puntas_count": 0,
                    "best_bid": None,
                    "best_ask": None,
                    "spread_abs": None,
                    "spread_pct": None,
                    "plazo": "",
                },
                {
                    "simbolo": "ADBAICA",
                    "mercado": "BCBA",
                    "descripcion": "Adcap Cobertura",
                    "tipo": "FondoComundeInversion",
                    "snapshot_status": "unsupported",
                    "snapshot_source_key": "local_classification",
                    "snapshot_source_label": "Clasificacion local",
                    "snapshot_reason_key": "cash_management_local_classification",
                    "snapshot_reason": "FCI y cash management usan un pipeline distinto al de titulos",
                    "fecha_hora": None,
                    "fecha_hora_label": "",
                    "ultimo_precio": None,
                    "variacion": None,
                    "cantidad_operaciones": 0,
                    "puntas_count": 0,
                    "best_bid": None,
                    "best_ask": None,
                    "spread_abs": None,
                    "spread_pct": None,
                    "plazo": "",
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
    assert summary["iol_market_snapshot_summary"]["total_symbols"] == 3
    assert summary["iol_market_snapshot_summary"]["available_count"] == 1
    assert summary["iol_market_snapshot_summary"]["missing_count"] == 1
    assert summary["iol_market_snapshot_summary"]["unsupported_count"] == 1
    assert summary["iol_market_snapshot_summary"]["detail_count"] == 1
    assert summary["iol_market_snapshot_summary"]["fallback_count"] == 0
    assert summary["iol_market_snapshot_summary"]["order_book_count"] == 1
    assert summary["iol_historical_price_rows"][0]["simbolo"] == "GGAL"
    assert summary["iol_market_snapshot_rows"][0]["simbolo"] == "GGAL"
    assert summary["iol_historical_price_symbol_groups"]["ready"] == ["GGAL (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["partial"] == ["AAPL (NASDAQ)"]
    assert summary["iol_historical_price_symbol_groups"]["missing"] == ["MSFT (NASDAQ)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported"] == ["ADBAICA (BCBA)", "CAUCION (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported_fci"] == ["ADBAICA (BCBA)"]
    assert summary["iol_historical_price_symbol_groups"]["unsupported_other"] == ["CAUCION (BCBA)"]
    row_by_symbol = {row["simbolo"]: row for row in summary["iol_historical_price_rows"]}
    assert row_by_symbol["GGAL"]["eligibility_source_key"] == "title_metadata"
    assert row_by_symbol["AAPL"]["eligibility_source_label"] == "Market snapshot"
    assert row_by_symbol["ADBAICA"]["eligibility_source_label"] == "Confirmacion FCI"
    assert summary["iol_historical_exclusion_rows"][0]["reason_key"] == "caucion_not_title_series"
    assert summary["iol_historical_exclusion_rows"][0]["count"] == 1
    assert summary["iol_historical_exclusion_rows"][1]["reason_key"] == "fci_confirmed_by_iol"
    assert summary["iol_historical_exclusion_rows"][1]["symbols"] == ["ADBAICA (BCBA)"]
    assert summary["iol_historical_ops_cta"]["level"] == "danger"
    assert summary["iol_historical_ops_cta"]["title"] == "Atención inmediata en históricos IOL"
    assert summary["iol_historical_ops_cta"]["symbol_keys"] == ["NYSE:KO"]
    assert [row["symbol_key"] for row in summary["iol_historical_recent_sync_priority_groups"]["critical"]] == ["NYSE:KO"]
    assert [row["symbol_key"] for row in summary["iol_historical_recent_sync_priority_groups"]["recoverable"]] == ["NASDAQ:AAPL", "NASDAQ:MSFT"]
    assert [row["symbol_key"] for row in summary["iol_historical_recent_sync_priority_groups"]["stable"]] == ["BCBA:GGAL"]
    assert len(summary["iol_historical_recent_sync_rows"]) == 5
    grouped_by_symbol = {row["symbol_key"]: row for row in summary["iol_historical_recent_sync_by_symbol"]}
    assert summary["iol_historical_recent_sync_by_symbol"][0]["symbol_key"] == "NYSE:KO"
    assert summary["iol_historical_recent_sync_by_symbol"][0]["priority_key"] == "critical"
    assert summary["iol_historical_recent_sync_by_symbol"][1]["symbol_key"] == "NASDAQ:AAPL"
    assert summary["iol_historical_recent_sync_by_symbol"][1]["priority_key"] == "recoverable"
    assert grouped_by_symbol["NASDAQ:AAPL"]["user_labels"] == ["system"]
    assert {item["scope"] for item in grouped_by_symbol["NASDAQ:AAPL"]["items"]} == {"missing", "metadata"}
    assert {item["rows_received"] for item in grouped_by_symbol["NASDAQ:AAPL"]["items"]} == {30, 7}
    assert grouped_by_symbol["NYSE:KO"]["priority_label"] == "Atención inmediata"
    assert grouped_by_symbol["BCBA:GGAL"]["priority_label"] == "Estable"
    assert {row["scope"] for row in summary["iol_historical_recent_sync_rows"]} == {"missing", "partial", "metadata"}
    assert {row["action_label"] for row in summary["iol_historical_recent_sync_rows"]} == {"Sync faltantes", "Reforzar parciales", "Reintentar metadata"}
    assert {row["user_label"] for row in summary["iol_historical_recent_sync_rows"]} == {"system"}
    rows_by_scope_symbol = {(row["scope"], row["symbol_key"]): row for row in summary["iol_historical_recent_sync_rows"]}
    assert rows_by_scope_symbol[("missing", "NASDAQ:AAPL")]["rows_received"] == 30
    assert rows_by_scope_symbol[("partial", "BCBA:GGAL")]["rows_received"] == 12
    assert rows_by_scope_symbol[("metadata", "NASDAQ:MSFT")]["rows_received"] == 18
    assert rows_by_scope_symbol[("metadata", "NASDAQ:AAPL")]["rows_received"] == 7
    assert rows_by_scope_symbol[("partial", "NYSE:KO")]["status"] == "failed"
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

        def get_current_portfolio_market_snapshot_rows(self, limit=8):
            assert limit == 8
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
    assert summary["iol_market_snapshot_summary"]["overall_status"] == "missing"
    assert summary["iol_historical_price_symbol_groups"]["ready"] == []
    assert summary["iol_historical_price_symbol_groups"]["partial"] == []
    assert summary["iol_historical_price_symbol_groups"]["missing"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported_fci"] == []
    assert summary["iol_historical_price_symbol_groups"]["unsupported_other"] == []
    assert summary["iol_historical_exclusion_rows"] == []
    assert summary["iol_historical_ops_cta"] is None
    assert summary["iol_historical_recent_sync_by_symbol"] == []
    assert summary["iol_historical_recent_sync_priority_groups"] == {
        "critical": [],
        "recoverable": [],
        "stable": [],
    }
    assert summary["iol_historical_recent_sync_rows"] == []
    assert summary["local_macro_status_summary"]["overall_status"] == "missing"
    assert summary["critical_local_macro_summary"]["overall_status"] == "missing"
    assert summary["critical_local_macro_summary"]["attention_count"] == 7
    assert summary["external_sources_status_summary"]["overall_status"] == "failed"
    assert summary["external_source_status_rows"][0]["detail"] == "service unavailable"
