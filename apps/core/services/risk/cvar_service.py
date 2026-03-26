from datetime import timedelta
from typing import Dict

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.portafolio_iol.models import PortfolioSnapshot


class CVaRService:
    """Expected Shortfall / Conditional VaR historico."""

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
        returns, fallback_source, observations = self._get_returns_with_metadata(days=lookback_days)
        if returns.empty:
            return {
                "warning": "insufficient_history",
                "required_min_observations": 2,
                "observations": observations,
            }

        cvar_1d = self.historical_cvar(confidence=confidence, horizon_days=1, lookback_days=lookback_days)
        cvar_10d = self.historical_cvar(confidence=confidence, horizon_days=10, lookback_days=lookback_days)

        result = {}
        if cvar_1d is not None:
            result["historical_cvar_95_1d"] = cvar_1d
        if cvar_10d is not None:
            result["historical_cvar_95_10d"] = cvar_10d
        if fallback_source:
            result["fallback_source"] = fallback_source
        return result
