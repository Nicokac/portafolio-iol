import math
from typing import Dict, List

from django.db.models import Max

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class LiquidityService:
    """Liquidez operativa por instrumento y tiempo estimado de liquidación."""

    TYPE_BASE_SCORE = {
        "CAUCIONESPESOS": 92.0,
        "FondoComundeInversion": 86.0,
        "CEDEARS": 74.0,
        "ACCIONES": 70.0,
        "TitulosPublicos": 62.0,
    }

    TYPE_SPREAD_ESTIMATE = {
        "CAUCIONESPESOS": 0.10,
        "FondoComundeInversion": 0.35,
        "CEDEARS": 1.10,
        "ACCIONES": 1.60,
        "TitulosPublicos": 2.20,
    }

    def analyze_portfolio_liquidity(self) -> Dict:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]
        if not latest_date:
            return {}

        activos = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
        )
        if not activos:
            return {}

        total_value = sum(float(a.valorizado) for a in activos)
        if total_value <= 0:
            return {}

        instrument_rows: List[Dict] = []
        weighted_score_sum = 0.0
        daily_liquidable_value = 0.0

        for activo in activos:
            position_value = float(activo.valorizado)
            if position_value <= 0:
                continue

            asset_type = activo.tipo
            base_score = self.TYPE_BASE_SCORE.get(asset_type, 55.0)
            spread_pct = self.TYPE_SPREAD_ESTIMATE.get(asset_type, 2.80)

            # Proxy simple de volumen: mayor tamaño nominal -> mejor capacidad de cruce
            avg_volume_proxy = max(1.0, math.log10(position_value + 1) * 1000)

            volume_bonus = min(14.0, math.log10(position_value + 1) * 2.5)
            spread_penalty = spread_pct * 6.0
            liquidity_score = max(5.0, min(99.0, base_score + volume_bonus - spread_penalty))

            daily_capacity_pct = max(0.04, min(0.40, liquidity_score / 250.0))
            instrument_days = 1.0 / daily_capacity_pct

            instrument_rows.append(
                {
                    "symbol": activo.simbolo,
                    "asset_type": asset_type,
                    "position_value": round(position_value, 2),
                    "estimated_spread_pct": round(spread_pct, 2),
                    "avg_volume_proxy": round(avg_volume_proxy, 2),
                    "liquidity_score": round(liquidity_score, 2),
                    "daily_liquidation_capacity_pct": round(daily_capacity_pct * 100, 2),
                    "days_to_liquidate": round(instrument_days, 2),
                }
            )

            weighted_score_sum += liquidity_score * position_value
            daily_liquidable_value += position_value * daily_capacity_pct

        if not instrument_rows or daily_liquidable_value <= 0:
            return {}

        portfolio_score = weighted_score_sum / total_value
        days_to_liquidate = total_value / daily_liquidable_value

        instrument_rows.sort(key=lambda row: row["position_value"], reverse=True)

        return {
            "portfolio_liquidity_score": round(portfolio_score, 2),
            "days_to_liquidate": round(days_to_liquidate, 2),
            "instruments": instrument_rows,
            "worst_instruments": sorted(
                instrument_rows, key=lambda row: row["liquidity_score"]
            )[:5],
        }
