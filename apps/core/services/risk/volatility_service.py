from datetime import timedelta
from typing import Dict

import pandas as pd
from django.utils import timezone

from apps.portafolio_iol.models import PortfolioSnapshot


class VolatilityService:
    """Cálculo de volatilidad histórica sobre retornos del patrimonio total."""

    TRADING_DAYS_PER_YEAR = 252

    def calculate_volatility(self, days: int = 30) -> Dict[str, float]:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        if snapshots.count() < 2:
            return {}

        df = pd.DataFrame(list(snapshots.values("fecha", "total_iol")))
        if df.empty:
            return {}

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
        df = df.set_index("fecha").sort_index()

        returns = df["total_iol"].pct_change().dropna()
        if returns.empty:
            return {}

        daily_vol = float(returns.std())
        annualized_vol = daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)

        result = {
            "daily_volatility": round(daily_vol * 100, 2),
            "annualized_volatility": round(annualized_vol * 100, 2),
            "sample_size": int(len(returns)),
        }

        mean_return = float(returns.mean())
        if daily_vol > 0:
            sharpe = mean_return / daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)
            result["sharpe_ratio"] = round(sharpe, 2)

        downside = returns[returns < 0]
        if not downside.empty:
            downside_vol = float(downside.std())
            if downside_vol > 0:
                sortino = mean_return / downside_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)
                result["sortino_ratio"] = round(sortino, 2)

        return result
