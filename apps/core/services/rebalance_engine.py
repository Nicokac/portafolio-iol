import logging
from typing import Dict, List, Tuple

from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_sector,
    get_dashboard_kpis,
    get_senales_rebalanceo,
)

logger = logging.getLogger(__name__)


class RebalanceRule:
    """Clase base para reglas de rebalanceo."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def analyze(self, data: Dict) -> Dict:
        """Analiza y retorna sugerencias de rebalanceo."""
        raise NotImplementedError


class ConcentrationRebalance(RebalanceRule):
    """Rebalanceo por concentración excesiva."""

    def __init__(self, max_concentration: float = 15.0):
        super().__init__(
            name="concentracion_maxima",
            description=f"Reducir posiciones > {max_concentration}% del portafolio"
        )
        self.max_concentration = max_concentration

    def analyze(self, data: Dict) -> Dict:
        # Esta requeriría datos detallados de posiciones
        # Por ahora, usar señales de rebalanceo existentes
        senales = data.get('senales_rebalanceo', [])
        suggestions = []

        for senal in senales:
            if senal.get('tipo') == 'concentracion':
                suggestions.append({
                    'activo': senal.get('activo'),
                    'accion': 'reducir',
                    'porcentaje_actual': senal.get('porcentaje'),
                    'porcentaje_objetivo': self.max_concentration,
                    'razon': 'Concentración excesiva'
                })

        return {
            'regla': self.name,
            'sugerencias': suggestions
        }


class LiquidityRebalance(RebalanceRule):
    """Rebalanceo por optimización de liquidez."""

    def __init__(self, min_liquidity: float = 10.0, max_liquidity: float = 30.0):
        super().__init__(
            name="liquidez_optima",
            description=f"Mantener liquidez entre {min_liquidity}% y {max_liquidity}%"
        )
        self.min_liquidity = min_liquidity
        self.max_liquidity = max_liquidity

    def analyze(self, data: Dict) -> Dict:
        pct_liquidez = data.get('pct_liquidez_operativa', 0)

        if pct_liquidez < self.min_liquidity:
            return {
                'regla': self.name,
                'sugerencias': [{
                    'accion': 'incrementar_liquidez',
                    'porcentaje_actual': pct_liquidez,
                    'porcentaje_objetivo': self.min_liquidity,
                    'razon': 'Liquidez insuficiente para operaciones'
                }]
            }
        elif pct_liquidez > self.max_liquidity:
            return {
                'regla': self.name,
                'sugerencias': [{
                    'accion': 'invertir_liquidez',
                    'porcentaje_actual': pct_liquidez,
                    'porcentaje_objetivo': self.max_liquidity,
                    'razon': 'Liquidez excesiva, oportunidad de inversión'
                }]
            }

        return {'regla': self.name, 'sugerencias': []}


class CountryDiversificationRebalance(RebalanceRule):
    """Rebalanceo por diversificación geográfica."""

    def __init__(self, max_country_exposure: float = 50.0):
        super().__init__(
            name="diversificacion_pais",
            description=f"Límite exposición país: {max_country_exposure}%"
        )
        self.max_country_exposure = max_country_exposure

    def analyze(self, data: Dict) -> Dict:
        concentracion_pais = data.get('concentracion_pais', {})
        suggestions = []

        for pais, porcentaje in concentracion_pais.items():
            if porcentaje > self.max_country_exposure:
                suggestions.append({
                    'pais': pais,
                    'accion': 'reducir_exposicion',
                    'porcentaje_actual': porcentaje,
                    'porcentaje_objetivo': self.max_country_exposure,
                    'razon': 'Exposición geográfica excesiva'
                })

        return {
            'regla': self.name,
            'sugerencias': suggestions
        }


class SectorDiversificationRebalance(RebalanceRule):
    """Rebalanceo por diversificación sectorial."""

    def __init__(self, max_sector_exposure: float = 25.0):
        super().__init__(
            name="diversificacion_sector",
            description=f"Límite exposición sector: {max_sector_exposure}%"
        )
        self.max_sector_exposure = max_sector_exposure

    def analyze(self, data: Dict) -> Dict:
        concentracion_sector = data.get('concentracion_sector', {})
        suggestions = []

        for sector, porcentaje in concentracion_sector.items():
            if porcentaje > self.max_sector_exposure:
                suggestions.append({
                    'sector': sector,
                    'accion': 'reducir_exposicion',
                    'porcentaje_actual': porcentaje,
                    'porcentaje_objetivo': self.max_sector_exposure,
                    'razon': 'Exposición sectorial excesiva'
                })

        return {
            'regla': self.name,
            'sugerencias': suggestions
        }


class RebalanceEngine:
    """Motor de rebalanceo inteligente."""

    def __init__(self):
        self.rules = [
            ConcentrationRebalance(),
            LiquidityRebalance(),
            CountryDiversificationRebalance(),
            SectorDiversificationRebalance(),
        ]

    def generate_rebalance_suggestions(self) -> List[Dict]:
        """
        Genera sugerencias de rebalanceo basadas en reglas estratégicas.

        Returns:
            List[Dict]: Lista de sugerencias de rebalanceo
        """
        logger.info("Generating rebalance suggestions")

        # Obtener datos actuales
        kpis = get_dashboard_kpis()
        concentracion_pais = get_concentracion_pais()
        concentracion_sector = get_concentracion_sector()
        senales_rebalanceo = get_senales_rebalanceo()

        # Datos para reglas
        data = {
            'kpis': kpis,
            'concentracion_pais': concentracion_pais,
            'concentracion_sector': concentracion_sector,
            'senales_rebalanceo': senales_rebalanceo,
            'pct_liquidez_operativa': kpis.get('pct_fci_cash_management', 0) + (kpis.get('liquidez_operativa', 0) / kpis.get('total_iol', 1) * 100),
        }

        all_suggestions = []
        for rule in self.rules:
            analysis = rule.analyze(data)
            if analysis.get('sugerencias'):
                all_suggestions.extend(analysis['sugerencias'])
                logger.info(f"Rebalance suggestions from {rule.name}: {len(analysis['sugerencias'])}")

        logger.info(f"Generated {len(all_suggestions)} rebalance suggestions")
        return all_suggestions

    def get_critical_actions(self) -> List[Dict]:
        """Obtiene acciones críticas de rebalanceo."""
        suggestions = self.generate_rebalance_suggestions()
        return [s for s in suggestions if s.get('razon') in [
            'Concentración excesiva',
            'Exposición geográfica excesiva',
            'Exposición sectorial excesiva'
        ]]

    def get_opportunity_actions(self) -> List[Dict]:
        """Obtiene acciones de oportunidad de rebalanceo."""
        suggestions = self.generate_rebalance_suggestions()
        return [s for s in suggestions if s.get('razon') in [
            'Liquidez excesiva, oportunidad de inversión'
        ]]