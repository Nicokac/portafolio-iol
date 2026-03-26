from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class CovarianceService:
    """Construccion de expected returns y matriz de covarianza por activos."""

    TRADING_DAYS_PER_YEAR = 252

    def build_returns_matrix(self, activos: List[str], lookback_days: int = 252) -> pd.DataFrame:
        end_dt = timezone.now()
        end_date = end_dt.date()
        start_date = (end_dt - timedelta(days=lookback_days)).date()

        queryset = ActivoPortafolioSnapshot.objects.filter(
            simbolo__in=activos,
            fecha_extraccion__date__gt=start_date,
            fecha_extraccion__date__lte=end_date,
        ).values("fecha_extraccion", "simbolo", "valorizado")

        df = pd.DataFrame(list(queryset))
        if df.empty:
            return pd.DataFrame()

        df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"])
        df["valorizado"] = pd.to_numeric(df["valorizado"], errors="coerce")
        pivot = self._build_daily_price_matrix(df, activos)
        return self._build_returns_from_price_matrix(pivot)

    @staticmethod
    def _build_returns_from_price_matrix(pivot: pd.DataFrame) -> pd.DataFrame:
        if pivot.shape[0] < 2:
            return pd.DataFrame()

        returns = pivot.pct_change().dropna(how="any")
        return returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")

    @staticmethod
    def _build_daily_price_matrix(df: pd.DataFrame, activos: List[str]) -> pd.DataFrame:
        normalized = df.copy()
        normalized["fecha"] = normalized["fecha_extraccion"].dt.date
        daily = (
            normalized.sort_values("fecha_extraccion")
            .dropna(subset=["valorizado"])
            .drop_duplicates(subset=["fecha", "simbolo"], keep="last")
        )
        pivot = (
            daily.pivot_table(
                index="fecha",
                columns="simbolo",
                values="valorizado",
                aggfunc="last",
            )
            .sort_index()
            .ffill()
        )
        pivot = pivot.reindex(columns=activos)
        return pivot.dropna(how="all")

    def expected_returns_annualized(self, returns: pd.DataFrame) -> np.ndarray:
        if returns.empty:
            return np.array([])
        return returns.mean().values * self.TRADING_DAYS_PER_YEAR

    def covariance_matrix_annualized(self, returns: pd.DataFrame) -> np.ndarray:
        if returns.empty or len(returns.index) < 2:
            return np.array([[]])
        sanitized = returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if sanitized.empty or len(sanitized.index) < 2:
            return np.array([[]])
        cov = sanitized.cov().values * self.TRADING_DAYS_PER_YEAR
        cov += np.eye(cov.shape[0]) * 1e-8
        return cov

    def build_model_inputs(self, activos: List[str], lookback_days: int = 252):
        returns = self.build_returns_matrix(activos, lookback_days=lookback_days)
        observations = int(len(returns.index))
        if returns.empty or observations < 2:
            return {
                "warning": "insufficient_history",
                "required_min_observations": 2,
                "observations": observations,
                "returns": returns,
                "expected_returns": np.array([]),
                "covariance_matrix": np.array([[]]),
            }
        return {
            "observations": observations,
            "returns": returns,
            "expected_returns": self.expected_returns_annualized(returns),
            "covariance_matrix": self.covariance_matrix_annualized(returns),
        }
