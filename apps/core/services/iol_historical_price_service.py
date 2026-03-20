from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

import pandas as pd
from django.db import transaction
from django.db.models import Count, Max

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class IOLHistoricalPriceService:
    """Persistencia minima de historicos diarios por simbolo desde IOL."""

    def __init__(self, client: IOLAPIClient | None = None):
        self.client = client or IOLAPIClient()

    def sync_symbol_history(self, mercado: str, simbolo: str, params: dict | None = None) -> dict:
        raw_rows = self.client.get_titulo_historicos(mercado, simbolo, params=params)
        if raw_rows is None:
            return {
                "success": False,
                "simbolo": simbolo,
                "mercado": mercado,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "error": self.client.last_error.get("message") or "IOL historical prices unavailable",
            }

        normalized_rows = self._normalize_rows(raw_rows)
        created = 0
        updated = 0

        with transaction.atomic():
            for row in normalized_rows:
                _, was_created = IOLHistoricalPriceSnapshot.objects.update_or_create(
                    simbolo=simbolo,
                    mercado=mercado,
                    source="iol",
                    fecha=row["fecha"],
                    defaults={
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        latest_date = max((row["fecha"] for row in normalized_rows), default=None)
        return {
            "success": True,
            "simbolo": simbolo,
            "mercado": mercado,
            "rows_received": len(normalized_rows),
            "created": created,
            "updated": updated,
            "latest_date": latest_date,
            "error": "",
        }

    def sync_current_portfolio_symbols(self, params: dict | None = None) -> dict:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        if not latest_date:
            return {
                "success": True,
                "symbols_count": 0,
                "processed": 0,
                "results": {},
            }

        latest_positions = (
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
            .exclude(simbolo__isnull=True)
            .exclude(simbolo="")
            .exclude(mercado__isnull=True)
            .exclude(mercado="")
            .values("simbolo", "mercado")
            .distinct()
        )

        results = {}
        processed = 0
        success = True
        for row in latest_positions:
            processed += 1
            result = self.sync_symbol_history(row["mercado"], row["simbolo"], params=params)
            results[f'{row["mercado"]}:{row["simbolo"]}'] = result
            success = success and bool(result.get("success"))

        return {
            "success": success,
            "symbols_count": int(latest_positions.count()),
            "processed": processed,
            "results": results,
        }

    def build_close_series(self, simbolo: str, mercado: str, dates: Iterable[pd.Timestamp]) -> pd.Series:
        normalized_dates = pd.to_datetime(list(dates))
        if len(normalized_dates) == 0:
            return pd.Series(dtype=float)

        snapshots = IOLHistoricalPriceSnapshot.objects.filter(
            simbolo=simbolo,
            mercado=mercado,
            source="iol",
            fecha__range=(normalized_dates.min().date(), normalized_dates.max().date()),
        ).order_by("fecha")
        if snapshots.count() < 2:
            return pd.Series(dtype=float)

        df = pd.DataFrame(list(snapshots.values("fecha", "close")))
        if df.empty:
            return pd.Series(dtype=float)

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).set_index("fecha").sort_index()
        if len(df.index) < 2:
            return pd.Series(dtype=float)
        return df["close"].reindex(normalized_dates).ffill()

    def get_status_summary(self) -> list[dict]:
        aggregated = {
            (row["simbolo"], row["mercado"]): row
            for row in IOLHistoricalPriceSnapshot.objects.values("simbolo", "mercado").annotate(
                latest_date=Max("fecha"),
                rows_count=Count("id"),
            )
        }
        return [
            {
                "simbolo": simbolo,
                "mercado": mercado,
                "latest_date": row["latest_date"],
                "rows_count": row["rows_count"],
                "is_ready": bool(row["rows_count"] and row["rows_count"] >= 2),
            }
            for (simbolo, mercado), row in aggregated.items()
        ]

    def get_current_portfolio_coverage_rows(self, *, minimum_ready_rows: int = 5) -> list[dict]:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        if not latest_date:
            return []

        coverage_by_symbol = {
            (row["simbolo"], row["mercado"]): row
            for row in IOLHistoricalPriceSnapshot.objects.values("simbolo", "mercado").annotate(
                latest_date=Max("fecha"),
                rows_count=Count("id"),
            )
        }

        latest_positions = (
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
            .exclude(simbolo__isnull=True)
            .exclude(simbolo="")
            .exclude(mercado__isnull=True)
            .exclude(mercado="")
            .values("simbolo", "mercado")
            .distinct()
        )

        rows = []
        for row in latest_positions:
            coverage = coverage_by_symbol.get((row["simbolo"], row["mercado"]), {})
            rows_count = int(coverage.get("rows_count") or 0)
            if rows_count >= minimum_ready_rows:
                status = "ready"
            elif rows_count > 0:
                status = "partial"
            else:
                status = "missing"
            rows.append(
                {
                    "simbolo": row["simbolo"],
                    "mercado": row["mercado"],
                    "rows_count": rows_count,
                    "latest_date": coverage.get("latest_date"),
                    "status": status,
                    "minimum_ready_rows": minimum_ready_rows,
                }
            )
        return sorted(rows, key=lambda item: (item["status"], item["simbolo"]))

    @staticmethod
    def _normalize_rows(raw_rows: list[dict]) -> list[dict]:
        normalized = []
        for row in raw_rows:
            normalized_row = IOLHistoricalPriceService._normalize_row(row)
            if normalized_row is not None:
                normalized.append(normalized_row)
        return normalized

    @staticmethod
    def _normalize_row(row: dict) -> dict | None:
        fecha = IOLHistoricalPriceService._coerce_date(
            row.get("fecha")
            or row.get("fechaHora")
            or row.get("fechaHistorico")
        )
        close = IOLHistoricalPriceService._coerce_decimal(
            row.get("ultimoPrecio")
            or row.get("close")
            or row.get("cierre")
        )
        if fecha is None or close is None:
            return None

        return {
            "fecha": fecha,
            "open": IOLHistoricalPriceService._coerce_decimal(row.get("apertura") or row.get("open")),
            "high": IOLHistoricalPriceService._coerce_decimal(row.get("maximo") or row.get("high")),
            "low": IOLHistoricalPriceService._coerce_decimal(row.get("minimo") or row.get("low")),
            "close": close,
            "volume": IOLHistoricalPriceService._coerce_int(
                row.get("volumenNominal")
                or row.get("volumenNominalTotal")
                or row.get("volume")
                or row.get("volumen")
            ),
        }

    @staticmethod
    def _coerce_date(value) -> date | None:
        if value in (None, ""):
            return None
        try:
            return pd.to_datetime(value).date()
        except Exception:
            return None

    @staticmethod
    def _coerce_decimal(value) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _coerce_int(value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except Exception:
            return None
