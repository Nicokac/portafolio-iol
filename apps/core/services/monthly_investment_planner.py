import logging
from typing import Dict, List, Optional
from decimal import Decimal

from apps.dashboard.selectors import get_dashboard_kpis
from apps.portafolio_iol.models import ActivoPortafolioSnapshot as Activo

logger = logging.getLogger(__name__)


class MonthlyInvestmentPlanner:
    """
    Planificador de aportes mensuales con distribución automática.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Configuración por defecto de asignación mensual
        self.default_allocation = {
            'SPY': 40,    # S&P 500
            'EEM': 20,    # Mercados emergentes
            'CEDEAR_USA': 20,  # CEDEARs de empresas USA
            'BONOS': 10,  # Bonos
            'LIQUIDEZ': 10  # Liquidez
        }

    def plan_monthly_investment(self, monthly_amount: Decimal,
                               current_portfolio: Optional[Dict] = None,
                               custom_allocation: Optional[Dict[str, float]] = None) -> Dict:
        """
        Planifica la distribución de un aporte mensual.

        Args:
            monthly_amount: Monto mensual a invertir
            current_portfolio: Estado actual del portafolio (opcional)
            custom_allocation: Asignación personalizada (opcional)

        Returns:
            Dict con plan de inversión mensual
        """
        logger.info(f"Planning monthly investment of {monthly_amount}")

        try:
            monthly_amount = Decimal(str(monthly_amount))
            # Usar asignaciÃ³n personalizada o por defecto
            allocation = custom_allocation or self.default_allocation

            # Validar que la asignación sume 100%
            total_allocation = sum(allocation.values())
            if abs(total_allocation - 100) > 0.1:
                return {'error': f'La asignación debe sumar 100%. Suma actual: {total_allocation}'}

            # Calcular distribución por activo
            distribution = {}
            for asset, percentage in allocation.items():
                amount = monthly_amount * Decimal(str(percentage / 100))
                distribution[asset] = {
                    'porcentaje': percentage,
                    'monto': float(amount),
                    'cantidad_estimada': self._estimate_quantity(asset, amount)
                }

            # Obtener estado actual para contexto
            if not current_portfolio:
                current_portfolio = get_dashboard_kpis()

            total_actual = Decimal(str(current_portfolio.get('total_iol', 0)))
            nuevo_total = total_actual + monthly_amount

            # Calcular impacto en el portafolio
            impacto = self._calculate_portfolio_impact(distribution, current_portfolio, nuevo_total)

            resultado = {
                'aporte_mensual': float(monthly_amount),
                'distribucion': distribution,
                'total_portafolio_actual': float(total_actual),
                'total_portafolio_nuevo': float(nuevo_total),
                'incremento_porcentual': float((monthly_amount / total_actual) * 100),
                'impacto_portafolio': impacto,
                'recomendaciones_adicionales': self._generate_additional_recommendations(distribution, current_portfolio)
            }

            logger.info("Monthly investment plan completed")
            return resultado

        except Exception as e:
            logger.error(f"Error planning monthly investment: {str(e)}")
            return {'error': str(e)}

    def create_custom_plan(self, monthly_amount: Decimal,
                          risk_profile: str,
                          investment_horizon: str,
                          current_portfolio: Optional[Dict] = None) -> Dict:
        """
        Crea un plan personalizado basado en perfil de riesgo e horizonte.

        Args:
            monthly_amount: Monto mensual
            risk_profile: 'conservador', 'moderado', 'agresivo'
            investment_horizon: 'corto', 'medio', 'largo'
            current_portfolio: Estado actual del portafolio

        Returns:
            Dict con plan personalizado
        """
        logger.info(f"Creating custom plan for {risk_profile} risk profile, {investment_horizon} horizon")

        try:
            # Definir asignaciones por perfil
            allocations = {
                'conservador': {
                    'LIQUIDEZ': 30,
                    'BONOS': 40,
                    'SPY': 20,
                    'EEM': 10
                },
                'moderado': {
                    'LIQUIDEZ': 15,
                    'BONOS': 25,
                    'SPY': 35,
                    'EEM': 15,
                    'CEDEAR_USA': 10
                },
                'agresivo': {
                    'SPY': 45,
                    'EEM': 25,
                    'CEDEAR_USA': 20,
                    'BONOS': 5,
                    'LIQUIDEZ': 5
                }
            }

            # Ajustar por horizonte temporal
            allocation = allocations.get(risk_profile, self.default_allocation).copy()

            if investment_horizon == 'corto':
                # Más conservador para horizontes cortos
                allocation['LIQUIDEZ'] = allocation.get('LIQUIDEZ', 0) + 10
                allocation['BONOS'] = allocation.get('BONOS', 0) + 5
                allocation['SPY'] = max(0, allocation.get('SPY', 0) - 15)
            elif investment_horizon == 'largo':
                # Más agresivo para horizontes largos
                allocation['LIQUIDEZ'] = max(0, allocation.get('LIQUIDEZ', 0) - 5)
                allocation['SPY'] = allocation.get('SPY', 0) + 5

            return self.plan_monthly_investment(monthly_amount, current_portfolio, allocation)

        except Exception as e:
            logger.error(f"Error creating custom plan: {str(e)}")
            return {'error': str(e)}

    def _estimate_quantity(self, asset_symbol: str, amount: Decimal) -> Optional[float]:
        """Estima cantidad de activos a comprar."""
        try:
            # Obtener precio del activo
            if asset_symbol in ['LIQUIDEZ', 'BONOS']:
                return None  # No aplicable para estos tipos

            activo = Activo.objects.filter(simbolo__icontains=asset_symbol.split('_')[0]).first()
            if activo and activo.precio_actual:
                return float(amount / activo.precio_actual)

        except Exception as e:
            logger.error(f"Error estimating quantity for {asset_symbol}: {str(e)}")

        return None

    def _calculate_portfolio_impact(self, distribution: Dict,
                                   current_portfolio: Dict,
                                   nuevo_total: Decimal) -> Dict:
        """Calcula el impacto del aporte en el portafolio."""
        impacto = {
            'cambio_liquidez': 0,
            'cambio_acciones_usa': 0,
            'cambio_emergentes': 0,
            'cambio_bonos': 0,
            'nueva_diversificacion': 'neutra'
        }

        try:
            # Calcular cambios aproximados
            for asset, data in distribution.items():
                percentage = data['porcentaje']

                if 'LIQUIDEZ' in asset:
                    impacto['cambio_liquidez'] += percentage
                elif 'SPY' in asset:
                    impacto['cambio_acciones_usa'] += percentage
                elif 'EEM' in asset:
                    impacto['cambio_emergentes'] += percentage
                elif 'BONOS' in asset:
                    impacto['cambio_bonos'] += percentage

            # Evaluar diversificación
            total_exposicion_argentina = sum(p for a, p in impacto.items()
                                           if 'argentina' in a.lower() or 'cede' in a.lower())

            if total_exposicion_argentina > 50:
                impacto['nueva_diversificacion'] = 'concentrada_argentina'
            elif impacto['cambio_acciones_usa'] > 30:
                impacto['nueva_diversificacion'] = 'equilibrada_global'
            else:
                impacto['nueva_diversificacion'] = 'diversificada'

        except Exception as e:
            logger.error(f"Error calculating portfolio impact: {str(e)}")

        return impacto

    def _generate_additional_recommendations(self, distribution: Dict,
                                           current_portfolio: Dict) -> List[str]:
        """Genera recomendaciones adicionales para el plan mensual."""
        recommendations = []

        try:
            # Recomendaciones basadas en el aporte
            total_amount = sum(data['monto'] for data in distribution.values())

            if total_amount < 100000:
                recommendations.append("Considera aumentar el aporte mensual para impacto significativo")
            elif total_amount > 1000000:
                recommendations.append("Monto elevado - considera diversificar en más activos")

            # Recomendaciones basadas en concentración
            spy_allocation = sum(data['porcentaje'] for asset, data in distribution.items()
                               if 'SPY' in asset)

            if spy_allocation > 60:
                recommendations.append("Alta concentración en SPY - considera diversificar en otros ETFs")

            # Recomendaciones de timing
            recommendations.append("Considera promediar el aporte durante el mes para reducir volatilidad")

        except Exception as e:
            logger.error(f"Error generating additional recommendations: {str(e)}")

        return recommendations