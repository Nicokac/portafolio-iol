from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import IOLMarketUniverseSnapshot
from apps.core.services.iol_api_client import IOLAPIClient


class IOLMarketUniverseService:
    """Persistencia y lectura del universo de instrumentos y paneles de cotizacion de IOL."""

    SOURCE_KEY = "iol"
    DEFAULT_PAISES = ("argentina",)

    def __init__(self, client: IOLAPIClient | None = None):
        self.client = client or IOLAPIClient()

    def sync_universe(self, *, paises: list[str] | tuple[str, ...] | None = None, captured_at=None) -> dict:
        captured_at = captured_at or timezone.now()
        paises = [self._as_str(pais).lower() for pais in (paises or self.DEFAULT_PAISES) if self._as_str(pais)]
        if not paises:
            return {
                "success": False,
                "countries_processed": 0,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "captured_date": captured_at.date().isoformat(),
                "error": "No countries configured",
            }

        created = 0
        updated = 0
        rows_received = 0
        country_errors: list[dict[str, str]] = []

        with transaction.atomic():
            for pais in paises:
                raw_instruments = self.client.get_quote_instruments(pais)
                if raw_instruments is None:
                    country_errors.append(
                        {
                            "pais": pais,
                            "error": self.client.last_error.get("message") or "Instrument discovery unavailable",
                        }
                    )
                    continue

                normalized_rows = self._normalize_country_rows(
                    pais=pais,
                    raw_instruments=raw_instruments,
                    captured_at=captured_at,
                )
                rows_received += len(normalized_rows)

                for normalized in normalized_rows:
                    _, was_created = IOLMarketUniverseSnapshot.objects.update_or_create(
                        pais=normalized["pais"],
                        instrumento=normalized["instrumento"],
                        panel=normalized["panel"],
                        source=normalized["source"],
                        captured_date=normalized["captured_date"],
                        defaults=normalized,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        return {
            "success": not country_errors and rows_received > 0,
            "countries_processed": len(paises),
            "rows_received": rows_received,
            "created": created,
            "updated": updated,
            "captured_date": captured_at.date().isoformat(),
            "errors": country_errors,
            "error": "; ".join(f"{item['pais']}: {item['error']}" for item in country_errors),
        }

    def list_latest_universe(
        self,
        *,
        pais: str | None = None,
        instrumento: str | None = None,
    ) -> dict:
        latest_date = IOLMarketUniverseSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {"captured_date": None, "count": 0, "countries": []}

        queryset = IOLMarketUniverseSnapshot.objects.filter(captured_date=latest_date).order_by(
            "pais",
            "instrumento",
            "panel",
        )
        if pais:
            queryset = queryset.filter(pais_key=self._normalize_key(pais))
        if instrumento:
            queryset = queryset.filter(instrumento_key=self._normalize_key(instrumento))

        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"pais": "", "instrumentos": []})
        instruments_index: dict[tuple[str, str], dict[str, Any]] = {}

        for row in queryset:
            country_bucket = grouped[row.pais]
            country_bucket["pais"] = row.pais

            key = (row.pais, row.instrumento)
            if key not in instruments_index:
                instruments_index[key] = {
                    "instrumento": row.instrumento,
                    "instrumento_key": row.instrumento_key,
                    "paneles": [],
                    "panel_count": 0,
                    "metadata": {"panel_discovery_status": "empty"},
                }
                country_bucket["instrumentos"].append(instruments_index[key])

            instrument_bucket = instruments_index[key]
            if row.panel:
                instrument_bucket["paneles"].append(
                    {
                        "panel": row.panel,
                        "panel_key": row.panel_key,
                    }
                )
                instrument_bucket["panel_count"] += 1
                instrument_bucket["metadata"]["panel_discovery_status"] = "available"
            else:
                instrument_bucket["metadata"]["panel_discovery_status"] = row.metadata.get(
                    "panel_discovery_status",
                    "empty",
                )

        countries = list(grouped.values())
        instrument_count = sum(len(country["instrumentos"]) for country in countries)
        panel_count = sum(
            instrument["panel_count"]
            for country in countries
            for instrument in country["instrumentos"]
        )
        return {
            "captured_date": latest_date.isoformat(),
            "count": instrument_count,
            "panel_count": panel_count,
            "countries": countries,
        }

    def _normalize_country_rows(self, *, pais: str, raw_instruments: list[dict[str, Any]], captured_at) -> list[dict]:
        normalized_rows: list[dict] = []
        seen_pairs: set[tuple[str, str]] = set()

        for raw_instrument in raw_instruments:
            instrument_name = self._extract_instrument_name(raw_instrument)
            if not instrument_name:
                continue

            raw_panels = self.client.get_quote_panels(pais, instrument_name) or []
            panel_names = self._extract_panel_names(raw_panels, instrument_name=instrument_name)

            if not panel_names:
                key = (instrument_name, "")
                if key not in seen_pairs:
                    normalized_rows.append(
                        self._build_snapshot_row(
                            pais=pais,
                            instrumento=instrument_name,
                            panel="",
                            captured_at=captured_at,
                            metadata={"panel_discovery_status": "empty"},
                        )
                    )
                    seen_pairs.add(key)
                continue

            for panel_name in panel_names:
                key = (instrument_name, panel_name)
                if key in seen_pairs:
                    continue
                normalized_rows.append(
                    self._build_snapshot_row(
                        pais=pais,
                        instrumento=instrument_name,
                        panel=panel_name,
                        captured_at=captured_at,
                        metadata={"panel_discovery_status": "available"},
                    )
                )
                seen_pairs.add(key)

        return normalized_rows

    def _build_snapshot_row(
        self,
        *,
        pais: str,
        instrumento: str,
        panel: str,
        captured_at,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "pais": pais,
            "pais_key": self._normalize_key(pais),
            "instrumento": instrumento,
            "instrumento_key": self._normalize_key(instrumento),
            "panel": panel,
            "panel_key": self._normalize_key(panel),
            "source": self.SOURCE_KEY,
            "captured_at": captured_at,
            "captured_date": captured_at.date(),
            "metadata": metadata,
        }

    @staticmethod
    def _extract_instrument_name(raw_row: dict[str, Any]) -> str:
        return IOLMarketUniverseService._as_str(raw_row.get("instrumento") or raw_row.get("nombre"))

    @staticmethod
    def _extract_panel_names(raw_rows: list[dict[str, Any]], *, instrument_name: str) -> list[str]:
        panel_names: list[str] = []
        seen: set[str] = set()
        instrument_key = IOLMarketUniverseService._normalize_key(instrument_name)

        for raw_row in raw_rows:
            candidate = IOLMarketUniverseService._as_str(
                raw_row.get("panel")
                or raw_row.get("nombre")
                or raw_row.get("identificador")
                or raw_row.get("instrumento")
            )
            if not candidate:
                continue

            candidate_key = IOLMarketUniverseService._normalize_key(candidate)
            if candidate_key == instrument_key:
                continue
            if candidate_key in seen:
                continue
            panel_names.append(candidate)
            seen.add(candidate_key)

        return panel_names

    @staticmethod
    def _as_str(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_key(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return "_".join(part for part in ascii_text.replace("/", " ").split() if part)
