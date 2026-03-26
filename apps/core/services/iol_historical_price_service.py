from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable
import unicodedata

import pandas as pd
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.parametros.models import ParametroActivo
from apps.core.services.iol_market_snapshot_support import (
    build_current_portfolio_market_snapshot_payload,
    build_current_portfolio_market_plazo_comparison_payload_from_observations,
    get_cached_current_portfolio_market_snapshot,
    get_current_portfolio_market_snapshot_rows,
    get_current_portfolio_market_snapshot_rows_by_plazo,
    get_latest_position_rows,
    get_recent_market_history_rows,
    persist_market_snapshot_payload,
    refresh_and_persist_current_portfolio_market_snapshot,
    refresh_cached_current_portfolio_market_snapshot,
    summarize_market_snapshot_rows,
    summarize_recent_market_history_rows,
)


class IOLHistoricalPriceService:
    """Persistencia minima de historicos diarios por simbolo desde IOL."""

    CASH_MANAGEMENT_SYMBOLS = {"ADBAICA", "IOLPORA", "PRPEDOB"}
    YFINANCE_SUPPORTED_PATRIMONIAL_TYPES = {"EQUITY", "ETF"}
    MARKET_SNAPSHOT_CACHE_KEY = "iol:current_portfolio_market_snapshot:v1"
    MARKET_SNAPSHOT_CACHE_TTL_SECONDS = 300
    MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS = 7
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
        self._market_snapshot_cache: dict[tuple[str, str], dict | None] = {}
        self._parametro_cache: dict[str, ParametroActivo | None] = {}

    def sync_symbol_history(
        self,
        mercado: str,
        simbolo: str,
        params: dict | None = None,
        row: dict | None = None,
    ) -> dict:
        yfinance_support = self.resolve_symbol_history_support_via_yfinance(
            mercado=mercado,
            simbolo=simbolo,
            row=row,
        )
        if yfinance_support.get("supported"):
            return self._sync_symbol_history_from_yfinance(
                mercado=mercado,
                simbolo=simbolo,
                params=params,
                yfinance_support=yfinance_support,
            )

        support = self.resolve_symbol_history_support(mercado=mercado, simbolo=simbolo, row=row)
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
            result = self.sync_symbol_history(
                row["mercado"],
                row["simbolo"],
                params=params,
                row=row,
            )
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
        eligibility_reason_keys: tuple[str, ...] | None = None,
        params: dict | None = None,
    ) -> dict:
        coverage_rows = self.get_current_portfolio_coverage_rows(minimum_ready_rows=minimum_ready_rows)
        selected_rows = [row for row in coverage_rows if row.get("status") in set(statuses)]
        if eligibility_reason_keys:
            selected_rows = [
                row
                for row in selected_rows
                if row.get("eligibility_reason_key") in set(eligibility_reason_keys)
            ]

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
            "eligibility_reason_keys": list(eligibility_reason_keys or ()),
            "results": results,
        }

    def build_close_series(self, simbolo: str, mercado: str, dates: Iterable[pd.Timestamp]) -> pd.Series:
        normalized_dates = pd.to_datetime(list(dates))
        if len(normalized_dates) == 0:
            return pd.Series(dtype=float)

        snapshots = IOLHistoricalPriceSnapshot.objects.filter(
            simbolo=simbolo,
            mercado=mercado,
            fecha__range=(normalized_dates.min().date(), normalized_dates.max().date()),
        ).order_by("fecha", "source")
        if snapshots.count() < 2:
            return pd.Series(dtype=float)

        df = pd.DataFrame(list(snapshots.values("fecha", "close")))
        if df.empty:
            return pd.Series(dtype=float)

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = (
            df.dropna(subset=["close"])
            .drop_duplicates(subset=["fecha"], keep="first")
            .set_index("fecha")
            .sort_index()
        )
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
            eligibility = self.resolve_symbol_history_support(
                mercado=row["mercado"],
                simbolo=row["simbolo"],
                row=row,
            )
            if not eligibility.get("supported"):
                status = "unsupported"
            elif rows_count >= minimum_ready_rows:
                status = "ready"
            elif rows_count > 0:
                status = "partial"
            else:
                status = "missing"
            source_key = self._resolve_support_source_key(eligibility)
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
                    "eligibility_source_key": source_key,
                    "eligibility_source_label": self._build_support_source_label(source_key),
                    "minimum_ready_rows": minimum_ready_rows,
                }
            )
        return sorted(rows, key=lambda item: (item["status"], item["simbolo"]))

    def get_current_portfolio_market_snapshot_rows(self, *, limit: int = 10) -> list[dict]:
        return get_current_portfolio_market_snapshot_rows(self, limit=limit)

    def get_current_portfolio_market_snapshot_rows_by_plazo(self, *, plazo: str = "t1", limit: int = 10) -> list[dict]:
        return get_current_portfolio_market_snapshot_rows_by_plazo(self, plazo=plazo, limit=limit)

    @staticmethod
    def summarize_market_snapshot_rows(rows: list[dict]) -> dict:
        return summarize_market_snapshot_rows(rows)

    def build_current_portfolio_market_snapshot_payload(self, *, limit: int = 25) -> dict:
        return build_current_portfolio_market_snapshot_payload(self, limit=limit)

    def refresh_cached_current_portfolio_market_snapshot(self, *, limit: int = 25) -> dict:
        return refresh_cached_current_portfolio_market_snapshot(self, limit=limit)

    def refresh_and_persist_current_portfolio_market_snapshot(self, *, limit: int = 25) -> dict:
        return refresh_and_persist_current_portfolio_market_snapshot(self, limit=limit)

    @classmethod
    def get_cached_current_portfolio_market_snapshot(cls) -> dict | None:
        return get_cached_current_portfolio_market_snapshot(
            cls.MARKET_SNAPSHOT_CACHE_KEY,
            service=cls(),
        )

    def persist_market_snapshot_payload(self, payload: dict | None) -> dict:
        return persist_market_snapshot_payload(self, payload)

    def build_current_portfolio_market_plazo_comparison_payload(
        self,
        *,
        limit: int = 25,
        lookback_days: int | None = None,
    ) -> dict:
        return build_current_portfolio_market_plazo_comparison_payload_from_observations(
            self,
            limit=limit,
            lookback_days=lookback_days,
        )

    def get_recent_market_history_rows(self, *, lookback_days: int | None = None) -> list[dict]:
        return get_recent_market_history_rows(self, lookback_days=lookback_days)

    @staticmethod
    def summarize_recent_market_history_rows(rows: list[dict]) -> dict:
        return summarize_recent_market_history_rows(rows)

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
            local_support["support_source"] = local_support.get("support_source") or "local_classification"
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
                    "reason": "Instrumento confirmado por IOL como FCI; no usa seriehistorica de t?tulos",
                    "support_source": "fci_confirmation",
                }
            market_snapshot = self._resolve_market_snapshot(mercado=mercado, simbolo=simbolo)
            if market_snapshot:
                snapshot_support = self.classify_position_for_history(
                    {
                        "simbolo": market_snapshot.get("simbolo") or simbolo,
                        "mercado": market_snapshot.get("mercado") or mercado,
                        "tipo": market_snapshot.get("tipo"),
                        "descripcion": market_snapshot.get("descripcionTitulo"),
                    }
                )
                if snapshot_support.get("supported"):
                    return {
                        "supported": True,
                        "mercado": str(market_snapshot.get("mercado") or mercado),
                        "simbolo": simbolo,
                        "eligibility_status": "supported",
                        "reason": "",
                        "support_source": "market_snapshot",
                    }
                snapshot_support["support_source"] = snapshot_support.get("support_source") or "market_snapshot"
                return snapshot_support
            return {
                "supported": False,
                "mercado": mercado,
                "simbolo": simbolo,
                "eligibility_status": "unsupported",
                "reason_key": "title_metadata_unresolved",
                "reason": "IOL no resolvi? metadata del instrumento para hist?ricos",
                "support_source": "unresolved",
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
            "support_source": "title_metadata",
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
                "support_source": "local_classification",
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
            "support_source": "local_classification",
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

    def _get_market_snapshot(self, *, mercado: str, simbolo: str, params: dict | None = None) -> dict | None:
        plazo = str((params or {}).get("plazo") or (params or {}).get("model.plazo") or "t1").strip().lower()
        cache_key = (str(mercado or "").strip(), str(simbolo or "").strip().upper(), plazo)
        if cache_key in self._market_snapshot_cache:
            return self._market_snapshot_cache[cache_key]

        getter = getattr(self.client, "get_titulo_market_snapshot", None)
        if not callable(getter):
            self._market_snapshot_cache[cache_key] = None
            return None

        snapshot = getter(mercado, simbolo, params=params)
        self._market_snapshot_cache[cache_key] = snapshot or None
        return self._market_snapshot_cache[cache_key]

    def _resolve_market_snapshot(self, *, mercado: str, simbolo: str, params: dict | None = None) -> dict | None:
        for candidate_market in self._candidate_markets(mercado):
            snapshot = self._get_market_snapshot(mercado=candidate_market, simbolo=simbolo, params=params)
            if snapshot:
                return snapshot
        return None

    def resolve_symbol_history_support_via_yfinance(
        self,
        *,
        mercado: str,
        simbolo: str,
        row: dict | None = None,
    ) -> dict:
        simbolo_clean = str(simbolo or "").strip().upper()
        if not simbolo_clean:
            return {"supported": False, "provider": "", "ticker": ""}

        parametro = self._get_parametro_activo(simbolo_clean)
        tipo_patrimonial = self._normalize_text(getattr(parametro, "tipo_patrimonial", ""))
        row_tipo = self._normalize_text((row or {}).get("tipo"))
        is_supported_type = (
            tipo_patrimonial in self.YFINANCE_SUPPORTED_PATRIMONIAL_TYPES
            or "CEDEAR" in row_tipo
            or "ACCION" in row_tipo
            or "ETF" in row_tipo
        )
        if not is_supported_type:
            return {"supported": False, "provider": "", "ticker": ""}

        normalized_market = self._normalize_text(mercado)
        ticker = ""
        if normalized_market == "BCBA":
            ticker = f"{simbolo_clean}.BA"
        elif normalized_market in {"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "ARCA"}:
            ticker = simbolo_clean

        if not ticker:
            return {"supported": False, "provider": "", "ticker": ""}

        return {
            "supported": True,
            "provider": "yfinance",
            "ticker": ticker,
            "mercado": mercado,
            "simbolo": simbolo_clean,
        }

    def _sync_symbol_history_from_yfinance(
        self,
        *,
        mercado: str,
        simbolo: str,
        params: dict | None,
        yfinance_support: dict,
    ) -> dict:
        raw_rows = self._get_yfinance_historical_rows(
            ticker=str(yfinance_support.get("ticker") or "").strip(),
            params=params,
        )
        if raw_rows is None:
            return {
                "success": False,
                "simbolo": simbolo,
                "mercado": mercado,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "eligibility_status": "supported",
                "error": "Yahoo Finance historical prices unavailable",
                "source": "yfinance",
            }

        normalized_rows = self._normalize_rows(raw_rows)
        created = 0
        updated = 0

        with transaction.atomic():
            for row in normalized_rows:
                _, was_created = IOLHistoricalPriceSnapshot.objects.update_or_create(
                    simbolo=simbolo,
                    mercado=mercado,
                    source="yfinance",
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
            "eligibility_status": "supported",
            "error": "",
            "source": "yfinance",
            "provider_ticker": yfinance_support.get("ticker") or "",
        }

    def _get_yfinance_historical_rows(self, *, ticker: str, params: dict | None = None) -> list[dict] | None:
        try:
            import yfinance as yf
        except ImportError:
            return None

        start_date, end_date = self._resolve_history_window(params)
        history = yf.Ticker(ticker).history(
            start=start_date.isoformat(),
            end=(pd.Timestamp(end_date) + pd.Timedelta(days=1)).date().isoformat(),
            auto_adjust=False,
        )
        if history is None or history.empty:
            return None

        rows = []
        for index, values in history.iterrows():
            rows.append(
                {
                    "fecha": pd.to_datetime(index).date(),
                    "open": values.get("Open"),
                    "high": values.get("High"),
                    "low": values.get("Low"),
                    "close": values.get("Close"),
                    "volume": values.get("Volume"),
                }
            )
        return rows

    @staticmethod
    def _resolve_history_window(params: dict | None = None) -> tuple[date, date]:
        params = params or {}
        today = date.today()
        default_start = (pd.Timestamp(today) - pd.Timedelta(days=365)).date()
        start_date = IOLHistoricalPriceService._coerce_date(
            params.get("fecha_desde") or params.get("fechaDesde") or params.get("desde") or default_start
        )
        end_date = IOLHistoricalPriceService._coerce_date(
            params.get("fecha_hasta") or params.get("fechaHasta") or params.get("hasta") or today
        )
        return start_date or default_start, end_date or today

    def _get_parametro_activo(self, simbolo: str) -> ParametroActivo | None:
        cache_key = str(simbolo or "").strip().upper()
        if cache_key not in self._parametro_cache:
            self._parametro_cache[cache_key] = ParametroActivo.objects.filter(simbolo=cache_key).first()
        return self._parametro_cache[cache_key]

    @staticmethod
    def _build_support_source_label(source_key: str | None) -> str:
        labels = {
            "title_metadata": "Metadata de titulo",
            "market_snapshot": "Market snapshot",
            "local_classification": "Clasificacion local",
            "fci_confirmation": "Confirmacion FCI",
            "unresolved": "Sin resolucion remota",
        }
        return labels.get(str(source_key or ""), "")

    @staticmethod
    def _build_snapshot_source_label(source_key: str | None) -> str:
        labels = {
            "cotizacion_detalle_mobile": "CotizacionDetalleMobile",
            "cotizacion_detalle": "CotizacionDetalle",
            "cotizacion": "Cotizacion fallback",
            "local_classification": "Clasificacion local",
        }
        return labels.get(str(source_key or ""), "")

    @staticmethod
    def _resolve_support_source_key(eligibility: dict) -> str:
        source_key = str(eligibility.get("support_source") or "").strip()
        if source_key:
            return source_key

        reason_key = str(eligibility.get("reason_key") or "").strip()
        if reason_key == "fci_confirmed_by_iol":
            return "fci_confirmation"
        if reason_key == "title_metadata_unresolved":
            return "unresolved"
        return "local_classification"

    @staticmethod
    def _infer_market_snapshot_source(snapshot: dict) -> str:
        explicit_source = str(snapshot.get("_snapshot_source_key") or "").strip()
        if explicit_source:
            return explicit_source
        detail_keys = {"simbolo", "pais", "mercado", "tipo", "cantidadMinima", "puntosVariacion"}
        if any(key in snapshot for key in detail_keys):
            return "cotizacion_detalle"
        return "cotizacion"

    @staticmethod
    def _format_snapshot_datetime(value) -> str:
        if not value:
            return ""
        try:
            parsed = pd.Timestamp(pd.to_datetime(value)).to_pydatetime(warn=False)
        except Exception:
            return str(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return timezone.localtime(parsed).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _get_latest_position_rows() -> list[dict]:
        return get_latest_position_rows()

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
    def _coerce_datetime(value):
        if value in (None, ""):
            return None
        try:
            parsed = pd.Timestamp(pd.to_datetime(value)).to_pydatetime(warn=False)
        except Exception:
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return timezone.localtime(parsed)

    @staticmethod
    def _coerce_int(value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    @staticmethod
    def _average_decimal(values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        total = sum(values, Decimal("0"))
        return total / Decimal(len(values))

    @staticmethod
    def _average_int(values: list[int]) -> int | None:
        if not values:
            return None
        return int(round(sum(values) / len(values)))

    @staticmethod
    def _coverage_percentage(numerator: int, denominator: int) -> Decimal:
        if denominator <= 0:
            return Decimal("0")
        return (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"))

    @staticmethod
    def _classify_recent_market_quality(
        *,
        observations_count: int,
        avg_spread_pct: Decimal | None,
        avg_operations: int | None,
        order_book_coverage_pct: Decimal,
    ) -> str:
        if observations_count < 2:
            return "insufficient"
        if (
            (avg_spread_pct is not None and avg_spread_pct >= Decimal("1.50"))
            or order_book_coverage_pct < Decimal("50")
            or (avg_operations is not None and avg_operations < 100)
        ):
            return "weak"
        if (
            (avg_spread_pct is not None and avg_spread_pct >= Decimal("0.75"))
            or order_book_coverage_pct < Decimal("75")
            or (avg_operations is not None and avg_operations < 300)
        ):
            return "watch"
        return "strong"

    @staticmethod
    def _build_recent_market_quality_label(status: str) -> str:
        labels = {
            "strong": "Favorable",
            "watch": "Mixta",
            "weak": "Debil",
            "insufficient": "Sin historico suficiente",
        }
        return labels.get(status, "Sin historico suficiente")

    @staticmethod
    def _build_recent_market_quality_summary(
        *,
        quality_status: str,
        avg_spread_pct: Decimal | None,
        avg_operations: int | None,
        order_book_coverage_pct: Decimal,
    ) -> str:
        if quality_status == "insufficient":
            return "Todavia no hay suficiente historial puntual para evaluar spread y actividad reciente."
        spread_text = (
            f"spread medio {avg_spread_pct.quantize(Decimal('0.01'))}%"
            if avg_spread_pct is not None
            else "spread medio N/D"
        )
        ops_text = f"ops medias {avg_operations}" if avg_operations is not None else "ops medias N/D"
        book_text = f"libro visible {order_book_coverage_pct}%"
        return f"{spread_text}, {ops_text}, {book_text}."
