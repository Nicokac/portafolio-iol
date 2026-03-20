import logging
from datetime import timedelta
from typing import Dict, List

import pandas as pd
from django.utils import timezone

from apps.core.services.performance.twr_service import TWRService
from apps.core.services.performance.attribution_service import AttributionService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.observability import timed
from apps.portafolio_iol.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class TemporalMetricsService:
    """Servicio para calculo de metricas temporales del portafolio."""

    ROBUST_HISTORY_DAYS = 60

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.volatility_service = VolatilityService()
        self.twr_service = TWRService()
        self.attribution_service = AttributionService()
        self.tracking_error_service = TrackingErrorService()
        self.var_service = VaRService()
        self.cvar_service = CVaRService()
        self.local_macro_service = LocalMacroSeriesService()

    def get_portfolio_returns(self, days: int = 30) -> Dict:
        logger.info(f"Calculating portfolio returns for last {days} days")
        with timed("metrics.returns.calc_ms"):
            return self._get_portfolio_returns(days)

    def _get_portfolio_returns(self, days: int) -> Dict:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha')

        if not snapshots.exists():
            logger.warning("No portfolio snapshots found for returns calculation")
            return self._fallback_returns_from_evolution(days)

        df = pd.DataFrame(list(snapshots.values('fecha', 'total_iol')))

        if df.empty or len(df) < 2:
            return self._fallback_returns_from_evolution(days)

        df['fecha'] = pd.to_datetime(df['fecha'])
        df['total_iol'] = pd.to_numeric(df['total_iol'], errors='coerce')
        df = df.set_index('fecha').sort_index()

        returns = {
            'observations': int(len(df.index)),
            'history_span_days': int((df.index.max() - df.index.min()).days),
            'requested_days': int(days),
        }
        returns['robust_history_min_days'] = self.ROBUST_HISTORY_DAYS
        returns['robust_history_available'] = returns['history_span_days'] >= self.ROBUST_HISTORY_DAYS

        if len(df) >= 2:
            initial_value = df['total_iol'].iloc[0]
            final_value = df['total_iol'].iloc[-1]
            total_return = (final_value - initial_value) / initial_value * 100
            returns['total_period_return'] = round(total_return, 2)

        monthly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=30))]
        if len(monthly_data) >= 2:
            monthly_return = (monthly_data['total_iol'].iloc[-1] - monthly_data['total_iol'].iloc[0]) / monthly_data['total_iol'].iloc[0] * 100
            returns['monthly_return'] = round(monthly_return, 2)

        weekly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=7))]
        if len(weekly_data) >= 2:
            weekly_return = (weekly_data['total_iol'].iloc[-1] - weekly_data['total_iol'].iloc[0]) / weekly_data['total_iol'].iloc[0] * 100
            returns['weekly_return'] = round(weekly_return, 2)

        if len(df) >= 2:
            daily_return = df['total_iol'].pct_change().iloc[-1] * 100
            returns['daily_return'] = round(daily_return, 2)

        if len(df) >= 2:
            returns['max_drawdown'] = round(self._calculate_max_drawdown(df['total_iol']), 2)

        twr_metrics = self.twr_service.calculate_twr(days=days)
        returns.update(twr_metrics)
        returns.update(self._get_real_ytd_metrics())

        logger.info(f"Calculated returns: {returns}")
        return returns

    def _fallback_returns_from_evolution(self, days: int) -> Dict:
        try:
            from apps.dashboard.selectors import get_evolucion_historica

            evolution = get_evolucion_historica(days=days, max_points=days)
            if not evolution or not evolution.get('tiene_datos'):
                return {}

            fechas = evolution.get('fechas', [])
            valores = evolution.get('total_iol', [])
            if len(fechas) < 2 or len(valores) < 2:
                return {}

            df = pd.DataFrame({'fecha': fechas, 'total_iol': valores})
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['total_iol'] = pd.to_numeric(df['total_iol'], errors='coerce')
            df = df.dropna(subset=['total_iol']).set_index('fecha').sort_index()
            if len(df) < 2:
                return {}

            returns = {
                'observations': int(len(df.index)),
                'history_span_days': int((df.index.max() - df.index.min()).days),
                'requested_days': int(days),
            }
            returns['robust_history_min_days'] = self.ROBUST_HISTORY_DAYS
            returns['robust_history_available'] = returns['history_span_days'] >= self.ROBUST_HISTORY_DAYS
            initial_value = df['total_iol'].iloc[0]
            final_value = df['total_iol'].iloc[-1]
            total_return = (final_value - initial_value) / initial_value * 100 if initial_value else 0
            returns['total_period_return'] = round(total_return, 2)

            if len(df) >= 2:
                daily_return = df['total_iol'].pct_change().iloc[-1] * 100
                returns['daily_return'] = round(daily_return, 2)

            weekly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=7))]
            if len(weekly_data) >= 2 and weekly_data['total_iol'].iloc[0]:
                weekly_return = (weekly_data['total_iol'].iloc[-1] - weekly_data['total_iol'].iloc[0]) / weekly_data['total_iol'].iloc[0] * 100
                returns['weekly_return'] = round(weekly_return, 2)

            monthly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=30))]
            if len(monthly_data) >= 2 and monthly_data['total_iol'].iloc[0]:
                monthly_return = (monthly_data['total_iol'].iloc[-1] - monthly_data['total_iol'].iloc[0]) / monthly_data['total_iol'].iloc[0] * 100
                returns['monthly_return'] = round(monthly_return, 2)

            returns['max_drawdown'] = round(self._calculate_max_drawdown(df['total_iol']), 2)

            returns['fallback_source'] = 'evolucion_historica'
            returns.update(self._get_real_ytd_metrics())
            return returns
        except Exception as exc:
            logger.warning("Fallback returns from evolution failed: %s", exc)
            return {}

    @staticmethod
    def _calculate_max_drawdown(series: pd.Series) -> float:
        values = pd.to_numeric(pd.Series(series), errors='coerce').dropna()
        if len(values) < 2:
            return 0.0

        running_max = values.cummax()
        drawdown = ((values - running_max) / running_max.replace(0, pd.NA)) * 100
        drawdown = drawdown.fillna(0.0)
        return float(drawdown.min())

    def _get_real_ytd_metrics(self) -> Dict:
        macro_context = self.local_macro_service.get_context_summary()
        real_history = self.local_macro_service.get_real_historical_metrics(days=365)
        return {
            'portfolio_return_ytd_nominal': macro_context.get('portfolio_return_ytd_nominal'),
            'portfolio_return_ytd_real': macro_context.get('portfolio_return_ytd_real'),
            'portfolio_return_ytd_is_partial': macro_context.get('portfolio_return_ytd_is_partial'),
            'portfolio_return_ytd_base_date': (
                macro_context.get('portfolio_return_ytd_base_date').isoformat()
                if macro_context.get('portfolio_return_ytd_base_date')
                else None
            ),
            'ipc_ytd': macro_context.get('ipc_nacional_variation_ytd'),
            'badlar_privada': macro_context.get('badlar_privada'),
            'badlar_ytd': macro_context.get('badlar_ytd'),
            'portfolio_excess_ytd_vs_badlar': macro_context.get('portfolio_excess_ytd_vs_badlar'),
            'max_drawdown_real': real_history.get('max_drawdown_real'),
            'badlar_privada_date': (
                macro_context.get('badlar_privada_date').isoformat()
                if macro_context.get('badlar_privada_date')
                else None
            ),
        }

    def get_portfolio_volatility(self, days: int = 30) -> Dict:
        logger.info(f"Calculating portfolio volatility for last {days} days")
        with timed("metrics.volatility.calc_ms"):
            volatility = self.volatility_service.calculate_volatility(days=days)
        logger.info(f"Calculated volatility: {volatility}")
        return volatility

    def get_performance_metrics(self, days: int = 90) -> Dict:
        logger.info(f"Calculating comprehensive performance metrics for last {days} days")
        with timed("metrics.performance.calc_ms"):
            return self._get_performance_metrics(days)

    def _get_performance_metrics(self, days: int) -> Dict:
        returns = self.get_portfolio_returns(days)
        volatility = self.get_portfolio_volatility(days)
        var = self.var_service.calculate_var_set()
        cvar = self.cvar_service.calculate_cvar_set()
        benchmarking = self.tracking_error_service.calculate(days=days)

        metrics = {
            'returns': returns,
            'volatility': volatility,
            'var': var,
            'cvar': cvar,
            'attribution': self.attribution_service.calculate_attribution(days=days),
            'benchmarking': benchmarking,
            'period_days': days,
            'calculated_at': timezone.now().isoformat(),
            'fallback_sources': self._collect_fallback_sources(
                returns=returns,
                volatility=volatility,
                var=var,
                cvar=cvar,
                benchmarking=benchmarking,
            ),
        }

        if returns and volatility:
            if 'max_drawdown' in returns and returns['max_drawdown'] != 0:
                if 'annualized_volatility' in volatility:
                    calmar_ratio = abs(volatility.get('annualized_volatility', 0) / returns['max_drawdown'])
                    metrics['calmar_ratio'] = round(calmar_ratio, 2)

        logger.info(f"Performance metrics calculated: {len(metrics)} categories")
        return metrics

    def get_historical_comparison(self, periods: List[int] = [7, 30, 90, 180]) -> Dict:
        logger.info(f"Comparing performance across periods: {periods}")

        comparison = {}
        for period in periods:
            returns = self.get_portfolio_returns(period)
            if returns:
                volatility = self.get_portfolio_volatility(period)
                history_span_days = int(returns.get('history_span_days', 0) or 0)
                comparison[f'{period}d'] = {
                    'total_return': returns.get('total_period_return', 0),
                    'volatility': volatility.get('annualized_volatility'),
                    'available_history_days': history_span_days,
                    'observations': returns.get('observations'),
                    'is_partial_window': history_span_days < period,
                    'returns_fallback_source': returns.get('fallback_source'),
                    'volatility_fallback_source': volatility.get('fallback_source'),
                    'volatility_proxy_coverage_pct': volatility.get('proxy_coverage_pct'),
                }

        logger.info(f"Historical comparison: {comparison}")
        return comparison

    @staticmethod
    def _collect_fallback_sources(**sections: Dict) -> Dict[str, str]:
        return {
            key: value.get('fallback_source')
            for key, value in sections.items()
            if isinstance(value, dict) and value.get('fallback_source')
        }
