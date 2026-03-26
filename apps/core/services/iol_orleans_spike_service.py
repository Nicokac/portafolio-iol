from __future__ import annotations

from typing import Any, Callable

from django.conf import settings
from django.utils import timezone

from apps.core.services.iol_api_client import IOLAPIClient
from apps.core.services.iol_market_coverage_service import IOLMarketCoverageService


class IOLOrleansSpikeService:
    """Spike controlado para contrastar Orleans contra la familia estandar de bulk quotes."""

    STANDARD_SOURCE_KEY = "iol_bulk_quotes"
    ORLEANS_SOURCE_KEY = "iol_orleans_bulk_quotes"
    ORLEANS_PANEL_SOURCE_KEY = "iol_orleans_panel_bulk_quotes"

    def __init__(
        self,
        client: IOLAPIClient | None = None,
        coverage_service: IOLMarketCoverageService | None = None,
    ):
        self.client = client or IOLAPIClient()
        self.coverage_service = coverage_service or IOLMarketCoverageService(client=self.client)

    def get_probe(
        self,
        *,
        instrumento: str,
        pais: str,
        include_panel_family: bool = True,
    ) -> dict[str, Any]:
        instrumento_clean = str(instrumento or "").strip()
        pais_clean = str(pais or "").strip().lower()
        if not instrumento_clean or not pais_clean:
            return {
                "instrumento": instrumento_clean,
                "pais": pais_clean,
                "feature_enabled": bool(settings.IOL_ORLEANS_SPIKE_ENABLED),
                "status": "invalid_request",
                "reason": "Instrumento y pais son obligatorios.",
                "baseline": self._empty_probe(self.STANDARD_SOURCE_KEY),
                "orleans": self._empty_probe(self.ORLEANS_SOURCE_KEY),
                "orleans_operables": self._empty_probe(self.ORLEANS_SOURCE_KEY),
                "orleans_panel": self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY),
                "orleans_panel_operables": self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY),
                "comparisons": {},
            }

        if not settings.IOL_ORLEANS_SPIKE_ENABLED:
            return {
                "instrumento": instrumento_clean,
                "pais": pais_clean,
                "feature_enabled": False,
                "status": "disabled",
                "reason": "Spike Orleans deshabilitado por feature flag.",
                "baseline": self._empty_probe(self.STANDARD_SOURCE_KEY),
                "orleans": self._empty_probe(self.ORLEANS_SOURCE_KEY),
                "orleans_operables": self._empty_probe(self.ORLEANS_SOURCE_KEY),
                "orleans_panel": self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY),
                "orleans_panel_operables": self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY),
                "comparisons": {},
            }

        baseline = self._fetch_probe(
            source=self.STANDARD_SOURCE_KEY,
            fetcher=lambda: self.client.get_bulk_quotes(instrumento_clean, pais_clean),
            instrumento=instrumento_clean,
            pais=pais_clean,
        )
        orleans = self._fetch_probe(
            source=self.ORLEANS_SOURCE_KEY,
            fetcher=lambda: self.client.get_orleans_bulk_quotes(instrumento_clean, pais_clean),
            instrumento=instrumento_clean,
            pais=pais_clean,
        )
        orleans_operables = self._fetch_probe(
            source=self.ORLEANS_SOURCE_KEY,
            fetcher=lambda: self.client.get_orleans_operables(instrumento_clean, pais_clean),
            instrumento=instrumento_clean,
            pais=pais_clean,
        )
        if include_panel_family:
            orleans_panel = self._fetch_probe(
                source=self.ORLEANS_PANEL_SOURCE_KEY,
                fetcher=lambda: self.client.get_orleans_panel_bulk_quotes(instrumento_clean, pais_clean),
                instrumento=instrumento_clean,
                pais=pais_clean,
            )
            orleans_panel_operables = self._fetch_probe(
                source=self.ORLEANS_PANEL_SOURCE_KEY,
                fetcher=lambda: self.client.get_orleans_panel_operables(instrumento_clean, pais_clean),
                instrumento=instrumento_clean,
                pais=pais_clean,
            )
        else:
            orleans_panel = self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY)
            orleans_panel_operables = self._empty_probe(self.ORLEANS_PANEL_SOURCE_KEY)

        return {
            "instrumento": instrumento_clean,
            "pais": pais_clean,
            "feature_enabled": True,
            "status": "available",
            "reason": "",
            "baseline": baseline,
            "orleans": orleans,
            "orleans_operables": orleans_operables,
            "orleans_panel": orleans_panel,
            "orleans_panel_operables": orleans_panel_operables,
            "comparisons": {
                "baseline_vs_orleans": self._build_comparison(baseline, orleans),
                "orleans_todos_vs_operables": self._build_comparison(orleans, orleans_operables),
                "orleans_panel_todos_vs_operables": self._build_comparison(orleans_panel, orleans_panel_operables),
            },
        }

    def _fetch_probe(
        self,
        *,
        source: str,
        fetcher: Callable[[], dict[str, Any] | None],
        instrumento: str,
        pais: str,
    ) -> dict[str, Any]:
        payload = fetcher()
        if payload is None:
            status, reason = self._build_remote_status()
            probe = self._empty_probe(source)
            probe["status"] = status
            probe["reason"] = reason
            return probe

        summary = self._summarize_payload(payload=payload, instrumento=instrumento, pais=pais, source=source)
        summary["status"] = "available"
        summary["reason"] = ""
        return summary

    def _summarize_payload(self, *, payload: dict[str, Any], instrumento: str, pais: str, source: str) -> dict[str, Any]:
        captured_at = timezone.now()
        row = self.coverage_service._build_snapshot_row(
            pais=pais,
            instrumento=instrumento,
            payload=payload,
            captured_at=captured_at,
        )
        titles = payload.get("titulos") if isinstance(payload, dict) else []
        symbols = [
            self.coverage_service._as_str(item.get("simbolo"))
            for item in titles
            if self.coverage_service._as_str(item.get("simbolo"))
        ]
        return {
            "source": source,
            "status": "available",
            "reason": "",
            "count": row["total_titles"],
            "symbols_sample": symbols[:10],
            "symbol_set": sorted(set(symbols)),
            "coverage_pct": float(row["coverage_pct"] or 0),
            "order_book_coverage_pct": float(row["order_book_coverage_pct"] or 0),
            "activity_pct": float(row["activity_pct"] or 0),
            "freshness_status": row["freshness_status"],
            "latest_quote_age_minutes": row["latest_quote_age_minutes"],
            "stale_titles": row["stale_titles"],
            "metadata": row["metadata"],
        }

    def _build_remote_status(self) -> tuple[str, str]:
        status_code = self.client.last_error.get("status_code")
        error_type = str(self.client.last_error.get("error_type") or "")
        if status_code == 403:
            return "forbidden", "IOL rechazo el endpoint Orleans con 403."
        if status_code == 401:
            return "unauthorized", "IOL rechazo autenticacion para el endpoint Orleans."
        if error_type:
            return "error", self.client.last_error.get("message") or "Fallo remoto al consultar Orleans."
        return "unavailable", "El endpoint Orleans no devolvio una respuesta usable."

    def _build_comparison(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        left_symbols = set(left.get("symbol_set") or [])
        right_symbols = set(right.get("symbol_set") or [])
        overlap = left_symbols.intersection(right_symbols)
        left_count = int(left.get("count") or 0)
        right_count = int(right.get("count") or 0)
        return {
            "left_status": left.get("status") or "unknown",
            "right_status": right.get("status") or "unknown",
            "left_count": left_count,
            "right_count": right_count,
            "count_delta": right_count - left_count,
            "overlap_count": len(overlap),
            "left_only_count": max(len(left_symbols) - len(overlap), 0),
            "right_only_count": max(len(right_symbols) - len(overlap), 0),
            "overlap_pct_vs_left": self._safe_pct(len(overlap), left_count),
            "overlap_pct_vs_right": self._safe_pct(len(overlap), right_count),
        }

    @staticmethod
    def _safe_pct(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 4)

    @staticmethod
    def _empty_probe(source: str) -> dict[str, Any]:
        return {
            "source": source,
            "status": "empty",
            "reason": "",
            "count": 0,
            "symbols_sample": [],
            "symbol_set": [],
            "coverage_pct": 0.0,
            "order_book_coverage_pct": 0.0,
            "activity_pct": 0.0,
            "freshness_status": "unknown",
            "latest_quote_age_minutes": None,
            "stale_titles": 0,
            "metadata": {},
        }
