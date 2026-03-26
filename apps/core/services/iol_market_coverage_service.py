from __future__ import annotations

import math
import unicodedata
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.models import IOLMarketCoverageSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.core.services.iol_market_universe_service import IOLMarketUniverseService


class IOLMarketCoverageService:
    """Persistencia y lectura del resumen batch de cobertura/freshness por instrumento."""

    SOURCE_KEY = "iol_bulk_quotes"
    DEFAULT_PAISES = ("argentina",)
    RECENT_THRESHOLD_MINUTES = 15
    STALE_THRESHOLD_MINUTES = 60

    def __init__(
        self,
        client: IOLAPIClient | None = None,
        universe_service: IOLMarketUniverseService | None = None,
    ):
        self.client = client or IOLAPIClient()
        self.universe_service = universe_service or IOLMarketUniverseService(client=self.client)

    def sync_coverage(
        self,
        *,
        paises: list[str] | tuple[str, ...] | None = None,
        instrumentos: list[str] | tuple[str, ...] | None = None,
        captured_at=None,
    ) -> dict:
        captured_at = captured_at or timezone.now()
        paises = [self._as_str(pais).lower() for pais in (paises or self.DEFAULT_PAISES) if self._as_str(pais)]
        requested_instruments = [self._as_str(item) for item in (instrumentos or []) if self._as_str(item)]
        if not paises:
            return {
                "success": False,
                "countries_processed": 0,
                "instruments_processed": 0,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "captured_date": captured_at.date().isoformat(),
                "error": "No countries configured",
            }

        created = 0
        updated = 0
        rows_received = 0
        instruments_processed = 0
        errors: list[dict[str, str]] = []

        with transaction.atomic():
            for pais in paises:
                instrument_names = requested_instruments or self._discover_instruments_for_country(pais)
                if not instrument_names:
                    errors.append(
                        {
                            "pais": pais,
                            "instrumento": "",
                            "error": "No instrument universe available for country",
                        }
                    )
                    continue

                for instrumento in instrument_names:
                    payload = self.client.get_bulk_quotes(instrumento, pais)
                    if payload is None:
                        errors.append(
                            {
                                "pais": pais,
                                "instrumento": instrumento,
                                "error": self.client.last_error.get("message") or "Bulk quotes unavailable",
                            }
                        )
                        continue

                    normalized = self._build_snapshot_row(
                        pais=pais,
                        instrumento=instrumento,
                        payload=payload,
                        captured_at=captured_at,
                    )
                    rows_received += int(normalized["total_titles"] or 0)
                    instruments_processed += 1
                    _, was_created = IOLMarketCoverageSnapshot.objects.update_or_create(
                        pais=normalized["pais"],
                        instrumento=normalized["instrumento"],
                        source=normalized["source"],
                        captured_date=normalized["captured_date"],
                        defaults=normalized,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        return {
            "success": not errors and instruments_processed > 0,
            "countries_processed": len(paises),
            "instruments_processed": instruments_processed,
            "rows_received": rows_received,
            "created": created,
            "updated": updated,
            "captured_date": captured_at.date().isoformat(),
            "errors": errors,
            "error": "; ".join(
                f"{item['pais']}:{item.get('instrumento') or '*'}: {item['error']}" for item in errors
            ),
        }

    def list_latest_coverage(
        self,
        *,
        pais: str | None = None,
        instrumento: str | None = None,
    ) -> dict:
        latest_date = IOLMarketCoverageSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {"captured_date": None, "count": 0, "countries": [], "totals": {}}

        queryset = IOLMarketCoverageSnapshot.objects.filter(captured_date=latest_date).order_by("pais", "instrumento")
        if pais:
            queryset = queryset.filter(pais_key=self._normalize_key(pais))
        if instrumento:
            queryset = queryset.filter(instrumento_key=self._normalize_key(instrumento))

        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"pais": "", "instrumentos": []})
        totals = {
            "total_titles": 0,
            "priced_titles": 0,
            "order_book_titles": 0,
            "active_titles": 0,
            "stale_titles": 0,
        }

        for row in queryset:
            country_bucket = grouped[row.pais]
            country_bucket["pais"] = row.pais
            country_bucket["instrumentos"].append(
                {
                    "instrumento": row.instrumento,
                    "instrumento_key": row.instrumento_key,
                    "total_titles": row.total_titles,
                    "priced_titles": row.priced_titles,
                    "order_book_titles": row.order_book_titles,
                    "volume_titles": row.volume_titles,
                    "active_titles": row.active_titles,
                    "recent_titles": row.recent_titles,
                    "stale_titles": row.stale_titles,
                    "zero_price_titles": row.zero_price_titles,
                    "latest_quote_at": self._format_datetime(row.latest_quote_at),
                    "oldest_quote_at": self._format_datetime(row.oldest_quote_at),
                    "latest_quote_age_minutes": row.latest_quote_age_minutes,
                    "oldest_quote_age_minutes": row.oldest_quote_age_minutes,
                    "coverage_pct": float(row.coverage_pct or 0),
                    "order_book_coverage_pct": float(row.order_book_coverage_pct or 0),
                    "activity_pct": float(row.activity_pct or 0),
                    "freshness_status": row.freshness_status,
                    "metadata": row.metadata,
                }
            )

            totals["total_titles"] += int(row.total_titles or 0)
            totals["priced_titles"] += int(row.priced_titles or 0)
            totals["order_book_titles"] += int(row.order_book_titles or 0)
            totals["active_titles"] += int(row.active_titles or 0)
            totals["stale_titles"] += int(row.stale_titles or 0)

        countries = list(grouped.values())
        return {
            "captured_date": latest_date.isoformat(),
            "count": sum(len(country["instrumentos"]) for country in countries),
            "countries": countries,
            "totals": totals,
        }

    def _discover_instruments_for_country(self, pais: str) -> list[str]:
        payload = self.universe_service.list_latest_universe(pais=pais)
        country_rows = payload.get("countries") or []
        if not country_rows:
            return []
        return [self._as_str(row.get("instrumento")) for row in country_rows[0].get("instrumentos", []) if self._as_str(row.get("instrumento"))]

    def _build_snapshot_row(self, *, pais: str, instrumento: str, payload: dict[str, Any], captured_at) -> dict[str, Any]:
        titles = payload.get("titulos") if isinstance(payload, dict) else None
        rows = titles if isinstance(titles, list) else []

        total_titles = len(rows)
        priced_titles = 0
        order_book_titles = 0
        volume_titles = 0
        active_titles = 0
        recent_titles = 0
        stale_titles = 0
        zero_price_titles = 0
        latest_quote_at = None
        oldest_quote_at = None
        stale_samples: list[str] = []

        for row in rows:
            ultimo_precio = self._as_float(row.get("ultimoPrecio"))
            volumen = self._as_float(row.get("volumen"))
            cantidad_operaciones = self._as_int(row.get("cantidadOperaciones"))
            if ultimo_precio > 0:
                priced_titles += 1
            else:
                zero_price_titles += 1
            if volumen > 0:
                volume_titles += 1
            if cantidad_operaciones > 0:
                active_titles += 1

            puntas = row.get("puntas")
            if self._has_visible_order_book(puntas):
                order_book_titles += 1

            quote_at = self._parse_quote_datetime(row.get("fecha"))
            if quote_at is None:
                continue
            if latest_quote_at is None or quote_at > latest_quote_at:
                latest_quote_at = quote_at
            if oldest_quote_at is None or quote_at < oldest_quote_at:
                oldest_quote_at = quote_at

            age_minutes = self._age_minutes(captured_at, quote_at)
            if age_minutes is None:
                continue
            if age_minutes <= self.RECENT_THRESHOLD_MINUTES:
                recent_titles += 1
            if age_minutes > self.STALE_THRESHOLD_MINUTES:
                stale_titles += 1
                if len(stale_samples) < 5:
                    stale_samples.append(self._as_str(row.get("simbolo")))

        latest_age = self._age_minutes(captured_at, latest_quote_at)
        oldest_age = self._age_minutes(captured_at, oldest_quote_at)
        freshness_status = self._build_freshness_status(
            total_titles=total_titles,
            latest_quote_age_minutes=latest_age,
            stale_titles=stale_titles,
        )

        return {
            "pais": pais,
            "pais_key": self._normalize_key(pais),
            "instrumento": instrumento,
            "instrumento_key": self._normalize_key(instrumento),
            "source": self.SOURCE_KEY,
            "captured_at": captured_at,
            "captured_date": captured_at.date(),
            "total_titles": total_titles,
            "priced_titles": priced_titles,
            "order_book_titles": order_book_titles,
            "volume_titles": volume_titles,
            "active_titles": active_titles,
            "recent_titles": recent_titles,
            "stale_titles": stale_titles,
            "zero_price_titles": zero_price_titles,
            "latest_quote_at": latest_quote_at,
            "oldest_quote_at": oldest_quote_at,
            "latest_quote_age_minutes": latest_age,
            "oldest_quote_age_minutes": oldest_age,
            "coverage_pct": self._coverage_percentage(priced_titles, total_titles),
            "order_book_coverage_pct": self._coverage_percentage(order_book_titles, total_titles),
            "activity_pct": self._coverage_percentage(active_titles, total_titles),
            "freshness_status": freshness_status,
            "metadata": {
                "rows_received": total_titles,
                "recent_threshold_minutes": self.RECENT_THRESHOLD_MINUTES,
                "stale_threshold_minutes": self.STALE_THRESHOLD_MINUTES,
                "stale_sample_symbols": stale_samples,
            },
        }

    @staticmethod
    def _has_visible_order_book(puntas: Any) -> bool:
        if isinstance(puntas, dict):
            return any(IOLMarketCoverageService._as_float(puntas.get(key)) > 0 for key in ("precioCompra", "precioVenta"))
        if not isinstance(puntas, list):
            return False
        for row in puntas:
            if isinstance(row, dict) and any(
                IOLMarketCoverageService._as_float(row.get(key)) > 0 for key in ("precioCompra", "precioVenta")
            ):
                return True
        return False

    @classmethod
    def _build_freshness_status(cls, *, total_titles: int, latest_quote_age_minutes: int | None, stale_titles: int) -> str:
        if total_titles <= 0:
            return "empty"
        if latest_quote_age_minutes is None:
            return "unknown"
        if latest_quote_age_minutes <= cls.RECENT_THRESHOLD_MINUTES and stale_titles == 0:
            return "fresh"
        if latest_quote_age_minutes <= cls.STALE_THRESHOLD_MINUTES:
            return "mixed"
        return "stale"

    @staticmethod
    def _parse_quote_datetime(value: Any):
        text = str(value or "").strip()
        if not text:
            return None
        parsed = parse_datetime(text)
        if parsed is None:
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @staticmethod
    def _age_minutes(reference_at, quote_at) -> int | None:
        if reference_at is None or quote_at is None:
            return None
        delta = reference_at - quote_at
        if delta.total_seconds() < 0:
            return 0
        return int(math.floor(delta.total_seconds() / 60))

    @staticmethod
    def _coverage_percentage(numerator: int, denominator: int) -> Decimal:
        if denominator <= 0:
            return Decimal("0")
        return (Decimal(str(numerator)) / Decimal(str(denominator)) * Decimal("100")).quantize(Decimal("0.01"))

    @staticmethod
    def _format_datetime(value) -> str | None:
        if value is None:
            return None
        return timezone.localtime(value).isoformat()

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_str(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_key(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return "_".join(part for part in ascii_text.replace("/", " ").split() if part)
