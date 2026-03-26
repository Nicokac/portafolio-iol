from datetime import timedelta
from statistics import NormalDist
from typing import Dict

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import PortfolioSnapshot


class VaRService:
    """Value at Risk (Historical + Parametric) sobre retornos de patrimonio."""

    def __init__(self, historical_price_service: IOLHistoricalPriceService | None = None):
        self.historical_price_service = historical_price_service or IOLHistoricalPriceService()
        self.volatility_service = VolatilityService(historical_price_service=self.historical_price_service)

    @staticmethod
    def _sanitize_returns(returns: pd.Series) -> pd.Series:
        if returns is None:
            return pd.Series(dtype=float)
        return (
            pd.to_numeric(returns, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

    def _get_returns_with_metadata(self, days: int = 252) -> tuple[pd.Series, str | None, int]:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        observations = snapshots.count()
        if observations < 2:
            proxy_returns = self._sanitize_returns(
                self.volatility_service.build_iol_proxy_return_series(days=days)
            )
            if not proxy_returns.empty:
                return proxy_returns, "iol_historical_prices_proxy", int(len(proxy_returns.index) + 1)
            return pd.Series(dtype=float), None, observations

        df = pd.DataFrame(list(snapshots.values("fecha", "total_iol")))
        if df.empty:
            return pd.Series(dtype=float), None, observations

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
        df = df.set_index("fecha").sort_index()
        return self._sanitize_returns(df["total_iol"].pct_change()), None, observations

    def _get_returns(self, days: int = 252) -> pd.Series:
        returns, _, _ = self._get_returns_with_metadata(days=days)
        return returns

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
        returns, fallback_source, observations = self._get_returns_with_metadata(days=lookback_days)
        if returns.empty:
            return {
                "warning": "insufficient_history",
                "required_min_observations": 2,
                "observations": observations,
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
        if fallback_source:
            result["fallback_source"] = fallback_source

        return result
