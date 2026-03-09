import logging
from typing import Dict, List, Optional
from decimal import Decimal
import numpy as np

from apps.dashboard.selectors import get_dashboard_kpis
from apps.portafolio_iol.models import ActivoPortafolioSnapshot as Activo

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Optimizador de portafolio con múltiples estrategias.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def optimize_risk_parity(self, activos: List[str], target_return: Optional[float] = None) -> Dict:
        """
        Optimización Risk Parity - equilibra el riesgo entre activos.

        Args:
            activos: Lista de símbolos de activos
            target_return: Retorno objetivo (opcional)

        Returns:
            Dict con asignaciones óptimas
        """
        logger.info(f"Optimizing portfolio with Risk Parity for assets: {activos}")

        try:
            # Obtener datos de activos
            assets_data = []
            for symbol in activos:
                try:
                    activo = Activo.objects.filter(simbolo=symbol).first()
                    if activo:
                        assets_data.append({
                            'symbol': symbol,
                            'volatility': self._estimate_volatility(activo),
                            'expected_return': self._estimate_return(activo)
                        })
                except Exception:
                    continue

            if not assets_data:
                return {'error': 'No se encontraron activos válidos'}

            # Risk Parity simplificado - pesos inversamente proporcionales a volatilidad
            volatilities = [asset['volatility'] for asset in assets_data]
            total_inverse_vol = sum(1/v for v in volatilities if v > 0)

            weights = {}
            for asset in assets_data:
                vol = asset['volatility']
                if vol > 0:
                    weight = (1/vol) / total_inverse_vol
                    weights[asset['symbol']] = weight * 100  # Convertir a porcentaje
                else:
                    weights[asset['symbol']] = 0

            resultado = {
                'metodo': 'risk_parity',
                'activos': activos,
                'pesos_optimos': weights,
                'riesgo_portafolio': self._calculate_portfolio_risk(weights, assets_data),
                'retorno_esperado': self._calculate_portfolio_return(weights, assets_data),
                'sharpe_ratio': self._calculate_sharpe_ratio(weights, assets_data)
            }

            logger.info("Risk Parity optimization completed")
            return resultado

        except Exception as e:
            logger.error(f"Error in Risk Parity optimization: {str(e)}")
            return {'error': str(e)}

    def optimize_markowitz(self, activos: List[str], target_return: float) -> Dict:
        """
        Optimización Markowitz simplificada - minimizar volatilidad para retorno objetivo.

        Args:
            activos: Lista de símbolos de activos
            target_return: Retorno objetivo

        Returns:
            Dict con asignaciones óptimas
        """
        logger.info(f"Optimizing portfolio with Markowitz for target return {target_return}")

        try:
            # Obtener datos de activos
            assets_data = []
            for symbol in activos:
                try:
                    activo = Activo.objects.filter(simbolo=symbol).first()
                    if activo:
                        assets_data.append({
                            'symbol': symbol,
                            'volatility': self._estimate_volatility(activo),
                            'expected_return': self._estimate_return(activo)
                        })
                except Exception:
                    continue

            if not assets_data:
                return {'error': 'No se encontraron activos válidos'}

            # Markowitz simplificado - asignación equitativa con ajuste por retorno
            expected_returns = [asset['expected_return'] for asset in assets_data]
            avg_return = sum(expected_returns) / len(expected_returns)

            weights = {}
            total_weight = 0

            for asset in assets_data:
                # Peso base equitativo
                base_weight = 1.0 / len(assets_data)

                # Ajuste por retorno esperado
                return_adjustment = asset['expected_return'] / avg_return if avg_return > 0 else 1

                weight = base_weight * return_adjustment
                weights[asset['symbol']] = weight
                total_weight += weight

            # Normalizar pesos
            for symbol in weights:
                weights[symbol] = (weights[symbol] / total_weight) * 100

            resultado = {
                'metodo': 'markowitz_simplified',
                'activos': activos,
                'retorno_objetivo': target_return,
                'pesos_optimos': weights,
                'riesgo_portafolio': self._calculate_portfolio_risk(weights, assets_data),
                'retorno_esperado': self._calculate_portfolio_return(weights, assets_data),
                'sharpe_ratio': self._calculate_sharpe_ratio(weights, assets_data)
            }

            logger.info("Markowitz optimization completed")
            return resultado

        except Exception as e:
            logger.error(f"Error in Markowitz optimization: {str(e)}")
            return {'error': str(e)}

    def optimize_target_allocation(self, target_allocations: Dict[str, float]) -> Dict:
        """
        Optimización por asignación objetivo definida por usuario.

        Args:
            target_allocations: Dict con pesos objetivo por categoría

        Returns:
            Dict con asignaciones específicas
        """
        logger.info(f"Optimizing portfolio with target allocations: {target_allocations}")

        try:
            # Validar que los pesos sumen 100%
            total_weight = sum(target_allocations.values())
            if abs(total_weight - 100) > 0.1:
                return {'error': f'Los pesos objetivo deben sumar 100%. Suma actual: {total_weight}'}

            resultado = {
                'metodo': 'target_allocation',
                'asignacion_objetivo': target_allocations,
                'validacion': 'pesos_suman_100',
                'recomendaciones': self._generate_target_recommendations(target_allocations)
            }

            logger.info("Target allocation optimization completed")
            return resultado

        except Exception as e:
            logger.error(f"Error in target allocation optimization: {str(e)}")
            return {'error': str(e)}

    def _estimate_volatility(self, activo: Activo) -> float:
        """Estima volatilidad del activo basado en su tipo y características."""
        # Lógica simplificada basada en el tipo de activo
        tipo_activo = getattr(activo, 'tipo', '').lower()
        if 'liquidez' in tipo_activo or 'cash' in tipo_activo:
            return 0.01  # 1% volatilidad para liquidez
        elif activo.pais_titulo and 'argentina' in activo.pais_titulo.lower():
            return 0.25  # 25% volatilidad para activos argentinos
        elif 'SPY' in activo.simbolo or 'QQQ' in activo.simbolo:
            return 0.15  # 15% para ETFs USA
        else:
            return 0.20  # 20% volatilidad por defecto

    def _estimate_return(self, activo: Activo) -> float:
        """Estima retorno esperado del activo."""
        # Lógica simplificada
        if activo.sector and activo.sector.nombre == 'Liquidez':
            return 0.035  # 3.5% para liquidez
        elif activo.pais and activo.pais.nombre == 'Argentina':
            return 0.15  # 15% para activos argentinos (alto riesgo/alto retorno)
        elif 'SPY' in activo.simbolo:
            return 0.08  # 8% para S&P 500
        elif 'EEM' in activo.simbolo:
            return 0.07  # 7% para mercados emergentes
        else:
            return 0.06  # 6% retorno por defecto

    def _calculate_portfolio_risk(self, weights: Dict[str, float], assets_data: List[Dict]) -> float:
        """Calcula riesgo del portafolio usando volatilidades."""
        total_risk = 0
        total_weight = 0

        for asset in assets_data:
            symbol = asset['symbol']
            if symbol in weights:
                weight = weights[symbol] / 100  # Convertir de porcentaje
                risk_contribution = weight * asset['volatility']
                total_risk += risk_contribution
                total_weight += weight

        return total_risk if total_weight > 0 else 0

    def _calculate_portfolio_return(self, weights: Dict[str, float], assets_data: List[Dict]) -> float:
        """Calcula retorno esperado del portafolio."""
        total_return = 0
        total_weight = 0

        for asset in assets_data:
            symbol = asset['symbol']
            if symbol in weights:
                weight = weights[symbol] / 100  # Convertir de porcentaje
                return_contribution = weight * asset['expected_return']
                total_return += return_contribution
                total_weight += weight

        return total_return if total_weight > 0 else 0

    def _calculate_sharpe_ratio(self, weights: Dict[str, float], assets_data: List[Dict]) -> float:
        """Calcula Sharpe Ratio del portafolio."""
        portfolio_return = self._calculate_portfolio_return(weights, assets_data)
        portfolio_risk = self._calculate_portfolio_risk(weights, assets_data)
        risk_free_rate = 0.035  # 3.5% tasa libre de riesgo

        if portfolio_risk > 0:
            return (portfolio_return - risk_free_rate) / portfolio_risk
        return 0

    def _generate_target_recommendations(self, target_allocations: Dict[str, float]) -> List[str]:
        """Genera recomendaciones basadas en asignación objetivo."""
        recommendations = []

        if 'liquidez' in target_allocations and target_allocations['liquidez'] > 30:
            recommendations.append("Alta asignación a liquidez - considerar reducir para mejorar retorno")
        elif 'liquidez' in target_allocations and target_allocations['liquidez'] < 5:
            recommendations.append("Baja liquidez - considerar aumentar para mayor seguridad")

        if 'argentina' in target_allocations and target_allocations['argentina'] > 50:
            recommendations.append("Alta exposición Argentina - considerar diversificar internacionalmente")

        if 'usa' in target_allocations and target_allocations['usa'] < 20:
            recommendations.append("Baja exposición USA - considerar aumentar para mayor estabilidad")

        return recommendations