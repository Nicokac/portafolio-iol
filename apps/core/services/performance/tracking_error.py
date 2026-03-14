from datetime import timedelta
import math
from typing import Dict

import pandas as pd
from django.db.models import Max
from django.utils import timezone

from apps.core.config.parametros_benchmark import ParametrosBenchmark
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class TrackingErrorService:
    """Calculo de Tracking Error e Information Ratio contra benchmark compuesto."""

    TRADING_DAYS_PER_YEAR = 252
    TRADING_WEEKS_PER_YEAR = 52

    def __init__(
        self,
        benchmark_service: BenchmarkSeriesService | None = None,
        local_macro_service: LocalMacroSeriesService | None = None,
    ):
        self.benchmark_service = benchmark_service or BenchmarkSeriesService()
        self.local_macro_service = local_macro_service or LocalMacroSeriesService()

    def calculate(self, days: int = 90) -> Dict[str, float]:
        portfolio_returns, benchmark_returns, frequency_used = self._resolve_return_series(days=days)
        if portfolio_returns.empty or benchmark_returns.empty:
            observations = int(len(portfolio_returns)) if not portfolio_returns.empty else 0
            return {
                "warning": "insufficient_history",
                "observations": observations,
                "requested_days": days,
            }

        active_returns = portfolio_returns - benchmark_returns
        if active_returns.empty:
            return {
                "warning": "insufficient_history",
                "observations": int(len(portfolio_returns)),
                "requested_days": days,
            }

        annualization_factor = self.TRADING_DAYS_PER_YEAR if frequency_used == "daily" else self.TRADING_WEEKS_PER_YEAR
        tracking_error = float(active_returns.std()) * (annualization_factor ** 0.5) * 100

        portfolio_total_return = float((1 + portfolio_returns).prod() - 1) * 100
        benchmark_total_return = float((1 + benchmark_returns).prod() - 1) * 100
        excess_return = portfolio_total_return - benchmark_total_return

        information_ratio = None
        if math.isfinite(tracking_error) and tracking_error > 0:
            information_ratio = excess_return / tracking_error
        else:
            tracking_error = None

        result = {
            "portfolio_return_period": round(portfolio_total_return, 2),
            "benchmark_return_period": round(benchmark_total_return, 2),
            "excess_return_period": round(excess_return, 2),
            "observations": int(len(portfolio_returns)),
            "requested_days": days,
            "benchmark_frequency_used": frequency_used,
        }
        if tracking_error is not None:
            result["tracking_error_annualized"] = round(tracking_error, 2)
        else:
            result["warning"] = "insufficient_history"
        if information_ratio is not None:
            result["information_ratio"] = round(information_ratio, 2)
        return result

    def build_comparison_curve(self, days: int = 365, base_value: float = 100.0) -> Dict[str, object]:
        portfolio_returns, benchmark_returns, frequency_used = self._resolve_return_series(days=days)
        if portfolio_returns.empty or benchmark_returns.empty:
            observations = int(len(portfolio_returns)) if not portfolio_returns.empty else 0
            return {
                "warning": "insufficient_history",
                "requested_days": days,
                "observations": observations,
                "series": [],
            }

        portfolio_curve = (1 + portfolio_returns).cumprod() * base_value
        benchmark_curve = (1 + benchmark_returns).cumprod() * base_value

        series = [
            {
                "fecha": idx.date().isoformat(),
                "portfolio": round(float(portfolio_curve.loc[idx]), 2),
                "benchmark": round(float(benchmark_curve.loc[idx]), 2),
            }
            for idx in portfolio_curve.index
            if idx in benchmark_curve.index
        ]
        return {
            "requested_days": days,
            "observations": len(series),
            "benchmark_frequency_used": frequency_used,
            "base_value": base_value,
            "series": series,
        }

    def _get_portfolio_returns(self, days: int) -> pd.Series:
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
        df = df.dropna(subset=["total_iol"]).set_index("fecha").sort_index()
        if len(df.index) < 2:
            return pd.Series(dtype=float)
        return df["total_iol"].pct_change().dropna()

    def _get_portfolio_weekly_returns(self, days: int) -> pd.Series:
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
        df = df.dropna(subset=["total_iol"]).set_index("fecha").sort_index()
        if df.empty:
            return pd.Series(dtype=float)

        weekly = df["total_iol"].resample("W-FRI").last().dropna()
        if len(weekly.index) < 2:
            return pd.Series(dtype=float)
        return weekly.pct_change().dropna()

    def _get_composite_benchmark_returns(self, index, frequency: str = "daily") -> pd.Series:
        weights = self._infer_weights_from_portfolio()
        annual_returns = ParametrosBenchmark.ANNUAL_RETURNS
        mappings = ParametrosBenchmark.BENCHMARK_MAPPINGS
        benchmark_returns = pd.Series(0.0, index=index, dtype=float)
        period_factor = self.TRADING_DAYS_PER_YEAR if frequency == "daily" else self.TRADING_WEEKS_PER_YEAR

        for key, weight in weights.items():
            if weight <= 0:
                continue

            if frequency == "daily":
                historical_returns = self.benchmark_service.build_daily_returns(key, index)
            else:
                historical_returns = self.benchmark_service.build_weekly_returns(key, index)

            if key == "liquidez":
                periods_per_year = self.TRADING_DAYS_PER_YEAR if frequency == "daily" else self.TRADING_WEEKS_PER_YEAR
                local_rate_returns = self.local_macro_service.build_rate_returns(
                    "badlar_privada",
                    index,
                    periods_per_year=periods_per_year,
                )
                if not local_rate_returns.empty:
                    historical_returns = local_rate_returns

            fallback_period_return = annual_returns[mappings[key]] / period_factor
            if historical_returns.empty:
                benchmark_returns = benchmark_returns.add(
                    weight * fallback_period_return,
                    fill_value=0.0,
                )
            else:
                benchmark_returns = benchmark_returns.add(
                    historical_returns.fillna(fallback_period_return) * weight,
                    fill_value=0.0,
                )

        return benchmark_returns.astype(float)

    def _resolve_return_series(self, days: int):
        daily_portfolio_returns = self._get_portfolio_returns(days=days)
        weekly_portfolio_returns = self._get_portfolio_weekly_returns(days=days)

        daily_historical_observations = self._count_historical_observations(
            daily_portfolio_returns.index,
            frequency="daily",
        ) if not daily_portfolio_returns.empty else 0
        weekly_historical_observations = self._count_historical_observations(
            weekly_portfolio_returns.index,
            frequency="weekly",
        ) if not weekly_portfolio_returns.empty else 0

        if daily_historical_observations >= max(2, weekly_historical_observations):
            daily_benchmark_returns = self._get_composite_benchmark_returns(
                daily_portfolio_returns.index,
                frequency="daily",
            )
            return daily_portfolio_returns, daily_benchmark_returns, "daily"
        if weekly_historical_observations >= 2:
            weekly_benchmark_returns = self._get_composite_benchmark_returns(
                weekly_portfolio_returns.index,
                frequency="weekly",
            )
            return weekly_portfolio_returns, weekly_benchmark_returns, "weekly"
        daily_benchmark_returns = self._get_composite_benchmark_returns(
            daily_portfolio_returns.index,
            frequency="daily",
        ) if not daily_portfolio_returns.empty else pd.Series(dtype=float)
        return daily_portfolio_returns, daily_benchmark_returns, "daily"

    def _count_historical_observations(self, index, frequency: str) -> int:
        weights = self._infer_weights_from_portfolio()
        observations = 0

        for key, weight in weights.items():
            if weight <= 0:
                continue
            if frequency == "daily":
                series = self.benchmark_service.build_daily_returns(key, index)
            else:
                series = self.benchmark_service.build_weekly_returns(key, index)
            if key == "liquidez":
                periods_per_year = self.TRADING_DAYS_PER_YEAR if frequency == "daily" else self.TRADING_WEEKS_PER_YEAR
                local_rate_returns = self.local_macro_service.build_rate_returns(
                    "badlar_privada",
                    index,
                    periods_per_year=periods_per_year,
                )
                if not local_rate_returns.empty:
                    series = local_rate_returns
            observations = max(observations, int(len(series.dropna())))

        return observations

    def _infer_weights_from_portfolio(self):
        latest_port = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]
        latest_resumen = ResumenCuentaSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]

        if not latest_port:
            return ParametrosBenchmark.DEFAULT_WEIGHTS.copy()

        activos = list(ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_port))
        if not activos:
            return ParametrosBenchmark.DEFAULT_WEIGHTS.copy()

        symbols = [a.simbolo for a in activos]
        params = {
            p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=symbols)
        }

        total_assets = sum(float(a.valorizado) for a in activos)
        cash = 0.0
        if latest_resumen:
            cuentas = ResumenCuentaSnapshot.objects.filter(fecha_extraccion=latest_resumen)
            cash = sum(float(c.disponible) for c in cuentas)

        total = total_assets + cash
        if total <= 0:
            return ParametrosBenchmark.DEFAULT_WEIGHTS.copy()

        cedear_usa = 0.0
        bonos_ar = 0.0
        for activo in activos:
            value = float(activo.valorizado)
            param = params.get(activo.simbolo)
            country = (param.pais_exposicion if param else "").lower()
            patrimonial = (param.tipo_patrimonial if param else "").lower()
            asset_type = (activo.tipo or "").upper()

            if country in {"usa", "estados unidos"} and asset_type == "CEDEARS":
                cedear_usa += value
            if country == "argentina" and ("bond" in patrimonial or asset_type == "TITULOSPUBLICOS"):
                bonos_ar += value

        liquidity = cash
        weights = {
            "cedear_usa": cedear_usa / total,
            "bonos_ar": bonos_ar / total,
            "liquidez": liquidity / total,
        }

        residual = 1 - sum(weights.values())
        if residual > 0:
            weights["cedear_usa"] += residual
        return weights
