from datetime import timedelta
from statistics import NormalDist
from typing import Dict

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.portafolio_iol.models import PortfolioSnapshot


class VaRService:
    """Value at Risk (Historical + Parametric) sobre retornos de patrimonio."""

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

    @staticmethod
    def _scale_horizon(value: float, horizon_days: int) -> float:
        return value * (horizon_days ** 0.5)

    def historical_var(
        self, confidence: float = 0.95, horizon_days: int = 1, lookback_days: int = 252
    ) -> float | None:
        returns = self._get_returns(days=lookback_days)
        if returns.empty:
            return None

        tail_percentile = (1 - confidence) * 100
        threshold = float(np.percentile(returns.values, tail_percentile))
        var_1d = max(0.0, -threshold) * 100
        return round(self._scale_horizon(var_1d, horizon_days), 2)

    def parametric_var(
        self, confidence: float = 0.95, horizon_days: int = 1, lookback_days: int = 252
    ) -> float | None:
        returns = self._get_returns(days=lookback_days)
        if returns.empty:
            return None

        mu = float(returns.mean())
        sigma = float(returns.std())
        if sigma <= 0:
            return 0.0

        q = 1 - confidence
        z = NormalDist().inv_cdf(q)

        horizon_mu = mu * horizon_days
        horizon_sigma = sigma * (horizon_days ** 0.5)
        threshold = horizon_mu + z * horizon_sigma
        var = max(0.0, -threshold) * 100
        return round(var, 2)

    def calculate_var_set(self, confidence: float = 0.95, lookback_days: int = 252) -> Dict[str, float]:
        returns = self._get_returns(days=lookback_days)
        if returns.empty:
            return {
                "warning": "insufficient_history",
                "required_min_observations": 2,
                "observations": 0,
            }

        historical_1d = self.historical_var(confidence=confidence, horizon_days=1, lookback_days=lookback_days)
        historical_10d = self.historical_var(confidence=confidence, horizon_days=10, lookback_days=lookback_days)
        parametric_1d = self.parametric_var(confidence=confidence, horizon_days=1, lookback_days=lookback_days)
        parametric_10d = self.parametric_var(confidence=confidence, horizon_days=10, lookback_days=lookback_days)

        result = {}
        if historical_1d is not None:
            result["historical_var_95_1d"] = historical_1d
        if historical_10d is not None:
            result["historical_var_95_10d"] = historical_10d
        if parametric_1d is not None:
            result["parametric_var_95_1d"] = parametric_1d
        if parametric_10d is not None:
            result["parametric_var_95_10d"] = parametric_10d

        return result
