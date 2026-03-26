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
        iol_market_snapshot_rows = self.iol_historical_price_service.get_current_portfolio_market_snapshot_rows(limit=8)
        iol_historical_recent_sync_rows = self._build_iol_historical_recent_sync_rows(limit=12)
        iol_historical_recent_sync_by_symbol = self._build_iol_historical_recent_sync_by_symbol(
            iol_historical_recent_sync_rows
        )
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
            "iol_market_snapshot_summary": self.iol_historical_price_service.summarize_market_snapshot_rows(
                iol_market_snapshot_rows
            ),
            "iol_historical_price_symbol_groups": self._build_iol_historical_symbol_groups(iol_historical_price_rows),
            "iol_historical_exclusion_rows": self._build_iol_historical_exclusion_rows(iol_historical_price_rows),
            "iol_historical_recent_sync_rows": iol_historical_recent_sync_rows,
            "iol_historical_recent_sync_by_symbol": iol_historical_recent_sync_by_symbol,
            "iol_historical_recent_sync_priority_groups": self._build_iol_historical_recent_sync_priority_groups(
                iol_historical_recent_sync_by_symbol
            ),
            "iol_historical_ops_cta": self._build_iol_historical_ops_cta(iol_historical_recent_sync_rows),
            "local_macro_status_summary": self._build_local_macro_status_summary(local_macro_status_rows),
            "critical_local_macro_summary": self._build_critical_local_macro_summary(critical_local_macro_rows),
            "external_sources_status_summary": self._build_external_sources_status_summary(external_source_status_rows),
            "snapshot_integrity_issues_count": int(snapshot_integrity.get("issues_count") or 0),
            "required_periodic_tasks": coverage.get("required_periodic_tasks", []),
            "benchmark_status_rows": benchmark_status_rows,
            "iol_historical_price_rows": iol_historical_price_rows,
            "iol_market_snapshot_rows": iol_market_snapshot_rows,
            "local_macro_status_rows": local_macro_status_rows,
            "critical_local_macro_rows": critical_local_macro_rows,
            "external_source_status_rows": external_source_status_rows,
        }

    def build_ops_lite_summary(self, lookback_days: int = 30, integrity_days: int = 120) -> dict:
        """Resumen acotado para la pantalla Ops.

        Evita resolver detalle por simbolo o snapshots puntuales, que disparan
        lookups remotos y vuelven la vista innecesariamente pesada.
        """

        sync_audit = self.sync_audit_service.run_audit(freshness_hours=24)
        coverage = self.coverage_health_service.build_summary(lookback_days=lookback_days)
        snapshot_integrity = self.snapshot_integrity_service.run_checks(days=integrity_days)
        benchmark_status_rows = self.benchmark_service.get_status_summary()
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
            latest_successful_iol_sync = self._format_local_datetime(snapshots_info["latest_sync"])

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
            "local_macro_status_summary": self._build_local_macro_status_summary(local_macro_status_rows),
            "critical_local_macro_summary": self._build_critical_local_macro_summary(critical_local_macro_rows),
            "external_sources_status_summary": self._build_external_sources_status_summary(external_source_status_rows),
            "snapshot_integrity_issues_count": int(snapshot_integrity.get("issues_count") or 0),
            "required_periodic_tasks": coverage.get("required_periodic_tasks", []),
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
        unsupported_fci_count = sum(1 for row in rows if row.get("eligibility_status") == "unsupported_fci")
        unsupported_other_count = max(unsupported_count - unsupported_fci_count, 0)
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
            "unsupported_fci_count": unsupported_fci_count,
            "unsupported_other_count": unsupported_other_count,
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
        unsupported_fci = [_label(row) for row in rows if row.get("eligibility_status") == "unsupported_fci"]
        unsupported_other = [
            _label(row)
            for row in rows
            if row.get("status") == "unsupported" and row.get("eligibility_status") != "unsupported_fci"
        ]
        return {
            "ready": ready,
            "partial": partial,
            "missing": missing,
            "unsupported": unsupported,
            "unsupported_fci": unsupported_fci,
            "unsupported_other": unsupported_other,
        }

    @staticmethod
    def _build_iol_historical_exclusion_rows(rows: list[dict]) -> list[dict]:
        labels = {
            "fci_confirmed_by_iol": "FCI confirmado por IOL",
            "cash_management_local_classification": "Cash management / FCI por clasificación local",
            "caucion_not_title_series": "Caución sin serie histórica de título",
            "cash_like_not_title_series": "Cash-like sin serie histórica de título",
            "title_metadata_unresolved": "Sin metadata resoluble de título",
            "missing_symbol_or_market": "Sin símbolo o mercado válido",
        }
        grouped: dict[str, dict] = {}
        for row in rows:
            if row.get("status") != "unsupported":
                continue
            reason_key = str(row.get("eligibility_reason_key") or "unknown")
            symbol_label = f"{row.get('simbolo', '-')} ({row.get('mercado', '-')})"
            group = grouped.setdefault(
                reason_key,
                {
                    "reason_key": reason_key,
                    "reason_label": labels.get(reason_key, "Motivo no clasificado"),
                    "reason_text": row.get("eligibility_reason") or "",
                    "count": 0,
                    "symbols": [],
                },
            )
            group["count"] += 1
            group["symbols"].append(symbol_label)
        exclusion_rows = list(grouped.values())
        exclusion_rows.sort(key=lambda item: (-int(item["count"]), item["reason_label"]))
        return exclusion_rows

    @staticmethod
    def _build_iol_historical_recent_sync_by_symbol(rows: list[dict]) -> list[dict]:
        grouped: dict[str, dict] = {}
        for row in rows:
            symbol_key = str(row.get("symbol_key") or "-")
            group = grouped.setdefault(
                symbol_key,
                {
                    "symbol_key": symbol_key,
                    "user_labels": [],
                    "items": [],
                    "latest_at": row.get("created_at"),
                },
            )
            user_label = str(row.get("user_label") or "system")
            if user_label not in group["user_labels"]:
                group["user_labels"].append(user_label)
            group["items"].append(
                {
                    "scope": row.get("scope"),
                    "action_label": row.get("action_label"),
                    "rows_received": row.get("rows_received"),
                    "status": row.get("status"),
                    "created_at": row.get("created_at"),
                    "message": row.get("message"),
                }
            )
            latest_at = row.get("created_at")
            if latest_at and (group["latest_at"] is None or str(latest_at) > str(group["latest_at"])):
                group["latest_at"] = latest_at

        result = list(grouped.values())
        for group in result:
            group["items"].sort(key=PipelineObservabilityService._sort_recent_sync_item_key)
            priority = PipelineObservabilityService._build_recent_sync_priority(group["items"])
            group["priority_key"] = priority["key"]
            group["priority_label"] = priority["label"]
            group["priority_badge"] = priority["badge"]
        result.sort(key=PipelineObservabilityService._sort_recent_sync_group_key)
        return result

    @staticmethod
    def _sort_recent_sync_item_key(item: dict) -> tuple[int, str, str]:
        status = str(item.get("status") or "")
        scope = str(item.get("scope") or "")
        created_at = str(item.get("created_at") or "")
        if status == "failed":
            priority = 0
        elif scope == "metadata":
            priority = 1
        else:
            priority = 2
        return (priority, created_at, scope)

    @staticmethod
    def _build_recent_sync_priority(items: list[dict]) -> dict:
        has_failed = any(str(item.get("status") or "") == "failed" for item in items)
        has_metadata = any(str(item.get("scope") or "") == "metadata" for item in items)
        if has_failed:
            return {
                "key": "critical",
                "label": "Atención inmediata",
                "badge": "danger",
            }
        if has_metadata:
            return {
                "key": "recoverable",
                "label": "Recuperable",
                "badge": "warning",
            }
        return {
            "key": "stable",
            "label": "Estable",
            "badge": "success",
        }

    @staticmethod
    def _sort_recent_sync_group_key(group: dict) -> tuple[int, int, str]:
        priority_key = str(group.get("priority_key") or "")
        latest_at = str(group.get("latest_at") or "")
        symbol_key = str(group.get("symbol_key") or "")
        if priority_key == "critical":
            priority = 0
        elif priority_key == "recoverable":
            priority = 1
        else:
            priority = 2
        return (priority, 0 if symbol_key == "-" else 1, f"{latest_at}|{symbol_key}")

    @staticmethod
    def _build_iol_historical_ops_cta(rows: list[dict]) -> dict | None:
        failed_rows = [row for row in rows if str(row.get("status") or "") == "failed"]
        metadata_rows = [row for row in rows if str(row.get("scope") or "") == "metadata"]

        if failed_rows:
            symbol_keys = [str(row.get("symbol_key") or "-") for row in failed_rows if str(row.get("symbol_key") or "-") != "-"]
            return {
                "level": "danger",
                "title": "Atención inmediata en históricos IOL",
                "message": "Hay sincronizaciones fallidas. Conviene revisar el detalle antes de seguir reforzando cobertura.",
                "action_hint": "Priorizá revisión manual de los símbolos fallidos y luego reintentá el flujo correspondiente.",
                "symbol_keys": symbol_keys[:5],
            }

        if metadata_rows:
            symbol_keys = [str(row.get("symbol_key") or "-") for row in metadata_rows if str(row.get("symbol_key") or "-") != "-"]
            return {
                "level": "warning",
                "title": "Cobertura recuperable por metadata",
                "message": "No hay fallos activos, pero todavía quedan símbolos que dependen de reintento de metadata.",
                "action_hint": "Usá 'Reintentar metadata IOL no resuelta' sobre los símbolos recuperables.",
                "symbol_keys": symbol_keys[:5],
            }

        if rows:
            return {
                "level": "success",
                "title": "Cobertura operativa estable",
                "message": "No hay fallos recientes ni reintentos de metadata pendientes en el historial manual.",
                "action_hint": "No hace falta intervenir ahora. Solo monitoreá nuevos faltantes o parciales.",
                "symbol_keys": [],
            }

        return None

    @staticmethod
    def _build_iol_historical_recent_sync_priority_groups(rows: list[dict]) -> dict:
        groups = {
            "critical": [row for row in rows if str(row.get("priority_key") or "") == "critical"],
            "recoverable": [row for row in rows if str(row.get("priority_key") or "") == "recoverable"],
            "stable": [row for row in rows if str(row.get("priority_key") or "") == "stable"],
        }
        return groups

    def _build_iol_historical_recent_sync_rows(self, limit: int = 12) -> list[dict]:
        audits = SensitiveActionAudit.objects.filter(
            action__in=[
                "sync_iol_historical_prices",
                "sync_iol_historical_prices_partial",
                "sync_iol_historical_prices_retry_metadata",
            ]
        ).order_by("-created_at", "-id")[:limit]

        rows: list[dict] = []
        seen_entries: set[tuple[str, str]] = set()
        for audit in audits:
            details = audit.details or {}
            result = details.get("result") or {}
            results = result.get("results") or {}
            if audit.action == "sync_iol_historical_prices":
                sync_scope = "missing"
                action_label = "Sync faltantes"
            elif audit.action == "sync_iol_historical_prices_partial":
                sync_scope = "partial"
                action_label = "Reforzar parciales"
            else:
                sync_scope = "metadata"
                action_label = "Reintentar metadata"
            if not results:
                empty_key = (sync_scope, "-")
                if empty_key in seen_entries:
                    continue
                seen_entries.add(empty_key)
                rows.append(
                    {
                        "scope": sync_scope,
                        "action_label": action_label,
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
                entry_key = (sync_scope, symbol_key)
                if entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)
                rows.append(
                    {
                        "scope": sync_scope,
                        "action_label": action_label,
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
