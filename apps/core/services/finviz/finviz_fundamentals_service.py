from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import FinvizFundamentalsSnapshot
from apps.core.services.finviz.finviz_client import FinvizClient
from apps.core.services.finviz.finviz_mapping_service import FinvizMappingService


class FinvizFundamentalsService:
    """Sincroniza y expone snapshots diarios de fundamentals Finviz."""

    SOURCE_KEY = "finviz"
    FIELD_MAP = {
        "Market Cap": "market_cap",
        "Price": "price",
        "Change": "change_pct",
        "Volume": "volume",
        "Beta": "beta",
        "P/E": "pe",
        "Fwd P/E": "fwd_pe",
        "PEG": "peg",
        "P/S": "ps",
        "P/B": "pb",
        "P/C": "pc",
        "P/FCF": "pfcf",
        "EPS This Y": "eps_this_y",
        "EPS Next Y": "eps_next_y",
        "EPS Past 5Y": "eps_past_5y",
        "EPS Next 5Y": "eps_next_5y",
        "Sales Past 5Y": "sales_past_5y",
        "ROA": "roa",
        "ROE": "roe",
        "ROIC": "roic",
        "Curr R": "curr_r",
        "Quick R": "quick_r",
        "LTDebt/Eq": "lt_debt_eq",
        "Debt/Eq": "debt_eq",
        "Gross M": "gross_m",
        "Oper M": "oper_m",
        "Profit M": "profit_m",
        "Dividend": "dividend",
    }
    PRIORITY_FIELDS = (
        "fwd_pe",
        "peg",
        "eps_next_y",
        "eps_next_5y",
        "sales_past_5y",
        "roic",
        "oper_m",
        "profit_m",
        "debt_eq",
        "quick_r",
        "beta",
        "change_pct",
        "volume",
    )

    def __init__(
        self,
        *,
        client: FinvizClient | None = None,
        mapping_service: FinvizMappingService | None = None,
    ):
        self.client = client or FinvizClient()
        self.mapping_service = mapping_service or FinvizMappingService()

    def sync_fundamentals(
        self,
        *,
        scope: str = "metadata",
        symbols: list[str] | None = None,
        captured_at=None,
    ) -> dict:
        captured_at = captured_at or timezone.now()
        mapped_rows = self._get_mapped_rows(scope=scope, symbols=symbols)
        created = 0
        updated = 0
        ok = 0
        errors = 0

        with transaction.atomic():
            for row in mapped_rows:
                raw_payload = self.client.get_fundamentals(row["finviz_symbol"])
                normalized = self._build_snapshot_defaults(
                    row=row,
                    raw_payload=raw_payload,
                    captured_at=captured_at,
                )
                _, was_created = FinvizFundamentalsSnapshot.objects.update_or_create(
                    internal_symbol=row["internal_symbol"],
                    source=self.SOURCE_KEY,
                    captured_date=normalized["captured_date"],
                    defaults=normalized,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

                if normalized["source_status"] == "ok":
                    ok += 1
                else:
                    errors += 1

        return {
            "success": True,
            "scope": scope,
            "symbols_requested": len(symbols or []),
            "mapped_assets": len(mapped_rows),
            "created": created,
            "updated": updated,
            "ok": ok,
            "errors": errors,
            "captured_date": captured_at.date().isoformat(),
        }

    def list_latest_snapshots(self, *, symbols: list[str] | None = None, limit: int | None = None) -> dict:
        latest_date = FinvizFundamentalsSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {"captured_date": None, "count": 0, "items": []}

        queryset = FinvizFundamentalsSnapshot.objects.filter(captured_date=latest_date).order_by("internal_symbol")
        if symbols:
            normalized_symbols = [str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()]
            queryset = queryset.filter(internal_symbol__in=normalized_symbols)
        if limit:
            queryset = queryset[:limit]

        items = [self._serialize_snapshot(item) for item in queryset]
        return {"captured_date": latest_date.isoformat(), "count": len(items), "items": items}

    def _get_mapped_rows(self, *, scope: str, symbols: list[str] | None) -> list[dict[str, Any]]:
        if scope == "portfolio":
            summary = self.mapping_service.build_current_portfolio_summary()
        else:
            summary = self.mapping_service.build_metadata_universe_summary(symbols=symbols)

        rows = [row for row in summary["rows"] if row["status"] == "mapped"]
        if symbols and scope == "portfolio":
            requested = {str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()}
            rows = [row for row in rows if row["internal_symbol"] in requested]
        return rows

    def _build_snapshot_defaults(self, *, row: dict[str, Any], raw_payload: dict[str, Any] | None, captured_at) -> dict[str, Any]:
        defaults = {
            "internal_symbol": row["internal_symbol"],
            "finviz_symbol": row["finviz_symbol"] or "",
            "source": self.SOURCE_KEY,
            "captured_at": captured_at,
            "captured_date": captured_at.date(),
            "source_status": "ok" if raw_payload else "error",
            "data_quality": "missing",
            "mapped_reason": row["reason"] or "",
            "tipo_patrimonial": row.get("tipo_patrimonial") or "",
            "sector": row.get("sector") or "",
            "country": row.get("country") or "",
            "strategic_bucket": row.get("strategic_bucket") or "",
            "raw_payload": raw_payload or {},
            "metadata": {
                "mapping_scope_source": row.get("source") or "",
                "client_error": self.client.last_error if not raw_payload else {},
            },
        }

        if not raw_payload:
            return defaults

        for source_field, target_field in self.FIELD_MAP.items():
            value = raw_payload.get(source_field)
            defaults[target_field] = self._normalize_value(target_field, value)

        defaults["data_quality"] = self._compute_data_quality(defaults)
        return defaults

    def _compute_data_quality(self, normalized: dict[str, Any]) -> str:
        populated = sum(1 for field in self.PRIORITY_FIELDS if normalized.get(field) is not None)
        if populated >= 10:
            return "full"
        if populated >= 4:
            return "partial"
        if populated >= 1:
            return "sparse"
        return "missing"

    def _serialize_snapshot(self, snapshot: FinvizFundamentalsSnapshot) -> dict:
        return {
            "internal_symbol": snapshot.internal_symbol,
            "finviz_symbol": snapshot.finviz_symbol,
            "source_status": snapshot.source_status,
            "data_quality": snapshot.data_quality,
            "mapped_reason": snapshot.mapped_reason,
            "tipo_patrimonial": snapshot.tipo_patrimonial,
            "sector": snapshot.sector,
            "country": snapshot.country,
            "strategic_bucket": snapshot.strategic_bucket,
            "market_cap": float(snapshot.market_cap) if snapshot.market_cap is not None else None,
            "price": float(snapshot.price) if snapshot.price is not None else None,
            "change_pct": float(snapshot.change_pct) if snapshot.change_pct is not None else None,
            "volume": snapshot.volume,
            "beta": float(snapshot.beta) if snapshot.beta is not None else None,
            "pe": float(snapshot.pe) if snapshot.pe is not None else None,
            "fwd_pe": float(snapshot.fwd_pe) if snapshot.fwd_pe is not None else None,
            "peg": float(snapshot.peg) if snapshot.peg is not None else None,
            "ps": float(snapshot.ps) if snapshot.ps is not None else None,
            "pb": float(snapshot.pb) if snapshot.pb is not None else None,
            "pc": float(snapshot.pc) if snapshot.pc is not None else None,
            "pfcf": float(snapshot.pfcf) if snapshot.pfcf is not None else None,
            "eps_this_y": float(snapshot.eps_this_y) if snapshot.eps_this_y is not None else None,
            "eps_next_y": float(snapshot.eps_next_y) if snapshot.eps_next_y is not None else None,
            "eps_past_5y": float(snapshot.eps_past_5y) if snapshot.eps_past_5y is not None else None,
            "eps_next_5y": float(snapshot.eps_next_5y) if snapshot.eps_next_5y is not None else None,
            "sales_past_5y": float(snapshot.sales_past_5y) if snapshot.sales_past_5y is not None else None,
            "roa": float(snapshot.roa) if snapshot.roa is not None else None,
            "roe": float(snapshot.roe) if snapshot.roe is not None else None,
            "roic": float(snapshot.roic) if snapshot.roic is not None else None,
            "curr_r": float(snapshot.curr_r) if snapshot.curr_r is not None else None,
            "quick_r": float(snapshot.quick_r) if snapshot.quick_r is not None else None,
            "lt_debt_eq": float(snapshot.lt_debt_eq) if snapshot.lt_debt_eq is not None else None,
            "debt_eq": float(snapshot.debt_eq) if snapshot.debt_eq is not None else None,
            "gross_m": float(snapshot.gross_m) if snapshot.gross_m is not None else None,
            "oper_m": float(snapshot.oper_m) if snapshot.oper_m is not None else None,
            "profit_m": float(snapshot.profit_m) if snapshot.profit_m is not None else None,
            "dividend": float(snapshot.dividend) if snapshot.dividend is not None else None,
            "metadata": snapshot.metadata or {},
        }

    def _normalize_value(self, target_field: str, value: Any) -> Decimal | int | None:
        if target_field == "market_cap":
            return self._parse_compact_number(value)
        if target_field == "volume":
            compact = self._parse_compact_number(value)
            return int(compact) if compact is not None else None
        if target_field in {
            "change_pct",
            "eps_this_y",
            "eps_next_y",
            "eps_past_5y",
            "eps_next_5y",
            "sales_past_5y",
            "roa",
            "roe",
            "roic",
            "gross_m",
            "oper_m",
            "profit_m",
            "dividend",
        }:
            return self._parse_percent(value)
        return self._parse_decimal(value)

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        if value in (None, "", "-", "N/A"):
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, TypeError):
            return None

    def _parse_percent(self, value: Any) -> Decimal | None:
        if value in (None, "", "-", "N/A"):
            return None
        return self._parse_decimal(str(value).replace("%", ""))

    def _parse_compact_number(self, value: Any) -> Decimal | None:
        if value in (None, "", "-", "N/A"):
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None

        multipliers = {
            "K": Decimal("1000"),
            "M": Decimal("1000000"),
            "B": Decimal("1000000000"),
            "T": Decimal("1000000000000"),
        }
        suffix = text[-1].upper()
        if suffix in multipliers:
            base = self._parse_decimal(text[:-1])
            if base is None:
                return None
            return base * multipliers[suffix]
        return self._parse_decimal(text)
