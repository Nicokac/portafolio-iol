from datetime import timedelta
from typing import Dict

import pandas as pd
from django.utils import timezone

from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.performance.twr_service import TWRService
from apps.portafolio_iol.models import PortfolioSnapshot


class VolatilityService:
    """Calculo de volatilidad historica sobre retornos diarios netos de flujos."""

    TRADING_DAYS_PER_YEAR = 252
    MIN_OBSERVATIONS = 5
    MAX_ABS_DAILY_RETURN = 0.50

    def __init__(self, local_macro_service: LocalMacroSeriesService | None = None, twr_service: TWRService | None = None):
        self.local_macro_service = local_macro_service or LocalMacroSeriesService()
        self.twr_service = twr_service or TWRService()

    def calculate_volatility(self, days: int = 30) -> Dict[str, float]:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        observations = snapshots.count()
        if observations < self.MIN_OBSERVATIONS:
            return self._fallback_volatility_from_evolution(days, observations)

        returns = self.twr_service.build_daily_return_series(days=days)
        history_span_days = int((snapshots.last().fecha - snapshots.first().fecha).days) if observations >= 2 else 0
        result = self._build_volatility_result_from_returns(
            returns=returns,
            observations=observations,
            history_span_days=history_span_days,
        )
        if result.get("warning"):
            return self._fallback_volatility_from_evolution(days, observations)
        return result

    def _fallback_volatility_from_evolution(self, days: int, observations: int) -> Dict[str, float]:
        try:
            from apps.dashboard.selectors import get_evolucion_historica

            evolution = get_evolucion_historica(days=days, max_points=days)
            if not evolution or not evolution.get("tiene_datos"):
                return {
                    "warning": "insufficient_history",
                    "required_min_observations": self.MIN_OBSERVATIONS,
                    "observations": observations,
                }

            df = pd.DataFrame(
                {
                    "fecha": evolution.get("fechas", []),
                    "total_iol": evolution.get("total_iol", []),
                }
            )
            if df.empty or len(df) < self.MIN_OBSERVATIONS:
                return {
                    "warning": "insufficient_history",
                    "required_min_observations": self.MIN_OBSERVATIONS,
                    "observations": observations,
                }

            df["fecha"] = pd.to_datetime(df["fecha"])
            df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
            df = df.dropna(subset=["total_iol"]).set_index("fecha").sort_index()
            returns = self.twr_service._build_return_series_from_frame(
                df,
                df.index.min().date(),
                df.index.max().date(),
            )
            result = self._build_volatility_result_from_returns(
                returns=returns,
                observations=int(len(df.index)),
                history_span_days=int((df.index.max() - df.index.min()).days) if len(df.index) >= 2 else 0,
            )
            if result.get("warning"):
                result["observations"] = observations
                return result
            result["fallback_source"] = "evolucion_historica"
            return result
        except Exception:
            return {
                "warning": "insufficient_history",
                "required_min_observations": self.MIN_OBSERVATIONS,
                "observations": observations,
            }

    def _build_volatility_result(self, df: pd.DataFrame) -> Dict[str, float]:
        returns = df["total_iol"].pct_change().dropna()
        history_span_days = int((df.index.max() - df.index.min()).days) if len(df.index) >= 2 else 0
        return self._build_volatility_result_from_returns(
            returns=returns,
            observations=int(len(df.index)),
            history_span_days=history_span_days,
        )

    def _build_volatility_result_from_returns(
        self,
        returns: pd.Series,
        observations: int,
        history_span_days: int,
    ) -> Dict[str, float]:
        if returns is None:
            returns = pd.Series(dtype=float)

        returns = pd.to_numeric(returns, errors="coerce").dropna()
        raw_observations = int(len(returns))
        returns = returns[returns.abs() <= self.MAX_ABS_DAILY_RETURN]
        if returns.empty or len(returns) < 2 or observations < self.MIN_OBSERVATIONS:
            return {
                "warning": "insufficient_history",
                "required_min_observations": self.MIN_OBSERVATIONS,
                "observations": int(observations),
            }

        daily_vol = float(returns.std())
        annualized_vol = daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)

        result = {
            "daily_volatility": round(daily_vol * 100, 2),
            "annualized_volatility": round(annualized_vol * 100, 2),
            "sample_size": int(len(returns)),
            "outlier_returns_filtered": raw_observations - int(len(returns)),
            "history_span_days": history_span_days,
            "observations": int(observations),
            "returns_basis": "net_of_flows",
        }

        mean_return = float(returns.mean())
        if daily_vol > 0:
            sharpe = mean_return / daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)
            result["sharpe_ratio"] = round(sharpe, 2)

            try:
                badlar_returns = self.local_macro_service.build_rate_returns(
                    "badlar_privada",
                    returns.index,
                    periods_per_year=self.TRADING_DAYS_PER_YEAR,
                )
            except Exception:
                badlar_returns = pd.Series(dtype=float)
            if not badlar_returns.empty:
                excess_returns = returns.sub(badlar_returns.fillna(0.0), fill_value=0.0)
                sharpe_badlar = float(excess_returns.mean()) / daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)
                result["sharpe_ratio_badlar"] = round(sharpe_badlar, 2)

        downside = returns[returns < 0]
        if not downside.empty:
            downside_vol = float(downside.std())
            if downside_vol > 0:
                sortino = mean_return / downside_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)
                result["sortino_ratio"] = round(sortino, 2)

        return result
