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
from apps.portafolio_iol.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class TemporalMetricsService:
    """Servicio para cálculo de métricas temporales del portafolio."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.volatility_service = VolatilityService()
        self.twr_service = TWRService()
        self.attribution_service = AttributionService()
        self.tracking_error_service = TrackingErrorService()
        self.var_service = VaRService()
        self.cvar_service = CVaRService()

    def get_portfolio_returns(self, days: int = 30) -> Dict:
        """
        Calcula retornos del portafolio para diferentes períodos.

        Args:
            days: Número de días hacia atrás para calcular

        Returns:
            Dict con retornos diarios, semanales, mensuales
        """
        logger.info(f"Calculating portfolio returns for last {days} days")

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Obtener snapshots ordenados por fecha
        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha')

        if not snapshots.exists():
            logger.warning("No portfolio snapshots found for returns calculation")
            return {}

        # Crear DataFrame con datos históricos
        df = pd.DataFrame(list(snapshots.values('fecha', 'total_iol')))

        if df.empty:
            return {}

        df['fecha'] = pd.to_datetime(df['fecha'])
        df['total_iol'] = pd.to_numeric(df['total_iol'], errors='coerce')
        df = df.set_index('fecha').sort_index()

        # Calcular retornos
        returns = {}

        # Retorno total del período
        if len(df) >= 2:
            initial_value = df['total_iol'].iloc[0]
            final_value = df['total_iol'].iloc[-1]
            total_return = (final_value - initial_value) / initial_value * 100
            returns['total_period_return'] = round(total_return, 2)

        # Retorno mensual (últimos 30 días)
        monthly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=30))]
        if len(monthly_data) >= 2:
            monthly_return = (monthly_data['total_iol'].iloc[-1] - monthly_data['total_iol'].iloc[0]) / monthly_data['total_iol'].iloc[0] * 100
            returns['monthly_return'] = round(monthly_return, 2)

        # Retorno semanal (últimos 7 días)
        weekly_data = df.loc[df.index >= (df.index.max() - pd.Timedelta(days=7))]
        if len(weekly_data) >= 2:
            weekly_return = (weekly_data['total_iol'].iloc[-1] - weekly_data['total_iol'].iloc[0]) / weekly_data['total_iol'].iloc[0] * 100
            returns['weekly_return'] = round(weekly_return, 2)

        # Retorno diario (último día)
        if len(df) >= 2:
            daily_return = df['total_iol'].pct_change().iloc[-1] * 100
            returns['daily_return'] = round(daily_return, 2)

        # Máximo drawdown del período
        if len(df) >= 2:
            cumulative = (1 + df['total_iol'].pct_change()).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max * 100
            max_drawdown = drawdown.min()
            returns['max_drawdown'] = round(max_drawdown, 2)

        # TWR: retorno neutralizando (estimación de) flujos externos
        twr_metrics = self.twr_service.calculate_twr(days=days)
        returns.update(twr_metrics)

        logger.info(f"Calculated returns: {returns}")
        return returns

    def get_portfolio_volatility(self, days: int = 30) -> Dict:
        """
        Calcula volatilidad histórica del portafolio.

        Args:
            days: Número de días para calcular volatilidad

        Returns:
            Dict con volatilidad diaria, anualizada, etc.
        """
        logger.info(f"Calculating portfolio volatility for last {days} days")
        volatility = self.volatility_service.calculate_volatility(days=days)
        logger.info(f"Calculated volatility: {volatility}")
        return volatility

    def get_performance_metrics(self, days: int = 90) -> Dict:
        """
        Calcula métricas de performance completas.

        Args:
            days: Número de días para análisis

        Returns:
            Dict con todas las métricas de performance
        """
        logger.info(f"Calculating comprehensive performance metrics for last {days} days")

        returns = self.get_portfolio_returns(days)
        volatility = self.get_portfolio_volatility(days)

        # Combinar métricas
        metrics = {
            'returns': returns,
            'volatility': volatility,
            'var': self.var_service.calculate_var_set(),
            'cvar': self.cvar_service.calculate_cvar_set(),
            'attribution': self.attribution_service.calculate_attribution(days=days),
            'benchmarking': self.tracking_error_service.calculate(days=days),
            'period_days': days,
            'calculated_at': timezone.now().isoformat()
        }

        # Métricas adicionales
        if returns and volatility:
            # Calmar ratio (retorno anualizado / max drawdown)
            if 'max_drawdown' in returns and returns['max_drawdown'] != 0:
                if 'annualized_volatility' in volatility:
                    # Usar volatilidad como proxy de retorno si no hay retorno total
                    calmar_ratio = abs(volatility.get('annualized_volatility', 0) / returns['max_drawdown'])
                    metrics['calmar_ratio'] = round(calmar_ratio, 2)

        logger.info(f"Performance metrics calculated: {len(metrics)} categories")
        return metrics

    def get_historical_comparison(self, periods: List[int] = [7, 30, 90, 180]) -> Dict:
        """
        Compara performance en diferentes períodos históricos.

        Args:
            periods: Lista de períodos en días

        Returns:
            Dict con comparación de retornos por período
        """
        logger.info(f"Comparing performance across periods: {periods}")

        comparison = {}
        for period in periods:
            returns = self.get_portfolio_returns(period)
            if returns:
                comparison[f'{period}d'] = {
                    'total_return': returns.get('total_period_return', 0),
                    'volatility': self.get_portfolio_volatility(period).get('annualized_volatility', 0)
                }

        logger.info(f"Historical comparison: {comparison}")
        return comparison
