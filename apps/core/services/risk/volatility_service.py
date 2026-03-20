from datetime import timedelta
from typing import Dict

import pandas as pd
from django.db.models import Max
from django.utils import timezone

from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.performance.twr_service import TWRService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


class VolatilityService:
    """Calculo de volatilidad historica sobre retornos diarios netos de flujos."""

    TRADING_DAYS_PER_YEAR = 252
    MIN_OBSERVATIONS = 5
    MAX_ABS_DAILY_RETURN = 0.50

    def __init__(
        self,
        local_macro_service: LocalMacroSeriesService | None = None,
        twr_service: TWRService | None = None,
        historical_price_service: IOLHistoricalPriceService | None = None,
    ):
        self.local_macro_service = local_macro_service or LocalMacroSeriesService()
        self.twr_service = twr_service or TWRService()
        self.historical_price_service = historical_price_service or IOLHistoricalPriceService()

    def calculate_volatility(self, days: int = 30) -> Dict[str, float]:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        observations = snapshots.count()
        if observations < self.MIN_OBSERVATIONS:
            iol_result = self._fallback_volatility_from_iol_historical_prices(days=days, observations=observations)
            if not iol_result.get("warning"):
                return iol_result
            return {
                "warning": "insufficient_history",
                "required_min_observations": self.MIN_OBSERVATIONS,
                "observations": observations,
            }

        returns = self.twr_service.build_daily_return_series(days=days)
        history_span_days = int((snapshots.last().fecha - snapshots.first().fecha).days) if observations >= 2 else 0
        result = self._build_volatility_result_from_returns(
            returns=returns,
            observations=observations,
            history_span_days=history_span_days,
        )
        return result

    def _fallback_volatility_from_iol_historical_prices(self, days: int, observations: int) -> Dict[str, float]:
        proxy_returns = self._build_iol_proxy_return_series(days=days)
        proxy_observations = int(len(proxy_returns.index) + 1) if not proxy_returns.empty else 0
        history_span_days = (
            int((proxy_returns.index.max() - proxy_returns.index.min()).days)
            if len(proxy_returns.index) >= 2
            else 0
        )
        result = self._build_volatility_result_from_returns(
            returns=proxy_returns,
            observations=proxy_observations,
            history_span_days=history_span_days,
        )
        if result.get("warning"):
            result["observations"] = int(observations)
            return result

        result["fallback_source"] = "iol_historical_prices_proxy"
        result["returns_basis"] = "current_weights_proxy"
        result["proxy_observations"] = proxy_observations
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

    def _build_iol_proxy_return_series(self, days: int) -> pd.Series:
        latest_extraction = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
        if not latest_extraction:
            return pd.Series(dtype=float)

        positions = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_extraction)
            .exclude(simbolo__isnull=True)
            .exclude(simbolo="")
            .exclude(mercado__isnull=True)
            .exclude(mercado="")
            .values("simbolo", "mercado", "valorizado")
        )
        if not positions:
            return pd.Series(dtype=float)

        total_value = sum(float(position["valorizado"] or 0.0) for position in positions)
        if total_value <= 0:
            return pd.Series(dtype=float)

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        business_dates = pd.bdate_range(start=start_date, end=end_date)
        if len(business_dates) < 2:
            return pd.Series(dtype=float)

        weighted_returns = []
        for position in positions:
            symbol = position["simbolo"]
            market = position["mercado"]
            series = self.historical_price_service.build_close_series(symbol, market, business_dates)
            if series.empty or len(series.dropna()) < 2:
                continue

            asset_returns = pd.to_numeric(series, errors="coerce").pct_change().dropna()
            if asset_returns.empty:
                continue

            weight = float(position["valorizado"] or 0.0) / total_value
            weighted_returns.append(asset_returns.mul(weight))

        if not weighted_returns:
            return pd.Series(dtype=float)

        proxy_returns = pd.concat(weighted_returns, axis=1).fillna(0.0).sum(axis=1)
        return pd.to_numeric(proxy_returns, errors="coerce").dropna().sort_index()

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
