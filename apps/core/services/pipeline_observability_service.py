from __future__ import annotations

from datetime import datetime

from apps.core.services.analytics_v2 import CovarianceAwareRiskContributionService
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.data_quality.historical_coverage_health import HistoricalCoverageHealthService
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.market_data.argentina_datos_client import ArgentinaDatosClient
from apps.core.models import SensitiveActionAudit
from django.utils import timezone


class PipelineObservabilityService:
    """Consolida metricas operativas del pipeline de datos para Ops."""

    CRITICAL_LOCAL_MACRO_SERIES = (
        {"series_key": "usdars_oficial", "label": "USDARS oficial", "why": "base para brecha FX"},
        {"series_key": "usdars_mep", "label": "USDARS MEP", "why": "referencia financiera local"},
        {"series_key": "usdars_ccl", "label": "USDARS CCL", "why": "divergencia MEP / CCL"},
        {"series_key": "badlar_privada", "label": "BADLAR privada", "why": "carry nominal local"},
        {"series_key": "ipc_nacional", "label": "IPC nacional", "why": "fallback de inflacion local"},
        {"series_key": "uva", "label": "UVA", "why": "proxy de CER e inflacion indexada"},
        {"series_key": "riesgo_pais_arg", "label": "Riesgo pais Argentina", "why": "stress soberano y riesgo local"},
    )

    def __init__(
        self,
        sync_audit_service: IOLSyncAuditService | None = None,
        coverage_health_service: HistoricalCoverageHealthService | None = None,
        snapshot_integrity_service: SnapshotIntegrityService | None = None,
        benchmark_service: BenchmarkSeriesService | None = None,
        iol_historical_price_service: IOLHistoricalPriceService | None = None,
        local_macro_service: LocalMacroSeriesService | None = None,
        argentina_datos_client: ArgentinaDatosClient | None = None,
    ):
        self.sync_audit_service = sync_audit_service or IOLSyncAuditService()
        self.coverage_health_service = coverage_health_service or HistoricalCoverageHealthService()
        self.snapshot_integrity_service = snapshot_integrity_service or SnapshotIntegrityService()
        self.benchmark_service = benchmark_service or BenchmarkSeriesService()
        self.iol_historical_price_service = iol_historical_price_service or IOLHistoricalPriceService()
        self.local_macro_service = local_macro_service or LocalMacroSeriesService()
        self.argentina_datos_client = argentina_datos_client or ArgentinaDatosClient()

    def build_summary(self, lookback_days: int = 30, integrity_days: int = 120) -> dict:
        sync_audit = self.sync_audit_service.run_audit(freshness_hours=24)
        coverage = self.coverage_health_service.build_summary(lookback_days=lookback_days)
        snapshot_integrity = self.snapshot_integrity_service.run_checks(days=integrity_days)
        benchmark_status_rows = self.benchmark_service.get_status_summary()
        iol_historical_price_rows = self.iol_historical_price_service.get_current_portfolio_coverage_rows()
        local_macro_status_rows = self.local_macro_service.get_status_summary()
        critical_local_macro_rows = self._build_critical_local_macro_rows(local_macro_status_rows)
        external_source_status_rows = self._build_external_source_status_rows()

        latest_portfolio_snapshot_date = coverage.get("latest_portfolio_snapshot_date")
        days_since_last_portfolio_snapshot = None
        if latest_portfolio_snapshot_date:
            days_since_last_portfolio_snapshot = (
                timezone.localdate() - datetime.fromisoformat(latest_portfolio_snapshot_date).date()
            ).days

        latest_successful_iol_sync = None
        snapshots_info = sync_audit.get("snapshots", {})
        if snapshots_info.get("status") == "ok" and snapshots_info.get("latest_sync") is not None:
            latest_sync = snapshots_info["latest_sync"]
            latest_successful_iol_sync = self._format_local_datetime(latest_sync)

        usable_observations_count = int(coverage.get("usable_observations_count") or 0)
        available_price_dates_count = int(coverage.get("available_price_dates_count") or 0)

        return {
            "last_successful_iol_sync": latest_successful_iol_sync,
            "iol_sync_status": sync_audit.get("status"),
            "latest_asset_snapshot_at": self._format_local_datetime(coverage.get("latest_asset_snapshot_at")),
            "latest_account_snapshot_at": self._format_local_datetime(coverage.get("latest_account_snapshot_at")),
            "latest_portfolio_snapshot_date": latest_portfolio_snapshot_date,
            "days_since_last_portfolio_snapshot": days_since_last_portfolio_snapshot,
            "covariance_readiness": self._build_covariance_readiness(
                usable_observations_count=usable_observations_count,
            ),
            "usable_observations_count": usable_observations_count,
            "available_price_dates_count": available_price_dates_count,
            "benchmark_status_summary": self._build_benchmark_status_summary(benchmark_status_rows),
            "iol_historical_price_summary": self._build_iol_historical_price_summary(iol_historical_price_rows),
            "iol_historical_price_symbol_groups": self._build_iol_historical_symbol_groups(iol_historical_price_rows),
            "iol_historical_recent_sync_rows": self._build_iol_historical_recent_sync_rows(limit=12),
            "local_macro_status_summary": self._build_local_macro_status_summary(local_macro_status_rows),
            "critical_local_macro_summary": self._build_critical_local_macro_summary(critical_local_macro_rows),
            "external_sources_status_summary": self._build_external_sources_status_summary(external_source_status_rows),
            "snapshot_integrity_issues_count": int(snapshot_integrity.get("issues_count") or 0),
            "required_periodic_tasks": coverage.get("required_periodic_tasks", []),
            "benchmark_status_rows": benchmark_status_rows,
            "iol_historical_price_rows": iol_historical_price_rows,
            "local_macro_status_rows": local_macro_status_rows,
            "critical_local_macro_rows": critical_local_macro_rows,
            "external_source_status_rows": external_source_status_rows,
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

    @staticmethod
    def _build_iol_historical_price_summary(rows: list[dict]) -> dict:
        total = len(rows)
        ready_count = sum(1 for row in rows if row.get("status") == "ready")
        partial_count = sum(1 for row in rows if row.get("status") == "partial")
        missing_count = sum(1 for row in rows if row.get("status") == "missing")
        unsupported_count = sum(1 for row in rows if row.get("status") == "unsupported")
        if total == 0:
            overall_status = "missing"
        elif missing_count == 0 and partial_count == 0:
            overall_status = "ready"
        elif ready_count > 0 or partial_count > 0:
            overall_status = "partial"
        else:
            overall_status = "warning" if unsupported_count > 0 else "missing"
        return {
            "total_symbols": total,
            "ready_count": ready_count,
            "partial_count": partial_count,
            "missing_count": missing_count,
            "unsupported_count": unsupported_count,
            "overall_status": overall_status,
        }

    @staticmethod
    def _build_iol_historical_symbol_groups(rows: list[dict]) -> dict:
        def _label(row: dict) -> str:
            simbolo = str(row.get("simbolo") or "-")
            mercado = str(row.get("mercado") or "-")
            return f"{simbolo} ({mercado})"

        ready = [_label(row) for row in rows if row.get("status") == "ready"]
        partial = [_label(row) for row in rows if row.get("status") == "partial"]
        missing = [_label(row) for row in rows if row.get("status") == "missing"]
        unsupported = [_label(row) for row in rows if row.get("status") == "unsupported"]
        return {
            "ready": ready,
            "partial": partial,
            "missing": missing,
            "unsupported": unsupported,
        }

    def _build_iol_historical_recent_sync_rows(self, limit: int = 12) -> list[dict]:
        audits = SensitiveActionAudit.objects.filter(
            action__in=["sync_iol_historical_prices", "sync_iol_historical_prices_partial"]
        ).order_by("-created_at", "-id")[:limit]

        rows: list[dict] = []
        seen_symbol_keys: set[str] = set()
        for audit in audits:
            details = audit.details or {}
            result = details.get("result") or {}
            results = result.get("results") or {}
            sync_scope = "missing" if audit.action == "sync_iol_historical_prices" else "partial"
            if not results:
                if "-" in seen_symbol_keys:
                    continue
                seen_symbol_keys.add("-")
                rows.append(
                    {
                        "scope": sync_scope,
                        "action_label": "Sync faltantes" if sync_scope == "missing" else "Reforzar parciales",
                        "symbol_key": "-",
                        "rows_received": 0,
                        "status": audit.status,
                        "user_label": audit.user.username if audit.user else "system",
                        "created_at": self._format_local_datetime(audit.created_at),
                        "message": "Sin simbolos seleccionados",
                    }
                )
                continue

            for symbol_key, payload in results.items():
                if symbol_key in seen_symbol_keys:
                    continue
                seen_symbol_keys.add(symbol_key)
                rows.append(
                    {
                        "scope": sync_scope,
                        "action_label": "Sync faltantes" if sync_scope == "missing" else "Reforzar parciales",
                        "symbol_key": symbol_key,
                        "rows_received": int(payload.get("rows_received") or 0),
                        "status": "success" if payload.get("success", True) else "failed",
                        "user_label": audit.user.username if audit.user else "system",
                        "created_at": self._format_local_datetime(audit.created_at),
                        "message": payload.get("error") or "",
                    }
                )
                if len(rows) >= limit:
                    return rows
        return rows[:limit]

    @staticmethod
    def _build_critical_local_macro_summary(rows: list[dict]) -> dict:
        total = len(rows)
        ready_count = sum(1 for row in rows if row.get("status") == "ready")
        attention_count = sum(1 for row in rows if row.get("status") != "ready")
        if total == 0:
            overall_status = "missing"
        elif attention_count == 0:
            overall_status = "ready"
        elif ready_count > 0:
            overall_status = "warning"
        else:
            overall_status = "missing"
        return {
            "total_series": total,
            "ready_count": ready_count,
            "attention_count": attention_count,
            "overall_status": overall_status,
        }

    @staticmethod
    def _build_external_sources_status_summary(rows: list[dict]) -> dict:
        total = len(rows)
        ready_count = sum(1 for row in rows if row.get("is_ready"))
        failed_count = max(total - ready_count, 0)
        if total == 0:
            overall_status = "missing"
        elif failed_count == 0:
            overall_status = "ready"
        elif ready_count > 0:
            overall_status = "partial"
        else:
            overall_status = "failed"
        return {
            "total_sources": total,
            "ready_count": ready_count,
            "failed_count": failed_count,
            "overall_status": overall_status,
        }

    def _build_critical_local_macro_rows(self, local_macro_status_rows: list[dict]) -> list[dict]:
        rows_by_key = {str(row.get("series_key")): row for row in local_macro_status_rows}
        critical_rows = []
        for item in self.CRITICAL_LOCAL_MACRO_SERIES:
            source_row = rows_by_key.get(item["series_key"], {})
            critical_rows.append(
                {
                    "series_key": item["series_key"],
                    "label": item["label"],
                    "why": item["why"],
                    "status": source_row.get("status") or "missing",
                    "source": source_row.get("source") or "-",
                    "latest_date": source_row.get("latest_date"),
                    "rows_count": int(source_row.get("rows_count") or 0),
                }
            )
        return critical_rows

    def _build_external_source_status_rows(self) -> list[dict]:
        rows = []
        try:
            payload = self.argentina_datos_client.fetch_status()
            reported_status = str(
                payload.get("status")
                or payload.get("estado")
                or payload.get("message")
                or "ok"
            )
            detail = str(
                payload.get("message")
                or payload.get("descripcion")
                or payload.get("version")
                or "-"
            )
            rows.append(
                {
                    "source_key": "argentina_datos",
                    "label": "ArgentinaDatos",
                    "endpoint": "/v1/estado",
                    "status": "ready",
                    "is_ready": True,
                    "reported_status": reported_status,
                    "detail": detail,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "source_key": "argentina_datos",
                    "label": "ArgentinaDatos",
                    "endpoint": "/v1/estado",
                    "status": "failed",
                    "is_ready": False,
                    "reported_status": "-",
                    "detail": str(exc),
                }
            )
        return rows

    @staticmethod
    def _format_local_datetime(value) -> str | None:
        if not value:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
