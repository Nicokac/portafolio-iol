from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
from django.utils import timezone

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class CovarianceService:
    """Construcción de expected returns y matriz de covarianza por activos."""

    TRADING_DAYS_PER_YEAR = 252

    def build_returns_matrix(self, activos: List[str], lookback_days: int = 252) -> pd.DataFrame:
        end_date = timezone.now()
        start_date = end_date - timedelta(days=lookback_days)

        queryset = ActivoPortafolioSnapshot.objects.filter(
            simbolo__in=activos,
            fecha_extraccion__range=(start_date, end_date),
        ).values("fecha_extraccion", "simbolo", "valorizado")

        df = pd.DataFrame(list(queryset))
        if df.empty:
            return pd.DataFrame()

        df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"])
        df["valorizado"] = pd.to_numeric(df["valorizado"], errors="coerce")
        pivot = (
            df.pivot_table(
                index="fecha_extraccion",
                columns="simbolo",
                values="valorizado",
                aggfunc="last",
            )
            .sort_index()
            .ffill()
        )

        # Restringir a activos solicitados y con presencia real de datos
        pivot = pivot.reindex(columns=activos)
        pivot = pivot.dropna(how="all")
        if pivot.shape[0] < 2:
            return pd.DataFrame()

        returns = pivot.pct_change().dropna(how="any")
        return returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")

    def expected_returns_annualized(self, returns: pd.DataFrame) -> np.ndarray:
        if returns.empty:
            return np.array([])
        return returns.mean().values * self.TRADING_DAYS_PER_YEAR

    def covariance_matrix_annualized(self, returns: pd.DataFrame) -> np.ndarray:
        if returns.empty:
            return np.array([[]])
        cov = returns.cov().values * self.TRADING_DAYS_PER_YEAR
        # Regularización leve para estabilidad numérica
        cov += np.eye(cov.shape[0]) * 1e-8
        return cov
