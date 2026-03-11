from datetime import timedelta
from typing import Dict

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.portafolio_iol.models import PortfolioSnapshot


class CVaRService:
    """Expected Shortfall / Conditional VaR histórico."""

    def _get_returns(self, days: int = 252) -> pd.Series:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        if snapshots.count() < 2:
            return pd.Series(dtype=float)

        df = pd.DataFrame(list(snapshots.values("fecha", "total_iol")))
        if df.empty:
            return pd.Series(dtype=float)

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
        df = df.set_index("fecha").sort_index()
        return df["total_iol"].pct_change().dropna()

    def historical_cvar(
        self, confidence: float = 0.95, horizon_days: int = 1, lookback_days: int = 252
    ) -> float | None:
        returns = self._get_returns(days=lookback_days)
        if returns.empty:
            return None

        tail_percentile = (1 - confidence) * 100
        var_threshold = float(np.percentile(returns.values, tail_percentile))
        tail = returns[returns <= var_threshold]
        if tail.empty:
            return 0.0

        cvar_1d = max(0.0, -float(tail.mean())) * 100
        cvar = cvar_1d * (horizon_days ** 0.5)
        return round(cvar, 2)

    def calculate_cvar_set(self, confidence: float = 0.95, lookback_days: int = 252) -> Dict[str, float]:
        cvar_1d = self.historical_cvar(confidence=confidence, horizon_days=1, lookback_days=lookback_days)
        cvar_10d = self.historical_cvar(confidence=confidence, horizon_days=10, lookback_days=lookback_days)

        result = {}
        if cvar_1d is not None:
            result["historical_cvar_95_1d"] = cvar_1d
        if cvar_10d is not None:
            result["historical_cvar_95_10d"] = cvar_10d
        return result
