from __future__ import annotations

from decimal import Decimal

from django.db.models import Max

from apps.core.models import FinvizFundamentalsSnapshot
from apps.core.services.finviz.finviz_scoring_service import FinvizScoringService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class FinvizPortfolioOverlayService:
    """Construye una lectura agregada del portafolio a partir de snapshots Finviz."""

    def __init__(self, *, scoring_service: FinvizScoringService | None = None):
        self.scoring_service = scoring_service or FinvizScoringService()

    def build_current_portfolio_overlay(self) -> dict:
        latest_portfolio_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        latest_finviz_date = FinvizFundamentalsSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]

        if not latest_portfolio_date or not latest_finviz_date:
            return self._empty_overlay()

        portfolio_rows = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_portfolio_date).order_by("simbolo")
        )
        invested_rows = [
            row for row in portfolio_rows
            if self._as_float(row.valorizado) > 0 and self._is_candidate_tipo(getattr(row, "tipo", ""))
        ]
        if not invested_rows:
            return self._empty_overlay()

        symbols = [row.simbolo.upper().strip() for row in invested_rows if (row.simbolo or "").strip()]
        latest_snapshots = {
            item["internal_symbol"]: item
            for item in self.scoring_service.fundamentals_service.list_latest_snapshots(symbols=symbols).get("items", [])
        }

        total_invested = sum(self._as_float(row.valorizado) for row in invested_rows)
        mapped_market_value = 0.0
        weighted_beta = 0.0
        weighted_composite = 0.0
        weighted_valuation = 0.0
        weighted_quality = 0.0
        weighted_balance = 0.0
        weighted_growth = 0.0
        weighted_market_signal = 0.0
        overlay_rows = []

        for row in invested_rows:
            symbol = row.simbolo.upper().strip()
            market_value = self._as_float(row.valorizado)
            snapshot = latest_snapshots.get(symbol)
            if not snapshot:
                continue
            scored = self.scoring_service.score_asset(snapshot)
            weight_pct = (market_value / total_invested * 100.0) if total_invested > 0 else 0.0
            mapped_market_value += market_value

            beta = self._as_float(scored.get("beta"))
            composite = self._as_float(scored.get("composite_buy_score"))
            valuation = self._as_float(scored.get("valuation_score"))
            quality = self._as_float(scored.get("quality_score"))
            balance = self._as_float(scored.get("balance_score"))
            growth = self._as_float(scored.get("growth_score"))
            market_signal = self._as_float(scored.get("market_signal_score"))

            if beta is not None:
                weighted_beta += beta * market_value
            if composite is not None:
                weighted_composite += composite * market_value
            if valuation is not None:
                weighted_valuation += valuation * market_value
            if quality is not None:
                weighted_quality += quality * market_value
            if balance is not None:
                weighted_balance += balance * market_value
            if growth is not None:
                weighted_growth += growth * market_value
            if market_signal is not None:
                weighted_market_signal += market_signal * market_value

            overlay_rows.append(
                {
                    "symbol": symbol,
                    "market_value": market_value,
                    "weight_pct": round(weight_pct, 2),
                    "beta": beta,
                    "composite_buy_score": composite,
                    "valuation_score": valuation,
                    "quality_score": quality,
                    "balance_score": balance,
                    "growth_score": growth,
                    "market_signal_score": market_signal,
                    "interpretation": scored.get("interpretation"),
                    "strengths": scored.get("strengths") or [],
                    "cautions": scored.get("cautions") or [],
                }
            )

        if mapped_market_value <= 0:
            return self._empty_overlay()

        coverage_pct = round(mapped_market_value / total_invested * 100.0, 2) if total_invested > 0 else 0.0
        ranked_by_weight = sorted(overlay_rows, key=lambda item: (-item["weight_pct"], item["symbol"]))
        ranked_by_beta = sorted(
            [row for row in overlay_rows if row.get("beta") is not None],
            key=lambda item: (-float(item["beta"]), -item["weight_pct"], item["symbol"]),
        )
        ranked_by_valuation = sorted(
            [row for row in overlay_rows if row.get("valuation_score") is not None],
            key=lambda item: (float(item["valuation_score"]), -item["weight_pct"], item["symbol"]),
        )
        ranked_by_quality = sorted(
            [row for row in overlay_rows if row.get("quality_score") is not None],
            key=lambda item: (-float(item["quality_score"]), -item["weight_pct"], item["symbol"]),
        )
        ranked_by_balance = sorted(
            [row for row in overlay_rows if row.get("balance_score") is not None],
            key=lambda item: (float(item["balance_score"]), -item["weight_pct"], item["symbol"]),
        )

        weighted_profiles = {
            "portfolio_beta": round(weighted_beta / mapped_market_value, 2),
            "composite_buy_score": round(weighted_composite / mapped_market_value, 1),
            "valuation_score": round(weighted_valuation / mapped_market_value, 1),
            "quality_score": round(weighted_quality / mapped_market_value, 1),
            "balance_score": round(weighted_balance / mapped_market_value, 1),
            "growth_score": round(weighted_growth / mapped_market_value, 1),
            "market_signal_score": round(weighted_market_signal / mapped_market_value, 1),
        }

        return {
            "captured_date": latest_finviz_date.isoformat(),
            "portfolio_date": latest_portfolio_date.isoformat(),
            "coverage": {
                "mapped_assets": len(overlay_rows),
                "portfolio_assets": len(invested_rows),
                "coverage_pct": coverage_pct,
                "mapped_market_value": round(mapped_market_value, 2),
                "total_invested": round(total_invested, 2),
            },
            "weighted_profiles": weighted_profiles,
            "valuation_profile": self._classify_profile(weighted_profiles["valuation_score"]),
            "quality_profile": self._classify_profile(weighted_profiles["quality_score"]),
            "leverage_profile": self._classify_profile(weighted_profiles["balance_score"]),
            "beta_profile": self._classify_beta_profile(weighted_profiles["portfolio_beta"]),
            "leaders": {
                "highest_weight": ranked_by_weight[:3],
                "highest_beta": ranked_by_beta[:3],
                "best_quality": ranked_by_quality[:3],
            },
            "warnings": {
                "expensive_names": ranked_by_valuation[:3],
                "fragile_balance": ranked_by_balance[:3],
            },
            "summary": self._build_summary(weighted_profiles, coverage_pct),
            "items": overlay_rows,
        }

    @staticmethod
    def _empty_overlay() -> dict:
        return {
            "captured_date": None,
            "portfolio_date": None,
            "coverage": {
                "mapped_assets": 0,
                "portfolio_assets": 0,
                "coverage_pct": 0.0,
                "mapped_market_value": 0.0,
                "total_invested": 0.0,
            },
            "weighted_profiles": {},
            "valuation_profile": {"label": "Sin base suficiente", "level": "unknown"},
            "quality_profile": {"label": "Sin base suficiente", "level": "unknown"},
            "leverage_profile": {"label": "Sin base suficiente", "level": "unknown"},
            "beta_profile": {"label": "Sin base suficiente", "level": "unknown"},
            "leaders": {"highest_weight": [], "highest_beta": [], "best_quality": []},
            "warnings": {"expensive_names": [], "fragile_balance": []},
            "summary": "Todavia no hay base suficiente de Finviz para leer el portafolio.",
            "items": [],
        }

    @staticmethod
    def _classify_profile(score: float | None) -> dict:
        if score is None:
            return {"label": "Sin base suficiente", "level": "unknown"}
        if score >= 80:
            return {"label": "Fuerte", "level": "high"}
        if score >= 65:
            return {"label": "Saludable", "level": "medium_high"}
        if score >= 50:
            return {"label": "Mixto", "level": "medium"}
        if score >= 35:
            return {"label": "Exigente", "level": "low"}
        return {"label": "Debil", "level": "weak"}

    @staticmethod
    def _classify_beta_profile(beta: float | None) -> dict:
        if beta is None:
            return {"label": "Sin base suficiente", "level": "unknown"}
        if beta <= 0.85:
            return {"label": "Defensivo", "level": "low"}
        if beta <= 1.15:
            return {"label": "Balanceado", "level": "balanced"}
        if beta <= 1.45:
            return {"label": "Agresivo", "level": "high"}
        return {"label": "Muy agresivo", "level": "very_high"}

    @staticmethod
    def _build_summary(weighted_profiles: dict, coverage_pct: float) -> str:
        beta = weighted_profiles.get("portfolio_beta")
        quality = weighted_profiles.get("quality_score")
        valuation = weighted_profiles.get("valuation_score")
        if beta is None:
            return "La cobertura Finviz del portafolio todavia es insuficiente para una lectura agregada."
        return (
            f"Cobertura Finviz {coverage_pct:.1f}% del portafolio invertido. "
            f"Beta ponderada {beta:.2f}, quality {quality:.1f}, valuation {valuation:.1f}."
        )

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
