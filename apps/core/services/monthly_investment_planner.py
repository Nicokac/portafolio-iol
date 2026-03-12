import logging
from typing import Dict, List, Optional
from decimal import Decimal

from apps.core.models import PortfolioParameters
from apps.dashboard.selectors import get_concentracion_pais
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
            # Usar asignación personalizada o por defecto
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
            base_allocation = allocations.get(risk_profile, self.default_allocation).copy()
            allocation = base_allocation.copy()

            if not current_portfolio:
                current_portfolio = get_dashboard_kpis()

            if investment_horizon == 'corto':
                # Más conservador para horizontes cortos
                allocation['LIQUIDEZ'] = allocation.get('LIQUIDEZ', 0) + 10
                allocation['BONOS'] = allocation.get('BONOS', 0) + 5
                allocation['SPY'] = max(0, allocation.get('SPY', 0) - 15)
            elif investment_horizon == 'largo':
                # Más agresivo para horizontes largos
                allocation['LIQUIDEZ'] = max(0, allocation.get('LIQUIDEZ', 0) - 5)
                allocation['SPY'] = allocation.get('SPY', 0) + 5

            # Ajuste principal por estado real del portafolio.
            dynamic_allocation, rationale = self._build_state_based_allocation(
                base_allocation=allocation,
                current_portfolio=current_portfolio,
                risk_profile=risk_profile,
            )

            # Mezcla para mantener coherencia de perfil pero responder al estado real.
            blend_factor = 0.65
            blended = {}
            keys = set(allocation.keys()) | set(dynamic_allocation.keys())
            for key in keys:
                base_value = float(allocation.get(key, 0))
                dyn_value = float(dynamic_allocation.get(key, 0))
                blended[key] = round((1 - blend_factor) * base_value + blend_factor * dyn_value, 2)

            allocation = self._normalize_allocation(blended)
            result = self.plan_monthly_investment(monthly_amount, current_portfolio, allocation)
            if isinstance(result, dict) and 'error' not in result:
                result['allocation_basis'] = {
                    'mode': rationale.get('mode'),
                    'targets': rationale.get('targets'),
                    'gaps': rationale.get('gaps'),
                    'base_allocation': allocation,
                }
            return result

        except Exception as e:
            logger.error(f"Error creating custom plan: {str(e)}")
            return {'error': str(e)}

    def _build_state_based_allocation(self, base_allocation: Dict[str, float],
                                      current_portfolio: Dict,
                                      risk_profile: str) -> tuple[Dict[str, float], Dict]:
        """
        Construye asignacion guiada por desvio entre exposicion actual y targets.
        """
        params = PortfolioParameters.get_active_parameters()
        if params:
            targets = {
                'liquidez': float(params.liquidez_target),
                'usa': float(params.usa_target),
                'argentina': float(params.argentina_target),
                'emerging': float(params.emerging_target),
            }
        else:
            targets = {'liquidez': 20.0, 'usa': 40.0, 'argentina': 30.0, 'emerging': 10.0}

        total_iol = float(current_portfolio.get('total_iol', 0) or 0)
        liq_oper = float(current_portfolio.get('liquidez_operativa', 0) or 0)
        fci_cash = float(current_portfolio.get('fci_cash_management', 0) or 0)
        current_liquidez = ((liq_oper + fci_cash) / total_iol * 100) if total_iol > 0 else 0

        pais_dist = get_concentracion_pais()
        current_usa = float(pais_dist.get('USA', 0) or 0)
        current_arg = float(pais_dist.get('Argentina', 0) or 0)
        current_em = sum(float(pais_dist.get(k, 0) or 0) for k in ['EM', 'Emergentes', 'China', 'Brasil', 'Latam'])

        gaps = {
            'liquidez': max(0.0, targets['liquidez'] - current_liquidez),
            'usa': max(0.0, targets['usa'] - current_usa),
            'argentina': max(0.0, targets['argentina'] - current_arg),
            'emerging': max(0.0, targets['emerging'] - current_em),
        }

        total_gap = sum(gaps.values())
        if total_gap <= 0:
            return base_allocation, {'mode': 'base_only', 'targets': targets, 'gaps': gaps}

        # Mapeo de buckets target -> instrumentos sugeridos para aporte mensual.
        alloc = {'LIQUIDEZ': 0.0, 'BONOS': 0.0, 'SPY': 0.0, 'EEM': 0.0, 'CEDEAR_USA': 0.0}
        alloc['LIQUIDEZ'] += (gaps['liquidez'] / total_gap) * 100
        usa_weight = (gaps['usa'] / total_gap) * 100
        alloc['SPY'] += usa_weight * 0.7
        alloc['CEDEAR_USA'] += usa_weight * 0.3
        alloc['BONOS'] += (gaps['argentina'] / total_gap) * 100
        alloc['EEM'] += (gaps['emerging'] / total_gap) * 100

        # Ajuste suave por perfil de riesgo.
        if risk_profile == 'conservador':
            alloc['LIQUIDEZ'] += 5
            alloc['BONOS'] += 5
            alloc['SPY'] = max(0, alloc['SPY'] - 5)
            alloc['CEDEAR_USA'] = max(0, alloc['CEDEAR_USA'] - 5)
        elif risk_profile == 'agresivo':
            alloc['LIQUIDEZ'] = max(0, alloc['LIQUIDEZ'] - 5)
            alloc['BONOS'] = max(0, alloc['BONOS'] - 5)
            alloc['SPY'] += 5
            alloc['CEDEAR_USA'] += 5

        normalized = self._normalize_allocation(alloc)
        return normalized, {'mode': 'state_based', 'targets': targets, 'gaps': gaps}

    @staticmethod
    def _normalize_allocation(allocation: Dict[str, float]) -> Dict[str, float]:
        cleaned = {k: max(0.0, float(v)) for k, v in allocation.items()}
        total = sum(cleaned.values())
        if total <= 0:
            return cleaned
        normalized = {k: round((v / total) * 100, 2) for k, v in cleaned.items()}
        # Ajuste de redondeo para cerrar en 100.
        drift = round(100 - sum(normalized.values()), 2)
        if abs(drift) > 0 and normalized:
            max_key = max(normalized, key=normalized.get)
            normalized[max_key] = round(normalized[max_key] + drift, 2)
        return normalized

    def _estimate_quantity(self, asset_symbol: str, amount: Decimal) -> Optional[float]:
        """Estima cantidad de activos a comprar."""
        try:
            # Obtener precio del activo
            if asset_symbol in ['LIQUIDEZ', 'BONOS']:
                return None  # No aplicable para estos tipos

            activo = Activo.objects.filter(simbolo__icontains=asset_symbol.split('_')[0]).first()
            if not activo:
                return None

            # ActivoPortafolioSnapshot no tiene precio_actual; usar precio operativo disponible.
            reference_price = getattr(activo, "ultimo_precio", None) or getattr(activo, "ppc", None)
            if not reference_price:
                return None

            reference_price = Decimal(str(reference_price))
            if reference_price <= 0:
                return None

            return float(amount / reference_price)

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

