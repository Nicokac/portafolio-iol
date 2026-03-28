from __future__ import annotations

from decimal import Decimal

from django.db.models import Max

from apps.core.services.finviz.finviz_scoring_service import FinvizScoringService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class FinvizOpportunityWatchlistService:
    """Construye un radar simple de oportunidades a partir del score Finviz mas reciente."""

    def __init__(self, *, scoring_service: FinvizScoringService | None = None):
        self.scoring_service = scoring_service or FinvizScoringService()

    def build_watchlist(
        self,
        *,
        shortlist_limit: int = 20,
        external_limit: int = 5,
        reinforce_limit: int = 5,
    ) -> dict:
        latest_portfolio_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        holdings = self._load_current_holdings(latest_portfolio_date)
        shortlist = self.scoring_service.build_latest_shortlist(limit=shortlist_limit)

        rows = []
        for item in shortlist.get("items", []):
            symbol = str(item.get("internal_symbol") or "").strip().upper()
            holding = holdings.get(symbol)
            enriched = {
                **item,
                "is_current_holding": bool(holding),
                "holding_weight_pct": holding.get("weight_pct") if holding else None,
                "holding_market_value": holding.get("market_value") if holding else None,
                "watchlist_bucket": "reinforce" if holding else "external",
            }
            rows.append(enriched)

        external = sorted(
            [row for row in rows if not row["is_current_holding"]],
            key=lambda item: (
                -(item.get("composite_buy_score") or float("-inf")),
                -(item.get("quality_score") or float("-inf")),
                -(item.get("analyst_score") or float("-inf")),
                item.get("internal_symbol") or "",
            ),
        )[:external_limit]
        reinforce = sorted(
            [row for row in rows if row["is_current_holding"]],
            key=lambda item: (
                -(item.get("composite_buy_score") or float("-inf")),
                item.get("holding_weight_pct") or float("inf"),
                -(item.get("quality_score") or float("-inf")),
                item.get("internal_symbol") or "",
            ),
        )[:reinforce_limit]
        high_conviction = sorted(
            [
                row for row in rows
                if (row.get("composite_buy_score") or 0) >= 75
                or (row.get("quality_score") or 0) >= 80
                or (row.get("analyst_score") or 0) >= 75
            ],
            key=lambda item: (
                -(item.get("composite_buy_score") or float("-inf")),
                -(item.get("analyst_score") or float("-inf")),
                item.get("internal_symbol") or "",
            ),
        )[:5]

        return {
            "captured_date": shortlist.get("captured_date"),
            "portfolio_date": latest_portfolio_date.isoformat() if latest_portfolio_date else None,
            "coverage": {
                "shortlist_count": shortlist.get("count") or 0,
                "current_holdings_considered": len(holdings),
                "external_candidates": len(external),
                "reinforce_candidates": len(reinforce),
            },
            "summary": self._build_summary(external=external, reinforce=reinforce),
            "external_candidates": external,
            "reinforce_candidates": reinforce,
            "high_conviction": high_conviction,
            "items": rows,
        }

    def _load_current_holdings(self, latest_portfolio_date) -> dict[str, dict]:
        if not latest_portfolio_date:
            return {}
        rows = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_portfolio_date).order_by("simbolo")
        )
        invested_rows = [
            row for row in rows
            if self._as_float(row.valorizado) > 0 and self._is_candidate_tipo(getattr(row, "tipo", ""))
        ]
        total_invested = sum(self._as_float(row.valorizado) for row in invested_rows)
        holdings = {}
        for row in invested_rows:
            symbol = str(row.simbolo or "").strip().upper()
            if not symbol:
                continue
            market_value = self._as_float(row.valorizado)
            holdings[symbol] = {
                "market_value": round(market_value, 2),
                "weight_pct": round((market_value / total_invested * 100.0), 2) if total_invested > 0 else 0.0,
            }
        return holdings

    @staticmethod
    def _build_summary(*, external: list[dict], reinforce: list[dict]) -> str:
        if not external and not reinforce:
            return "Todavia no hay cobertura Finviz suficiente para construir un radar de oportunidades."
        if external and reinforce:
            return (
                f"{external[0]['internal_symbol']} aparece como idea externa mejor rankeada y "
                f"{reinforce[0]['internal_symbol']} lidera entre los nombres ya tenidos para reforzar."
            )
        if external:
            return f"{external[0]['internal_symbol']} lidera el radar externo de oportunidades."
        return f"{reinforce[0]['internal_symbol']} lidera la lista de refuerzo dentro de la cartera actual."

    @staticmethod
    def _is_candidate_tipo(tipo: str) -> bool:
        normalized = str(tipo or "").strip().lower()
        return normalized in {"cedears", "acciones", "accionesusa", "etfs", "etf"}

    @staticmethod
    def _as_float(value) -> float:
        if value in (None, "", Decimal("0")):
            try:
                return float(value or 0.0)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
