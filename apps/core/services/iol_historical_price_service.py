from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable
import unicodedata

import pandas as pd
from django.db import transaction
from django.db.models import Count, Max

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class IOLHistoricalPriceService:
    """Persistencia minima de historicos diarios por simbolo desde IOL."""

    CASH_MANAGEMENT_SYMBOLS = {"ADBAICA", "IOLPORA", "PRPEDOB"}
    MARKET_ALIASES = {
        "BCBA": ("BCBA", "bCBA", "bcba"),
        "NASDAQ": ("NASDAQ", "nasdaq"),
        "NYSE": ("NYSE", "nyse"),
        "ROFX": ("ROFX", "Rofx", "rofX", "rofx"),
    }

    def __init__(self, client: IOLAPIClient | None = None):
        self.client = client or IOLAPIClient()
        self._title_metadata_cache: dict[tuple[str, str], dict] = {}
        self._fci_metadata_cache: dict[str, dict | None] = {}

    def sync_symbol_history(self, mercado: str, simbolo: str, params: dict | None = None) -> dict:
        support = self.resolve_symbol_history_support(mercado=mercado, simbolo=simbolo)
        if not support.get("supported"):
            return {
                "success": True,
                "skipped": True,
                "simbolo": simbolo,
                "mercado": mercado,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "eligibility_status": support.get("eligibility_status") or "unsupported",
                "error": support.get("reason") or "Instrumento no elegible para históricos IOL",
            }

        resolved_market = str(support.get("mercado") or mercado)
        raw_rows = self.client.get_titulo_historicos(resolved_market, simbolo, params=params)
        if raw_rows is None:
            return {
                "success": False,
                "simbolo": simbolo,
                "mercado": resolved_market,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "eligibility_status": support.get("eligibility_status") or "supported",
                "error": self.client.last_error.get("message") or "IOL historical prices unavailable",
            }

        normalized_rows = self._normalize_rows(raw_rows)
        created = 0
        updated = 0

        with transaction.atomic():
            for row in normalized_rows:
                _, was_created = IOLHistoricalPriceSnapshot.objects.update_or_create(
                    simbolo=simbolo,
                    mercado=resolved_market,
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
            "mercado": resolved_market,
            "rows_received": len(normalized_rows),
            "created": created,
            "updated": updated,
            "latest_date": latest_date,
            "eligibility_status": support.get("eligibility_status") or "supported",
            "error": "",
        }

    def sync_current_portfolio_symbols(self, params: dict | None = None) -> dict:
        latest_positions = self._get_latest_position_rows()
        if not latest_positions:
            return {
                "success": True,
                "symbols_count": 0,
                "processed": 0,
                "results": {},
            }

        results = {}
        processed = 0
        success = True
        for row in latest_positions:
            processed += 1
            result = self.sync_symbol_history(row["mercado"], row["simbolo"], params=params)
            results[f'{row["mercado"]}:{row["simbolo"]}'] = result
            success = success and (bool(result.get("success")) or bool(result.get("skipped")))

        return {
            "success": success,
            "symbols_count": len(latest_positions),
            "processed": processed,
            "results": results,
        }

    def sync_current_portfolio_symbols_by_status(
        self,
        *,
        statuses: tuple[str, ...] = ("missing",),
        minimum_ready_rows: int = 5,
        params: dict | None = None,
    ) -> dict:
        coverage_rows = self.get_current_portfolio_coverage_rows(minimum_ready_rows=minimum_ready_rows)
        selected_rows = [row for row in coverage_rows if row.get("status") in set(statuses)]

        results = {}
        processed = 0
        success = True
        for row in selected_rows:
            processed += 1
            result = self.sync_symbol_history(row["mercado"], row["simbolo"], params=params)
            results[f'{row["mercado"]}:{row["simbolo"]}'] = result
            success = success and (bool(result.get("success")) or bool(result.get("skipped")))

        return {
            "success": success,
            "selected_count": len(selected_rows),
            "processed": processed,
            "statuses": list(statuses),
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
        latest_positions = self._get_latest_position_rows()
        if not latest_positions:
            return []

        coverage_by_symbol = {
            (row["simbolo"], row["mercado"]): row
            for row in IOLHistoricalPriceSnapshot.objects.values("simbolo", "mercado").annotate(
                latest_date=Max("fecha"),
                rows_count=Count("id"),
            )
        }

        rows = []
        for row in latest_positions:
            coverage = coverage_by_symbol.get((row["simbolo"], row["mercado"]), {})
            rows_count = int(coverage.get("rows_count") or 0)
            eligibility = self.classify_position_for_history(row)
            if not eligibility.get("supported"):
                status = "unsupported"
            elif rows_count >= minimum_ready_rows:
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
                    "eligibility_status": eligibility.get("eligibility_status") or status,
                    "eligibility_reason_key": eligibility.get("reason_key") or "",
                    "eligibility_reason": eligibility.get("reason") or "",
                    "minimum_ready_rows": minimum_ready_rows,
                }
            )
        return sorted(rows, key=lambda item: (item["status"], item["simbolo"]))

    def resolve_symbol_history_support(self, *, mercado: str, simbolo: str, row: dict | None = None) -> dict:
        local_row = row or {"simbolo": simbolo, "mercado": mercado}
        local_support = self.classify_position_for_history(local_row)
        if not local_support.get("supported"):
            if local_support.get("eligibility_status") == "unsupported_fci":
                fci_metadata = self._get_fci_metadata(simbolo=simbolo)
                if fci_metadata:
                    return {
                        "supported": False,
                        "mercado": mercado,
                        "simbolo": simbolo,
                        "eligibility_status": "unsupported_fci",
                        "reason_key": "fci_confirmed_by_iol",
                        "reason": "Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos",
                    }
            return local_support

        metadata = self._resolve_titulo_metadata(mercado=mercado, simbolo=simbolo)
        if metadata is None:
            fci_metadata = self._get_fci_metadata(simbolo=simbolo)
            if fci_metadata:
                return {
                    "supported": False,
                    "mercado": mercado,
                    "simbolo": simbolo,
                    "eligibility_status": "unsupported_fci",
                    "reason_key": "fci_confirmed_by_iol",
                    "reason": "Instrumento confirmado por IOL como FCI; no usa seriehistorica de títulos",
                }
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported",
                "reason_key": "title_metadata_unresolved",
                "reason": "IOL no resolvió metadata del instrumento para históricos",
            }

        metadata_support = self.classify_position_for_history(
            {
                "simbolo": simbolo,
                "mercado": metadata.get("mercado") or mercado,
                "tipo": metadata.get("tipo"),
                "descripcion": metadata.get("descripcion"),
            }
        )
        if not metadata_support.get("supported"):
            return metadata_support

        return {
            "supported": True,
            "mercado": str(metadata.get("mercado") or mercado),
            "simbolo": simbolo,
            "eligibility_status": "supported",
            "reason": "",
        }

    def classify_position_for_history(self, row: dict) -> dict:
        simbolo = str(row.get("simbolo") or "").strip()
        mercado = str(row.get("mercado") or "").strip()
        tipo = self._normalize_text(row.get("tipo"))
        descripcion = self._normalize_text(row.get("descripcion"))
        simbolo_norm = self._normalize_text(simbolo)

        if not simbolo or not mercado:
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported",
                "reason_key": "missing_symbol_or_market",
                "reason": "Instrumento sin simbolo o mercado valido",
            }
        if simbolo_norm in self.CASH_MANAGEMENT_SYMBOLS or "FCI" in tipo or "FONDO" in descripcion:
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported_fci",
                "reason_key": "cash_management_local_classification",
                "reason": "FCI y cash management usan un pipeline distinto al de títulos",
            }
        if "CAUCION" in simbolo_norm or "CAUCION" in tipo or "CAUCION" in descripcion:
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported",
                "reason_key": "caucion_not_title_series",
                "reason": "La caución no expone serie histórica de cotización como un título estándar",
            }
        if "DISPONIBLE" in descripcion or "CASH MANAGEMENT" in descripcion or "MONEY MARKET" in descripcion:
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported",
                "reason_key": "cash_like_not_title_series",
                "reason": "El instrumento es cash-like y no se sincroniza como título cotizante",
            }
        return {
            "supported": True,
            "mercado": mercado,
            "simbolo": simbolo,
            "eligibility_status": "supported",
            "reason_key": "",
            "reason": "",
        }

    def _get_titulo_metadata(self, *, mercado: str, simbolo: str) -> dict | None:
        cache_key = (str(mercado or "").strip(), str(simbolo or "").strip().upper())
        if cache_key in self._title_metadata_cache:
            return self._title_metadata_cache[cache_key]

        getter = getattr(self.client, "get_titulo", None)
        if not callable(getter):
            self._title_metadata_cache[cache_key] = {}
            return {}

        metadata = getter(mercado, simbolo)
        self._title_metadata_cache[cache_key] = metadata or None
        return self._title_metadata_cache[cache_key]

    def _get_fci_metadata(self, *, simbolo: str) -> dict | None:
        cache_key = str(simbolo or "").strip().upper()
        if cache_key in self._fci_metadata_cache:
            return self._fci_metadata_cache[cache_key]

        getter = getattr(self.client, "get_fci", None)
        if not callable(getter):
            self._fci_metadata_cache[cache_key] = None
            return None

        metadata = getter(simbolo)
        self._fci_metadata_cache[cache_key] = metadata or None
        return self._fci_metadata_cache[cache_key]

    def _resolve_titulo_metadata(self, *, mercado: str, simbolo: str) -> dict | None:
        for candidate_market in self._candidate_markets(mercado):
            metadata = self._get_titulo_metadata(mercado=candidate_market, simbolo=simbolo)
            if metadata:
                return metadata
        return None

    @staticmethod
    def _get_latest_position_rows() -> list[dict]:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        if not latest_date:
            return []
        return list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
            .exclude(simbolo__isnull=True)
            .exclude(simbolo="")
            .exclude(mercado__isnull=True)
            .exclude(mercado="")
            .values("simbolo", "mercado", "descripcion", "tipo")
            .distinct()
        )

    @staticmethod
    def _normalize_text(value) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(char for char in text if not unicodedata.combining(char))
        return text.upper().strip()

    @classmethod
    def _candidate_markets(cls, mercado: str) -> list[str]:
        raw_market = str(mercado or "").strip()
        if not raw_market:
            return []
        normalized_market = cls._normalize_text(raw_market)
        candidates = list(cls.MARKET_ALIASES.get(normalized_market, (raw_market, normalized_market)))
        if raw_market not in candidates:
            candidates.insert(0, raw_market)
        deduped = []
        seen = set()
        for candidate in candidates:
            key = str(candidate).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped

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
