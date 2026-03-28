from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db.models import Max

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


FINVIZ_SYMBOL_OVERRIDES = {
    "BRKB": "BRK-B",
    "DISN": "DIS",
    "TECO2": "TEO",
    "YPFD": "YPF",
}

SUPPORTED_TIPO_PATRIMONIAL = {"equity", "etf"}


@dataclass(frozen=True)
class FinvizMappingResult:
    internal_symbol: str
    finviz_symbol: str | None
    status: str
    reason: str
    tipo_patrimonial: str | None = None
    sector: str | None = None
    country: str | None = None
    strategic_bucket: str | None = None
    source: str = "metadata"


class FinvizMappingService:
    """Resuelve y audita mapping entre simbolos internos y tickers compatibles con Finviz."""

    def resolve_from_metadata(self, parametro: ParametroActivo | None) -> FinvizMappingResult:
        if parametro is None:
            return FinvizMappingResult(
                internal_symbol="",
                finviz_symbol=None,
                status="missing_metadata",
                reason="metadata_missing",
            )

        symbol = (parametro.simbolo or "").upper().strip()
        tipo_patrimonial = (parametro.tipo_patrimonial or "").strip()
        normalized_tipo = tipo_patrimonial.lower()

        if not symbol:
            return FinvizMappingResult(
                internal_symbol="",
                finviz_symbol=None,
                status="missing_symbol",
                reason="empty_symbol",
                tipo_patrimonial=tipo_patrimonial or None,
                sector=parametro.sector or None,
                country=parametro.pais_exposicion or None,
                strategic_bucket=parametro.bloque_estrategico or None,
            )

        if normalized_tipo not in SUPPORTED_TIPO_PATRIMONIAL:
            return FinvizMappingResult(
                internal_symbol=symbol,
                finviz_symbol=None,
                status="out_of_scope",
                reason=f"unsupported_tipo_patrimonial:{tipo_patrimonial or 'unknown'}",
                tipo_patrimonial=tipo_patrimonial or None,
                sector=parametro.sector or None,
                country=parametro.pais_exposicion or None,
                strategic_bucket=parametro.bloque_estrategico or None,
            )

        finviz_symbol = FINVIZ_SYMBOL_OVERRIDES.get(symbol, symbol)
        reason = "manual_override" if finviz_symbol != symbol else "identity_mapping"

        return FinvizMappingResult(
            internal_symbol=symbol,
            finviz_symbol=finviz_symbol,
            status="mapped",
            reason=reason,
            tipo_patrimonial=tipo_patrimonial or None,
            sector=parametro.sector or None,
            country=parametro.pais_exposicion or None,
            strategic_bucket=parametro.bloque_estrategico or None,
        )

    def build_metadata_universe_summary(self, *, symbols: Iterable[str] | None = None) -> dict:
        queryset = ParametroActivo.objects.all().order_by("simbolo")
        if symbols:
            normalized = [str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()]
            queryset = queryset.filter(simbolo__in=normalized)

        rows = [self.resolve_from_metadata(parametro) for parametro in queryset]
        return self._build_summary(rows=rows, scope="metadata_universe")

    def build_current_portfolio_summary(self) -> dict:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        if not latest_date:
            return self._build_summary(rows=[], scope="current_portfolio")

        portfolio_rows = (
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
            .order_by("simbolo")
        )
        symbols = [row.simbolo.upper().strip() for row in portfolio_rows if (row.simbolo or "").strip()]
        metadata_by_symbol = {
            parametro.simbolo.upper(): parametro
            for parametro in ParametroActivo.objects.filter(simbolo__in=symbols)
        }

        rows: list[FinvizMappingResult] = []
        for asset in portfolio_rows:
            symbol = (asset.simbolo or "").upper().strip()
            parametro = metadata_by_symbol.get(symbol)
            result = self.resolve_from_metadata(parametro)
            if parametro is None:
                result = FinvizMappingResult(
                    internal_symbol=symbol,
                    finviz_symbol=None,
                    status="missing_metadata",
                    reason="metadata_missing",
                    source="portfolio",
                )
            else:
                result = FinvizMappingResult(
                    **{**result.__dict__, "source": "portfolio"}
                )
            rows.append(result)

        return self._build_summary(rows=rows, scope="current_portfolio")

    def _build_summary(self, *, rows: list[FinvizMappingResult], scope: str) -> dict:
        status_counts: dict[str, int] = {}
        for row in rows:
            status_counts[row.status] = status_counts.get(row.status, 0) + 1

        normalized_rows = [
            {
                "internal_symbol": row.internal_symbol,
                "finviz_symbol": row.finviz_symbol,
                "status": row.status,
                "reason": row.reason,
                "tipo_patrimonial": row.tipo_patrimonial,
                "sector": row.sector,
                "country": row.country,
                "strategic_bucket": row.strategic_bucket,
                "source": row.source,
            }
            for row in rows
        ]

        return {
            "scope": scope,
            "total": len(rows),
            "mapped": status_counts.get("mapped", 0),
            "out_of_scope": status_counts.get("out_of_scope", 0),
            "missing_metadata": status_counts.get("missing_metadata", 0),
            "missing_symbol": status_counts.get("missing_symbol", 0),
            "status_counts": status_counts,
            "rows": normalized_rows,
        }
