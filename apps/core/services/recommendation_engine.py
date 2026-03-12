import logging
from typing import Dict, List, Optional

from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_patrimonial,
    get_concentracion_sector,
    get_dashboard_kpis,
)

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Motor de recomendaciones de inversion basado en analisis del portafolio."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_recommendations(self, current_portfolio: Optional[Dict] = None) -> List[Dict]:
        logger.info("Generating investment recommendations")

        try:
            if not current_portfolio:
                current_portfolio = get_dashboard_kpis()

            recommendations = []

            liquidity_rec = self._analyze_liquidity(current_portfolio)
            if liquidity_rec:
                recommendations.append(liquidity_rec)

            geo_rec = self._analyze_geographic_concentration(current_portfolio)
            if geo_rec:
                recommendations.extend(geo_rec)

            sector_rec = self._analyze_sector_concentration(current_portfolio)
            if sector_rec:
                recommendations.extend(sector_rec)

            risk_rec = self._analyze_risk_profile(current_portfolio)
            if risk_rec:
                recommendations.append(risk_rec)

            performance_rec = self._analyze_performance(current_portfolio)
            if performance_rec:
                recommendations.append(performance_rec)

            logger.info(f"Generated {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return [{"tipo": "error", "mensaje": f"Error generando recomendaciones: {str(e)}"}]

    def _analyze_liquidity(self, portfolio: Dict) -> Optional[Dict]:
        try:
            total_iol = float(portfolio.get("total_iol", 0) or 0)
            liq_oper = float(portfolio.get("liquidez_operativa", 0) or 0)
            fci_cash = float(portfolio.get("fci_cash_management", 0) or 0)
            # Liquidez total operativa para decisiones tacticas de aporte.
            liquidity_percentage = ((liq_oper + fci_cash) / total_iol * 100) if total_iol > 0 else 0.0

            if liquidity_percentage > 30:
                return {
                    "tipo": "liquidez_excesiva",
                    "prioridad": "media",
                    "titulo": "Liquidez Excesiva",
                    "descripcion": f"Tienes {liquidity_percentage:.1f}% en liquidez. Considera invertir parte para mejorar el retorno.",
                    "acciones_sugeridas": [
                        "Invertir en ETFs globales (SPY, EEM)",
                        "Aumentar exposicion a bonos corporativos",
                        "Considerar fondos de inversion",
                    ],
                    "activos_sugeridos": ["SPY", "EEM", "QQQ"],
                    "impacto_esperado": "Aumento de retorno esperado",
                }
            if liquidity_percentage < 5:
                return {
                    "tipo": "liquidez_insuficiente",
                    "prioridad": "alta",
                    "titulo": "Liquidez Insuficiente",
                    "descripcion": f"Tienes solo {liquidity_percentage:.1f}% en liquidez. Considera aumentar para mayor seguridad.",
                    "acciones_sugeridas": [
                        "Mantener al menos 5-10% en liquidez",
                        "Reducir exposicion a activos volatiles",
                    ],
                    "impacto_esperado": "Mayor seguridad financiera",
                }

        except Exception as e:
            logger.error(f"Error analyzing liquidity: {str(e)}")

        return None

    def _analyze_geographic_concentration(self, portfolio: Dict) -> List[Dict]:
        recommendations = []

        try:
            country_dist = get_concentracion_pais()

            argentina_pct = 0.0
            usa_pct = 0.0

            for country, percentage in country_dist.items():
                country_l = country.lower()
                if "argentina" in country_l:
                    argentina_pct = float(percentage)
                elif "estados unidos" in country_l or "usa" in country_l:
                    usa_pct = float(percentage)

            if argentina_pct > 50:
                recommendations.append(
                    {
                        "tipo": "concentracion_argentina_alta",
                        "prioridad": "alta",
                        "titulo": "Alta Concentracion Argentina",
                        "descripcion": f"{argentina_pct:.1f}% del portafolio esta expuesto a Argentina. Considera diversificar.",
                        "acciones_sugeridas": [
                            "Aumentar exposicion internacional",
                            "Invertir en ETFs globales",
                            "Considerar mercados emergentes diversificados",
                        ],
                        "activos_sugeridos": ["SPY", "EEM", "VEA"],
                        "impacto_esperado": "Reduccion de riesgo pais",
                    }
                )

            if usa_pct < 20:
                recommendations.append(
                    {
                        "tipo": "exposicion_usa_baja",
                        "prioridad": "media",
                        "titulo": "Baja Exposicion USA",
                        "descripcion": f"Solo {usa_pct:.1f}% del portafolio esta en USA. Considera aumentar exposicion.",
                        "acciones_sugeridas": [
                            "Invertir en ETFs de S&P 500",
                            "Aumentar exposicion a tech americana",
                            "Considerar bonos del tesoro USA",
                        ],
                        "activos_sugeridos": ["SPY", "QQQ", "IEF"],
                        "impacto_esperado": "Mayor estabilidad y diversificacion",
                    }
                )

        except Exception as e:
            logger.error(f"Error analyzing geographic concentration: {str(e)}")

        return recommendations

    def _analyze_sector_concentration(self, portfolio: Dict) -> List[Dict]:
        recommendations = []

        try:
            sector_dist = get_concentracion_sector()

            def _is_tech(label: str) -> bool:
                lowered = label.lower()
                return "tecnolog" in lowered or "tech" in lowered

            tech_pct = sum(
                float(pct)
                for sector, pct in sector_dist.items()
                if _is_tech(sector)
            )

            financial_pct = sum(
                float(pct)
                for sector, pct in sector_dist.items()
                if "financiero" in sector.lower() or "finanzas" in sector.lower() or "banco" in sector.lower()
            )

            if tech_pct < 10:
                recommendations.append(
                    {
                        "tipo": "tecnologia_subponderada",
                        "prioridad": "media",
                        "titulo": "Tecnologia Subponderada",
                        "descripcion": f"Solo {tech_pct:.1f}% en tecnologia. El sector tech ha mostrado fuerte crecimiento.",
                        "acciones_sugeridas": [
                            "Aumentar exposicion a tecnologia",
                            "Invertir en ETFs sectoriales",
                            "Considerar FAANG stocks",
                        ],
                        "activos_sugeridos": ["QQQ", "VGT", "AAPL"],
                        "impacto_esperado": "Potencial de mayor crecimiento",
                    }
                )

            if financial_pct > 40:
                recommendations.append(
                    {
                        "tipo": "financiero_sobreponderado",
                        "prioridad": "media",
                        "titulo": "Sector Financiero Sobreponderado",
                        "descripcion": f"{financial_pct:.1f}% en sector financiero. Considera diversificar.",
                        "acciones_sugeridas": [
                            "Reducir exposicion a bancos locales",
                            "Diversificar hacia otros sectores",
                            "Invertir en ETFs globales",
                        ],
                        "activos_sugeridos": ["SPY", "EEM"],
                        "impacto_esperado": "Mejor diversificacion sectorial",
                    }
                )

        except Exception as e:
            logger.error(f"Error analyzing sector concentration: {str(e)}")

        return recommendations

    def _analyze_risk_profile(self, portfolio: Dict) -> Optional[Dict]:
        try:
            concentracion = get_concentracion_patrimonial()
            herfindahl = sum(float(pct) ** 2 for pct in concentracion.values()) / 10000

            if herfindahl > 0.3:
                return {
                    "tipo": "riesgo_concentracion_alto",
                    "prioridad": "alta",
                    "titulo": "Alta Concentracion de Riesgo",
                    "descripcion": f"Indice de concentracion alto ({herfindahl:.3f}). Portafolio vulnerable.",
                    "acciones_sugeridas": [
                        "Diversificar en mas activos",
                        "Reducir posiciones grandes",
                        "Invertir en ETFs para mayor diversificacion",
                    ],
                    "impacto_esperado": "Reduccion de riesgo de concentracion",
                }
            if herfindahl < 0.1:
                return {
                    "tipo": "diversificacion_excelente",
                    "prioridad": "baja",
                    "titulo": "Diversificacion Excelente",
                    "descripcion": f"Buena diversificacion (indice: {herfindahl:.3f}). Mantener estrategia.",
                    "acciones_sugeridas": [
                        "Mantener asignacion actual",
                        "Monitorear cambios en correlaciones",
                    ],
                    "impacto_esperado": "Estabilidad del portafolio",
                }

        except Exception as e:
            logger.error(f"Error analyzing risk profile: {str(e)}")

        return None

    def _analyze_performance(self, portfolio: Dict) -> Optional[Dict]:
        try:
            return {
                "tipo": "revision_rendimiento",
                "prioridad": "baja",
                "titulo": "Revision de Rendimiento",
                "descripcion": "Considera revisar el rendimiento relativo vs benchmarks.",
                "acciones_sugeridas": [
                    "Comparar con indices de referencia",
                    "Evaluar costo de transacciones",
                    "Considerar rebalanceo si desviaciones son grandes",
                ],
                "impacto_esperado": "Optimizacion de retorno ajustado por riesgo",
            }

        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")

        return None
