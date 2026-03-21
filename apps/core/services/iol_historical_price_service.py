from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable
import unicodedata

import pandas as pd
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class IOLHistoricalPriceService:
    """Persistencia minima de historicos diarios por simbolo desde IOL."""

    CASH_MANAGEMENT_SYMBOLS = {"ADBAICA", "IOLPORA", "PRPEDOB"}
    MARKET_SNAPSHOT_CACHE_KEY = "iol:current_portfolio_market_snapshot:v1"
    MARKET_SNAPSHOT_CACHE_TTL_SECONDS = 300
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
        latest_positions = self._get_latest_position_rows()
        if not latest_positions:
            return []

        rows = []
        for row in sorted(latest_positions, key=lambda item: (str(item["mercado"]), str(item["simbolo"]))):
            local_support = self.classify_position_for_history(row)
            if not local_support.get("supported"):
                rows.append(
                    {
                        "simbolo": row["simbolo"],
                        "mercado": row["mercado"],
                        "descripcion": row.get("descripcion") or "",
                        "tipo": row.get("tipo") or "",
                        "snapshot_status": "unsupported",
                        "snapshot_source_key": local_support.get("support_source") or "local_classification",
                        "snapshot_source_label": self._build_snapshot_source_label(
                            local_support.get("support_source") or "local_classification"
                        ),
                        "snapshot_reason_key": local_support.get("reason_key") or "",
                        "snapshot_reason": local_support.get("reason") or "",
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
                    }
                )
                continue

            snapshot = self._resolve_market_snapshot(mercado=row["mercado"], simbolo=row["simbolo"])
            if not snapshot:
                rows.append(
                    {
                        "simbolo": row["simbolo"],
                        "mercado": row["mercado"],
                        "descripcion": row.get("descripcion") or "",
                        "tipo": row.get("tipo") or "",
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
                    }
                )
                continue

            first_punta = snapshot["puntas"][0] if isinstance(snapshot.get("puntas"), list) and snapshot.get("puntas") else {}
            best_bid = self._coerce_decimal(first_punta.get("precioCompra"))
            best_ask = self._coerce_decimal(first_punta.get("precioVenta"))
            spread_abs = None
            spread_pct = None
            if best_bid is not None and best_ask is not None and best_bid > 0 and best_ask >= best_bid:
                spread_abs = best_ask - best_bid
                spread_pct = (spread_abs / best_bid) * Decimal("100")

            fecha_hora = snapshot.get("fechaHora")
            rows.append(
                {
                    "simbolo": row["simbolo"],
                    "mercado": str(snapshot.get("mercado") or row["mercado"]),
                    "descripcion": snapshot.get("descripcionTitulo") or row.get("descripcion") or "",
                    "tipo": snapshot.get("tipo") or row.get("tipo") or "",
                    "snapshot_status": "available",
                    "snapshot_source_key": self._infer_market_snapshot_source(snapshot),
                    "snapshot_source_label": self._build_snapshot_source_label(
                        self._infer_market_snapshot_source(snapshot)
                    ),
                    "snapshot_reason_key": "",
                    "snapshot_reason": "",
                    "fecha_hora": fecha_hora,
                    "fecha_hora_label": self._format_snapshot_datetime(fecha_hora),
                    "ultimo_precio": self._coerce_decimal(snapshot.get("ultimoPrecio")),
                    "variacion": self._coerce_decimal(snapshot.get("variacion")),
                    "cantidad_operaciones": self._coerce_int(snapshot.get("cantidadOperaciones")) or 0,
                    "puntas_count": len(snapshot.get("puntas") or []),
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread_abs": spread_abs,
                    "spread_pct": spread_pct,
                    "plazo": str(snapshot.get("plazo") or ""),
                }
            )

        return rows[:limit]

    @staticmethod
    def summarize_market_snapshot_rows(rows: list[dict]) -> dict:
        total = len(rows)
        available_count = sum(1 for row in rows if row.get("snapshot_status") == "available")
        missing_count = sum(1 for row in rows if row.get("snapshot_status") == "missing")
        unsupported_count = sum(1 for row in rows if row.get("snapshot_status") == "unsupported")
        detail_count = sum(1 for row in rows if row.get("snapshot_source_key") == "cotizacion_detalle")
        fallback_count = sum(1 for row in rows if row.get("snapshot_source_key") == "cotizacion")
        order_book_count = sum(1 for row in rows if int(row.get("puntas_count") or 0) > 0)

        if total == 0:
            overall_status = "missing"
        elif missing_count == 0 and unsupported_count == 0:
            overall_status = "ready"
        elif available_count > 0:
            overall_status = "partial"
        else:
            overall_status = "warning"

        return {
            "total_symbols": total,
            "available_count": available_count,
            "missing_count": missing_count,
            "unsupported_count": unsupported_count,
            "detail_count": detail_count,
            "fallback_count": fallback_count,
            "order_book_count": order_book_count,
            "overall_status": overall_status,
        }

    def build_current_portfolio_market_snapshot_payload(self, *, limit: int = 25) -> dict:
        rows = self.get_current_portfolio_market_snapshot_rows(limit=limit)
        return {
            "rows": rows,
            "summary": self.summarize_market_snapshot_rows(rows),
            "refreshed_at": timezone.now().isoformat(),
            "limit": limit,
        }

    def refresh_cached_current_portfolio_market_snapshot(self, *, limit: int = 25) -> dict:
        payload = self.build_current_portfolio_market_snapshot_payload(limit=limit)
        cache.set(
            self.MARKET_SNAPSHOT_CACHE_KEY,
            payload,
            timeout=self.MARKET_SNAPSHOT_CACHE_TTL_SECONDS,
        )
        return payload

    @classmethod
    def get_cached_current_portfolio_market_snapshot(cls) -> dict | None:
        cached = cache.get(cls.MARKET_SNAPSHOT_CACHE_KEY)
        return cached if isinstance(cached, dict) else None

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

    def _get_market_snapshot(self, *, mercado: str, simbolo: str) -> dict | None:
        cache_key = (str(mercado or "").strip(), str(simbolo or "").strip().upper())
        if cache_key in self._market_snapshot_cache:
            return self._market_snapshot_cache[cache_key]

        getter = getattr(self.client, "get_titulo_market_snapshot", None)
        if not callable(getter):
            self._market_snapshot_cache[cache_key] = None
            return None

        snapshot = getter(mercado, simbolo)
        self._market_snapshot_cache[cache_key] = snapshot or None
        return self._market_snapshot_cache[cache_key]

    def _resolve_market_snapshot(self, *, mercado: str, simbolo: str) -> dict | None:
        for candidate_market in self._candidate_markets(mercado):
            snapshot = self._get_market_snapshot(mercado=candidate_market, simbolo=simbolo)
            if snapshot:
                return snapshot
        return None

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
