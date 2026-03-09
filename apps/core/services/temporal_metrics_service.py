import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from django.db.models import Sum
from django.utils import timezone

from apps.portafolio_iol.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class TemporalMetricsService:
    """Servicio para cálculo de métricas temporales del portafolio."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_portfolio_returns(self, days: int = 30) -> Dict:
        """
        Calcula retornos del portafolio para diferentes períodos.

        Args:
            days: Número de días hacia atrás para calcular

        Returns:
            Dict con retornos diarios, semanales, mensuales
        """
        logger.info(f"Calculating portfolio returns for last {days} days")

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Obtener snapshots ordenados por fecha
        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha')

        if not snapshots.exists():
            logger.warning("No portfolio snapshots found for returns calculation")
            return {}

        # Crear DataFrame con datos históricos
        df = pd.DataFrame(list(snapshots.values(
            'fecha', 'total_iol', 'total_portafolio', 'rendimiento_diario'
        )))

        if df.empty:
            return {}

        df['fecha'] = pd.to_datetime(df['fecha'])
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
        monthly_data = df.last('30D')
        if len(monthly_data) >= 2:
            monthly_return = (monthly_data['total_iol'].iloc[-1] - monthly_data['total_iol'].iloc[0]) / monthly_data['total_iol'].iloc[0] * 100
            returns['monthly_return'] = round(monthly_return, 2)

        # Retorno semanal (últimos 7 días)
        weekly_data = df.last('7D')
        if len(weekly_data) >= 2:
            weekly_return = (weekly_data['total_iol'].iloc[-1] - weekly_data['total_iol'].iloc[0]) / weekly_data['total_iol'].iloc[0] * 100
            returns['weekly_return'] = round(weekly_return, 2)

        # Retorno diario (último día)
        if len(df) >= 2:
            daily_return = df['rendimiento_diario'].iloc[-1] if pd.notna(df['rendimiento_diario'].iloc[-1]) else 0
            returns['daily_return'] = round(daily_return, 2)

        # Máximo drawdown del período
        if len(df) >= 2:
            cumulative = (1 + df['total_iol'].pct_change()).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max * 100
            max_drawdown = drawdown.min()
            returns['max_drawdown'] = round(max_drawdown, 2)

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

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha')

        if not snapshots.exists() or len(snapshots) < 2:
            logger.warning("Insufficient data for volatility calculation")
            return {}

        df = pd.DataFrame(list(snapshots.values('fecha', 'total_iol')))
        df['fecha'] = pd.to_datetime(df['fecha'])
        df = df.set_index('fecha').sort_index()

        # Calcular retornos diarios
        daily_returns = df['total_iol'].pct_change().dropna()

        if daily_returns.empty:
            return {}

        volatility = {}

        # Volatilidad diaria
        daily_vol = daily_returns.std()
        volatility['daily_volatility'] = round(daily_vol * 100, 2)

        # Volatilidad anualizada (asumiendo 252 días de trading)
        annualized_vol = daily_vol * (252 ** 0.5)
        volatility['annualized_volatility'] = round(annualized_vol * 100, 2)

        # Sharpe ratio (simplificado, asumiendo tasa libre de riesgo = 0)
        if daily_vol > 0:
            sharpe_ratio = daily_returns.mean() / daily_vol * (252 ** 0.5)
            volatility['sharpe_ratio'] = round(sharpe_ratio, 2)

        # Sortino ratio (solo pérdidas)
        downside_returns = daily_returns[daily_returns < 0]
        if not downside_returns.empty:
            downside_vol = downside_returns.std()
            if downside_vol > 0:
                sortino_ratio = daily_returns.mean() / downside_vol * (252 ** 0.5)
                volatility['sortino_ratio'] = round(sortino_ratio, 2)

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