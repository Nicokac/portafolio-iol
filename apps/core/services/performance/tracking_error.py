from datetime import timedelta
import math
from typing import Dict

import pandas as pd
from django.db.models import Max
from django.utils import timezone

from apps.core.config.parametros_benchmark import ParametrosBenchmark
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class TrackingErrorService:
    """Cálculo de Tracking Error e Information Ratio contra benchmark compuesto."""

    TRADING_DAYS_PER_YEAR = 252

    def calculate(self, days: int = 90) -> Dict[str, float]:
        portfolio_returns = self._get_portfolio_returns(days=days)
        if portfolio_returns.empty:
            return {
                "warning": "insufficient_history",
                "observations": 0,
                "requested_days": days,
            }

        benchmark_daily_return = self._get_composite_benchmark_daily_return()
        benchmark_returns = pd.Series(
            benchmark_daily_return, index=portfolio_returns.index, dtype=float
        )

        active_returns = portfolio_returns - benchmark_returns
        if active_returns.empty:
            return {
                "warning": "insufficient_history",
                "observations": int(len(portfolio_returns)),
                "requested_days": days,
            }

        tracking_error = float(active_returns.std()) * (self.TRADING_DAYS_PER_YEAR ** 0.5) * 100

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
        }
        if tracking_error is not None:
            result["tracking_error_annualized"] = round(tracking_error, 2)
        else:
            result["warning"] = "insufficient_history"
        if information_ratio is not None:
            result["information_ratio"] = round(information_ratio, 2)
        return result

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
        df = df.set_index("fecha").sort_index()
        return df["total_iol"].pct_change().dropna()

    def _get_composite_benchmark_daily_return(self) -> float:
        weights = self._infer_weights_from_portfolio()
        annual_returns = ParametrosBenchmark.ANNUAL_RETURNS
        mappings = ParametrosBenchmark.BENCHMARK_MAPPINGS

        annual_composite = (
            weights["cedear_usa"] * annual_returns[mappings["cedear_usa"]]
            + weights["bonos_ar"] * annual_returns[mappings["bonos_ar"]]
            + weights["liquidez"] * annual_returns[mappings["liquidez"]]
        )
        return annual_composite / self.TRADING_DAYS_PER_YEAR

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
