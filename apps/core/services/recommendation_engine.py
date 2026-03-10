import logging
from typing import Dict, List, Optional
from decimal import Decimal

from apps.dashboard.selectors import (
    get_dashboard_kpis,
    get_distribucion_sector,
    get_distribucion_pais,
    get_concentracion_patrimonial
)
from apps.portafolio_iol.models import ActivoPortafolioSnapshot as Activo

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Motor de recomendaciones de inversión basado en análisis del portafolio.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_recommendations(self, current_portfolio: Optional[Dict] = None) -> List[Dict]:
        """
        Genera recomendaciones automáticas basadas en el estado del portafolio.

        Args:
            current_portfolio: Estado actual del portafolio (opcional)

        Returns:
            Lista de recomendaciones
        """
        logger.info("Generating investment recommendations")

        try:
            if not current_portfolio:
                current_portfolio = get_dashboard_kpis()

            recommendations = []

            # Análisis de liquidez
            liquidity_rec = self._analyze_liquidity(current_portfolio)
            if liquidity_rec:
                recommendations.append(liquidity_rec)

            # Análisis de concentración geográfica
            geo_rec = self._analyze_geographic_concentration(current_portfolio)
            if geo_rec:
                recommendations.extend(geo_rec)

            # Análisis de concentración sectorial
            sector_rec = self._analyze_sector_concentration(current_portfolio)
            if sector_rec:
                recommendations.extend(sector_rec)

            # Análisis de riesgo
            risk_rec = self._analyze_risk_profile(current_portfolio)
            if risk_rec:
                recommendations.append(risk_rec)

            # Análisis de rendimiento
            performance_rec = self._analyze_performance(current_portfolio)
            if performance_rec:
                recommendations.append(performance_rec)

            logger.info(f"Generated {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return [{'tipo': 'error', 'mensaje': f'Error generando recomendaciones: {str(e)}'}]

    def _analyze_liquidity(self, portfolio: Dict) -> Optional[Dict]:
        """Analiza nivel de liquidez y genera recomendaciones."""
        try:
            # Obtener distribución por sector
            sector_dist = get_distribucion_sector()

            liquidity_percentage = 0
            for sector, percentage in sector_dist.items():
                if 'liquidez' in sector.lower() or 'cash' in sector.lower():
                    liquidity_percentage = percentage
                    break

            if liquidity_percentage > 30:
                return {
                    'tipo': 'liquidez_excesiva',
                    'prioridad': 'media',
                    'titulo': 'Liquidez Excesiva',
                    'descripcion': f'Tienes {liquidity_percentage:.1f}% en liquidez. Considera invertir parte para mejorar el retorno.',
                    'acciones_sugeridas': [
                        'Invertir en ETFs globales (SPY, EEM)',
                        'Aumentar exposición a bonos corporativos',
                        'Considerar fondos de inversión'
                    ],
                    'activos_sugeridos': ['SPY', 'EEM', 'QQQ'],
                    'impacto_esperado': 'Aumento de retorno esperado'
                }
            elif liquidity_percentage < 5:
                return {
                    'tipo': 'liquidez_insuficiente',
                    'prioridad': 'alta',
                    'titulo': 'Liquidez Insuficiente',
                    'descripcion': f'Tienes solo {liquidity_percentage:.1f}% en liquidez. Considera aumentar para mayor seguridad.',
                    'acciones_sugeridas': [
                        'Mantener al menos 5-10% en liquidez',
                        'Reducir exposición a activos volátiles'
                    ],
                    'impacto_esperado': 'Mayor seguridad financiera'
                }

        except Exception as e:
            logger.error(f"Error analyzing liquidity: {str(e)}")

        return None

    def _analyze_geographic_concentration(self, portfolio: Dict) -> List[Dict]:
        """Analiza concentración geográfica."""
        recommendations = []

        try:
            country_dist = get_distribucion_pais()

            argentina_pct = 0
            usa_pct = 0

            for country, percentage in country_dist.items():
                if 'argentina' in country.lower():
                    argentina_pct = percentage
                elif 'estados unidos' in country.lower() or 'usa' in country.lower():
                    usa_pct = percentage

            # Alta concentración en Argentina
            if argentina_pct > 50:
                recommendations.append({
                    'tipo': 'concentracion_argentina_alta',
                    'prioridad': 'alta',
                    'titulo': 'Alta Concentración Argentina',
                    'descripcion': f'{argentina_pct:.1f}% del portafolio está expuesto a Argentina. Considera diversificar.',
                    'acciones_sugeridas': [
                        'Aumentar exposición internacional',
                        'Invertir en ETFs globales',
                        'Considerar mercados emergentes diversificados'
                    ],
                    'activos_sugeridos': ['SPY', 'EEM', 'VEA'],
                    'impacto_esperado': 'Reducción de riesgo país'
                })

            # Baja exposición USA
            if usa_pct < 20:
                recommendations.append({
                    'tipo': 'exposicion_usa_baja',
                    'prioridad': 'media',
                    'titulo': 'Baja Exposición USA',
                    'descripcion': f'Solo {usa_pct:.1f}% del portafolio está en USA. Considera aumentar exposición.',
                    'acciones_sugeridas': [
                        'Invertir en ETFs de S&P 500',
                        'Aumentar exposición a tech americana',
                        'Considerar bonos del tesoro USA'
                    ],
                    'activos_sugeridos': ['SPY', 'QQQ', 'IEF'],
                    'impacto_esperado': 'Mayor estabilidad y diversificación'
                })

        except Exception as e:
            logger.error(f"Error analyzing geographic concentration: {str(e)}")

        return recommendations

    def _analyze_sector_concentration(self, portfolio: Dict) -> List[Dict]:
        """Analiza concentración sectorial."""
        recommendations = []

        try:
            sector_dist = get_distribucion_sector()

            # Identificar sectores sobre/sub-representados
            tech_pct = sum(pct for sector, pct in sector_dist.items()
                          if 'tecnologia' in sector.lower() or 'tech' in sector.lower())

            financial_pct = sum(pct for sector, pct in sector_dist.items()
                               if 'financiero' in sector.lower() or 'banco' in sector.lower())

            # Tecnología subponderada
            if tech_pct < 10:
                recommendations.append({
                    'tipo': 'tecnologia_subponderada',
                    'prioridad': 'media',
                    'titulo': 'Tecnología Subponderada',
                    'descripcion': f'Solo {tech_pct:.1f}% en tecnología. El sector tech ha mostrado fuerte crecimiento.',
                    'acciones_sugeridas': [
                        'Aumentar exposición a tecnología',
                        'Invertir en ETFs sectoriales',
                        'Considerar FAANG stocks'
                    ],
                    'activos_sugeridos': ['QQQ', 'VGT', 'AAPL'],
                    'impacto_esperado': 'Potencial de mayor crecimiento'
                })

            # Financiero sobreponderado (común en Argentina)
            if financial_pct > 40:
                recommendations.append({
                    'tipo': 'financiero_sobreponderado',
                    'prioridad': 'media',
                    'titulo': 'Sector Financiero Sobreponderado',
                    'descripcion': f'{financial_pct:.1f}% en sector financiero. Considera diversificar.',
                    'acciones_sugeridas': [
                        'Reducir exposición a bancos locales',
                        'Diversificar hacia otros sectores',
                        'Invertir en ETFs globales'
                    ],
                    'activos_sugeridos': ['SPY', 'EEM'],
                    'impacto_esperado': 'Mejor diversificación sectorial'
                })

        except Exception as e:
            logger.error(f"Error analyzing sector concentration: {str(e)}")

        return recommendations

    def _analyze_risk_profile(self, portfolio: Dict) -> Optional[Dict]:
        """Analiza perfil de riesgo del portafolio."""
        try:
            # Calcular métricas de riesgo
            concentracion = get_concentracion_patrimonial()

            # Índice de Herfindahl (suma de cuadrados de porcentajes)
            herfindahl = sum(pct ** 2 for pct in concentracion.values()) / 10000

            if herfindahl > 0.3:  # Alta concentración
                return {
                    'tipo': 'riesgo_concentracion_alto',
                    'prioridad': 'alta',
                    'titulo': 'Alta Concentración de Riesgo',
                    'descripcion': f'Índice de concentración alto ({herfindahl:.3f}). Portafolio vulnerable.',
                    'acciones_sugeridas': [
                        'Diversificar en más activos',
                        'Reducir posiciones grandes',
                        'Invertir en ETFs para mayor diversificación'
                    ],
                    'impacto_esperado': 'Reducción de riesgo de concentración'
                }
            elif herfindahl < 0.1:  # Muy diversificado
                return {
                    'tipo': 'diversificacion_excelente',
                    'prioridad': 'baja',
                    'titulo': 'Diversificación Excelente',
                    'descripcion': f'Buena diversificación (índice: {herfindahl:.3f}). Mantener estrategia.',
                    'acciones_sugeridas': [
                        'Mantener asignación actual',
                        'Monitorear cambios en correlaciones'
                    ],
                    'impacto_esperado': 'Estabilidad del portafolio'
                }

        except Exception as e:
            logger.error(f"Error analyzing risk profile: {str(e)}")

        return None

    def _analyze_performance(self, portfolio: Dict) -> Optional[Dict]:
        """Analiza rendimiento del portafolio."""
        try:
            # Obtener KPIs de rendimiento
            kpis = portfolio

            # Lógica simplificada para análisis de rendimiento
            # En implementación real, comparar con benchmarks

            return {
                'tipo': 'revision_rendimiento',
                'prioridad': 'baja',
                'titulo': 'Revisión de Rendimiento',
                'descripcion': 'Considera revisar el rendimiento relativo vs benchmarks.',
                'acciones_sugeridas': [
                    'Comparar con índices de referencia',
                    'Evaluar costo de transacciones',
                    'Considerar rebalanceo si desviaciones son grandes'
                ],
                'impacto_esperado': 'Optimización de retorno ajustado por riesgo'
            }

        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")

        return None