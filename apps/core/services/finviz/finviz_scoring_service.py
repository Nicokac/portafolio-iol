from __future__ import annotations

from typing import Any

from apps.core.services.finviz.finviz_fundamentals_service import FinvizFundamentalsService
from apps.core.services.finviz.finviz_signal_overlay_service import FinvizSignalOverlayService


class FinvizScoringService:
    """Construye subscores y shortlist de compra a partir del snapshot Finviz mas reciente."""

    SCORE_WEIGHTS = {
        "valuation_score": 20,
        "growth_score": 20,
        "quality_score": 25,
        "balance_score": 15,
        "market_signal_score": 10,
        "analyst_score": 10,
    }

    def __init__(
        self,
        *,
        fundamentals_service: FinvizFundamentalsService | None = None,
        signal_overlay_service: FinvizSignalOverlayService | None = None,
    ):
        self.fundamentals_service = fundamentals_service or FinvizFundamentalsService()
        self.signal_overlay_service = signal_overlay_service or FinvizSignalOverlayService()

    def build_latest_shortlist(self, *, symbols: list[str] | None = None, limit: int = 10) -> dict:
        latest = self.fundamentals_service.list_latest_snapshots(symbols=symbols)
        signal_map = {
            item["internal_symbol"]: item
            for item in self.signal_overlay_service.list_latest_snapshots(symbols=symbols).get("items", [])
        }
        scored_items = []
        for item in latest.get("items", []):
            merged = {**item, **signal_map.get(item.get("internal_symbol"), {})}
            scored_items.append(self.score_asset(merged))

        scored_items = [
            item for item in scored_items
            if item.get("source_status") == "ok" and item.get("composite_buy_score") is not None
        ]
        ranked = sorted(
            scored_items,
            key=lambda item: (
                -(item.get("composite_buy_score") or float("-inf")),
                -(item.get("quality_score") or float("-inf")),
                item.get("internal_symbol") or "",
            ),
        )
        if limit:
            ranked = ranked[:limit]

        return {
            "captured_date": latest.get("captured_date"),
            "count": len(ranked),
            "items": [
                {
                    **item,
                    "rank": index,
                }
                for index, item in enumerate(ranked, start=1)
            ],
        }

    def compare_candidates(self, symbols: list[str]) -> dict:
        scored = self.build_latest_shortlist(symbols=symbols, limit=len(symbols or []))
        items = scored.get("items", [])
        if not items:
            return {
                "captured_date": scored.get("captured_date"),
                "count": 0,
                "winner": None,
                "items": [],
                "summary": "No hay snapshots Finviz listos para comparar estos candidatos.",
            }

        winner = items[0]
        runner_up = items[1] if len(items) > 1 else None
        score_gap = None
        if runner_up is not None:
            score_gap = round(float(winner["composite_buy_score"]) - float(runner_up["composite_buy_score"]), 1)

        summary = (
            f"{winner['internal_symbol']} lidera por score compuesto."
            if runner_up is None
            else f"{winner['internal_symbol']} queda arriba por {score_gap} puntos sobre {runner_up['internal_symbol']}."
        )
        return {
            "captured_date": scored.get("captured_date"),
            "count": len(items),
            "winner": winner,
            "items": items,
            "summary": summary,
        }

    def score_asset(self, item: dict[str, Any]) -> dict:
        valuation_score = self._score_valuation(item)
        growth_score = self._score_growth(item)
        quality_score = self._score_quality(item)
        balance_score = self._score_balance(item)
        market_signal_score = self._score_market_signal(item)
        analyst_score = self._as_float(item.get("analyst_score"))

        score_map = {
            "valuation_score": valuation_score,
            "growth_score": growth_score,
            "quality_score": quality_score,
            "balance_score": balance_score,
            "market_signal_score": market_signal_score,
            "analyst_score": analyst_score,
        }
        available_weight = sum(
            weight for key, weight in self.SCORE_WEIGHTS.items()
            if score_map.get(key) is not None
        )
        if available_weight <= 0:
            composite_buy_score = None
        else:
            weighted_total = sum(
                float(score_map[key]) * weight
                for key, weight in self.SCORE_WEIGHTS.items()
                if score_map.get(key) is not None
            )
            composite_buy_score = round(weighted_total / available_weight, 1)

        interpretation = self._build_interpretation(composite_buy_score)
        strengths, cautions = self._build_explanations(score_map)

        return {
            **item,
            **score_map,
            "composite_buy_score": composite_buy_score,
            "interpretation": interpretation,
            "strengths": strengths,
            "cautions": cautions,
            "main_reason": strengths[0] if strengths else "Sin senal diferencial clara por ahora.",
            "data_quality_label": self._data_quality_label(item.get("data_quality")),
            "analyst_signal_label_text": self._analyst_signal_label(item.get("analyst_signal_label"), analyst_score),
            "secondary_overlay_summary": self._build_secondary_overlay_summary(item),
        }

    def _score_valuation(self, item: dict[str, Any]) -> float | None:
        scores = []
        fwd_pe = self._as_float(item.get("fwd_pe"))
        peg = self._as_float(item.get("peg"))
        ps = self._as_float(item.get("ps"))
        pb = self._as_float(item.get("pb"))

        if fwd_pe is not None:
            scores.append(self._banded_lower_better(fwd_pe, [(15, 95), (22, 80), (30, 60), (40, 35)], 15))
        if peg is not None:
            scores.append(self._banded_lower_better(peg, [(1.0, 95), (1.5, 82), (2.0, 65), (3.0, 40)], 18))
        if ps is not None:
            scores.append(self._banded_lower_better(ps, [(3.0, 85), (6.0, 68), (10.0, 45)], 25))
        if pb is not None:
            scores.append(self._banded_lower_better(pb, [(3.0, 82), (6.0, 65), (10.0, 40)], 22))
        return self._average(scores)

    def _score_growth(self, item: dict[str, Any]) -> float | None:
        scores = []
        eps_next_y = self._as_float(item.get("eps_next_y"))
        eps_next_5y = self._as_float(item.get("eps_next_5y"))
        sales_past_5y = self._as_float(item.get("sales_past_5y"))

        if eps_next_y is not None:
            scores.append(self._banded_higher_better(eps_next_y, [(0, 45), (5, 62), (12, 80), (20, 95)], 18))
        if eps_next_5y is not None:
            scores.append(self._banded_higher_better(eps_next_5y, [(0, 45), (5, 62), (10, 80), (15, 95)], 18))
        if sales_past_5y is not None:
            scores.append(self._banded_higher_better(sales_past_5y, [(0, 45), (3, 60), (8, 77), (15, 92)], 20))
        return self._average(scores)

    def _score_quality(self, item: dict[str, Any]) -> float | None:
        scores = []
        roic = self._as_float(item.get("roic"))
        oper_m = self._as_float(item.get("oper_m"))
        profit_m = self._as_float(item.get("profit_m"))
        roe = self._as_float(item.get("roe"))

        if roic is not None:
            scores.append(self._banded_higher_better(roic, [(0, 35), (5, 55), (10, 72), (15, 85), (20, 95)], 15))
        if oper_m is not None:
            scores.append(self._banded_higher_better(oper_m, [(0, 35), (10, 60), (20, 82), (30, 95)], 15))
        if profit_m is not None:
            scores.append(self._banded_higher_better(profit_m, [(0, 35), (8, 58), (15, 80), (25, 95)], 15))
        if roe is not None:
            scores.append(self._banded_higher_better(roe, [(0, 35), (10, 60), (18, 82), (25, 95)], 15))
        return self._average(scores)

    def _score_balance(self, item: dict[str, Any]) -> float | None:
        scores = []
        debt_eq = self._as_float(item.get("debt_eq"))
        quick_r = self._as_float(item.get("quick_r"))
        curr_r = self._as_float(item.get("curr_r"))
        lt_debt_eq = self._as_float(item.get("lt_debt_eq"))

        if debt_eq is not None:
            scores.append(self._banded_lower_better(debt_eq, [(0.3, 95), (0.6, 82), (1.0, 68), (2.0, 42)], 18))
        if lt_debt_eq is not None:
            scores.append(self._banded_lower_better(lt_debt_eq, [(0.3, 95), (0.6, 82), (1.0, 68), (2.0, 42)], 18))
        if quick_r is not None:
            scores.append(self._banded_higher_better(quick_r, [(0.7, 35), (1.0, 58), (1.2, 76), (2.0, 92)], 18))
        if curr_r is not None:
            scores.append(self._banded_higher_better(curr_r, [(0.8, 40), (1.1, 60), (1.5, 78), (2.0, 90)], 20))
        return self._average(scores)

    def _score_market_signal(self, item: dict[str, Any]) -> float | None:
        scores = []
        beta = self._as_float(item.get("beta"))
        change_pct = self._as_float(item.get("change_pct"))
        volume = self._as_float(item.get("volume"))

        if beta is not None:
            if 0.8 <= beta <= 1.3:
                scores.append(80.0)
            elif 0.5 <= beta < 0.8 or 1.3 < beta <= 1.6:
                scores.append(65.0)
            elif beta < 0.5:
                scores.append(55.0)
            elif 1.6 < beta <= 2.0:
                scores.append(38.0)
            else:
                scores.append(22.0)
        if change_pct is not None:
            scores.append(self._banded_higher_better(change_pct, [(-8, 20), (-3, 35), (0, 52), (3, 72), (8, 88)], 92))
        if volume is not None:
            scores.append(self._banded_higher_better(volume, [(100000, 28), (500000, 48), (2000000, 68), (10000000, 86)], 94))
        return self._average(scores)

    @staticmethod
    def _build_interpretation(score: float | None) -> dict:
        if score is None:
            return {"label": "Sin base suficiente", "level": "unknown"}
        if score >= 80:
            return {"label": "Alta conviccion", "level": "high"}
        if score >= 65:
            return {"label": "Interesante para compra", "level": "medium_high"}
        if score >= 50:
            return {"label": "Conviene esperar mejor punto", "level": "medium"}
        if score >= 35:
            return {"label": "Fragil o exigente", "level": "low"}
        return {"label": "Evitar por ahora", "level": "avoid"}

    def _build_explanations(self, score_map: dict[str, float | None]) -> tuple[list[str], list[str]]:
        strengths = []
        cautions = []
        labels = {
            "valuation_score": "valuacion",
            "growth_score": "growth",
            "quality_score": "quality",
            "balance_score": "balance",
            "market_signal_score": "timing",
            "analyst_score": "consenso externo",
        }

        for key, score in score_map.items():
            if score is None:
                continue
            label = labels[key]
            if score >= 75:
                strengths.append(f"Buena senal de {label}.")
            elif score <= 40:
                cautions.append(f"Senal floja de {label}.")

        if not strengths and any(score is not None for score in score_map.values()):
            best_key = max(
                (key for key, value in score_map.items() if value is not None),
                key=lambda key: score_map[key],
            )
            strengths.append(f"Lo mejor hoy pasa por {labels[best_key]}.")
        if not cautions and any(score is not None for score in score_map.values()):
            worst_key = min(
                (key for key, value in score_map.items() if value is not None),
                key=lambda key: score_map[key],
            )
            if score_map[worst_key] < 60:
                cautions.append(f"El punto mas flojo hoy pasa por {labels[worst_key]}.")
        return strengths, cautions

    @staticmethod
    def _analyst_signal_label(signal_label: Any, analyst_score: float | None) -> str:
        label = str(signal_label or "").strip().lower()
        if label == "positive":
            return "Consenso favorable"
        if label == "negative":
            return "Consenso adverso"
        if label == "cautious":
            return "Consenso fragil"
        if label == "mixed":
            return "Consenso mixto"
        if analyst_score is None:
            return "Sin consenso visible"
        return "Consenso disponible"

    @staticmethod
    def _build_secondary_overlay_summary(item: dict[str, Any]) -> str:
        ratings_count = int(item.get("ratings_count") or 0)
        news_count = int(item.get("news_count") or 0)
        insider_buy_count = int(item.get("insider_buy_count") or 0)
        insider_sale_count = int(item.get("insider_sale_count") or 0)
        parts = []
        if ratings_count:
            parts.append(f"{ratings_count} rating(s)")
        if news_count:
            parts.append(f"{news_count} noticia(s)")
        if insider_buy_count or insider_sale_count:
            parts.append(f"insiders B{insider_buy_count}/S{insider_sale_count}")
        if not parts:
            return "Sin overlays secundarios visibles por ahora."
        return "Overlay: " + " · ".join(parts)

    @staticmethod
    def _data_quality_label(data_quality: Any) -> str:
        value = str(data_quality or "").strip().lower()
        return {
            "full": "Cobertura alta",
            "partial": "Cobertura usable",
            "sparse": "Cobertura limitada",
            "missing": "Sin base suficiente",
        }.get(value, "Cobertura desconocida")

    @staticmethod
    def _average(values: list[float]) -> float | None:
        usable = [float(value) for value in values if value is not None]
        if not usable:
            return None
        return round(sum(usable) / len(usable), 1)

    @staticmethod
    def _banded_lower_better(value: float, bands: list[tuple[float, float]], fallback: float) -> float:
        for threshold, score in bands:
            if value <= threshold:
                return float(score)
        return float(fallback)

    @staticmethod
    def _banded_higher_better(value: float, bands: list[tuple[float, float]], fallback: float) -> float:
        selected = fallback
        for threshold, score in bands:
            if value >= threshold:
                selected = score
        return float(selected)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value in (None, "", "-", "N/A"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
