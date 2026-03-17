import logging
from typing import Dict, List, Optional

from apps.core.services.analytics_v2 import (
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    LocalMacroSignalsService,
    RiskContributionService,
    ScenarioAnalysisService,
    StressFragilityService,
)
from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_patrimonial,
    get_concentracion_sector,
    get_dashboard_kpis,
)

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Motor de recomendaciones de inversion basado en analisis del portafolio."""

    PRIORITY_RANK = {"alta": 0, "media": 1, "baja": 2}

    DIVERSIFICATION_CANDIDATES = (
        ("Healthcare", 8.0),
        ("Industrials", 8.0),
        ("Small Caps", 6.0),
        ("Utilities", 6.0),
    )

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

            analytics_v2_recs = self._analyze_analytics_v2()
            if analytics_v2_recs:
                recommendations.extend(analytics_v2_recs)

            prioritized = self._prioritize_recommendations(recommendations)
            logger.info(
                "Generated %s recommendations (%s after prioritization)",
                len(recommendations),
                len(prioritized),
            )
            return prioritized

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
                suggested_categories = self._build_diversification_categories()
                return {
                    "tipo": "liquidez_excesiva",
                    "prioridad": "media",
                    "titulo": "Liquidez Excesiva",
                    "descripcion": (
                        f"Tienes {liquidity_percentage:.1f}% en liquidez total. "
                        "Liquidez total = liquidez operativa + cash management."
                    ),
                    "acciones_sugeridas": [
                        "Dirigir nuevos flujos a sectores subrepresentados",
                        "Usar diversificacion por sectores antes que sumar mas peso a posiciones dominantes",
                        "Priorizar exposiciones complementarias al sesgo actual de la cartera",
                    ],
                    "activos_sugeridos": suggested_categories,
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

            diversification_gaps = self._build_diversification_gaps(sector_dist)
            if diversification_gaps:
                recommendations.append(
                    {
                        "tipo": "diversificacion_sectorial",
                        "prioridad": "media",
                        "titulo": "Diversificacion Sectorial Pendiente",
                        "descripcion": "La cartera sigue concentrada en pocos sectores. Conviene reforzar sectores subrepresentados antes que ampliar posiciones dominantes.",
                        "acciones_sugeridas": [
                            "Asignar nuevos flujos a sectores con menor peso relativo",
                            "Evitar sumar capital a los sectores ya dominantes salvo conviccion tactica explicita",
                        ],
                        "activos_sugeridos": [gap["label"] for gap in diversification_gaps],
                        "impacto_esperado": "Mejor diversificacion real del portafolio",
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

            if herfindahl > 0.5:
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
            if herfindahl > 0.3:
                return {
                    "tipo": "riesgo_concentracion_media",
                    "prioridad": "media",
                    "titulo": "Concentracion de Riesgo Media",
                    "descripcion": f"Indice de concentracion en zona media ({herfindahl:.3f}). Conviene diversificar gradualmente sin forzar rebalanceos abruptos.",
                    "acciones_sugeridas": [
                        "Canalizar nuevos aportes a sectores o geografias subrepresentadas",
                        "Reducir dependencia de uno o dos bloques dominantes",
                    ],
                    "impacto_esperado": "Mejor equilibrio de riesgo sin sobreoperar",
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

    def _build_diversification_gaps(self, sector_dist: Dict) -> List[Dict]:
        normalized = {str(sector).lower(): float(pct) for sector, pct in sector_dist.items()}
        gaps = []
        for label, target in self.DIVERSIFICATION_CANDIDATES:
            current = normalized.get(label.lower(), 0.0)
            if current < target:
                gaps.append({"label": label, "current": current, "target": target})
        return gaps

    def _build_diversification_categories(self) -> List[str]:
        sector_dist = get_concentracion_sector()
        gaps = self._build_diversification_gaps(sector_dist)
        if gaps:
            return [gap["label"] for gap in gaps]
        return [label for label, _ in self.DIVERSIFICATION_CANDIDATES]

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

    def _analyze_analytics_v2(self) -> List[Dict]:
        try:
            signals = (
                self._build_risk_contribution_signals()
                + ScenarioAnalysisService().build_recommendation_signals()
                + FactorExposureService().build_recommendation_signals()
                + StressFragilityService().build_recommendation_signals()
                + ExpectedReturnService().build_recommendation_signals()
                + LocalMacroSignalsService().build_recommendation_signals()
            )
            if not signals:
                return []

            normalized = [self._map_signal_to_recommendation(signal) for signal in signals]
            return sorted(
                normalized,
                key=lambda rec: {"alta": 0, "media": 1, "baja": 2}.get(rec.get("prioridad", "media"), 3),
            )
        except Exception as e:
            logger.error(f"Error analyzing analytics v2 signals: {str(e)}")
            return []

    def _build_risk_contribution_signals(self) -> List[Dict]:
        try:
            covariance_service = CovarianceAwareRiskContributionService()
            covariance_result = covariance_service.calculate(top_n=5)
            if covariance_result.get("model_variant") == "covariance_aware":
                return [
                    {
                        **signal,
                        "risk_model_variant": "covariance_aware",
                    }
                    for signal in covariance_service.build_recommendation_signals(top_n=5)
                ]
        except Exception as e:
            logger.error(f"Error evaluating covariance-aware risk contribution signals: {str(e)}")

        return [
            {
                **signal,
                "risk_model_variant": "mvp_proxy",
            }
            for signal in RiskContributionService().build_recommendation_signals(top_n=5)
        ]

    def _prioritize_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        selected_by_topic = {}

        for index, recommendation in enumerate(recommendations):
            topic_key = self._recommendation_topic_key(recommendation)
            sort_key = self._recommendation_sort_key(recommendation, index)
            current = selected_by_topic.get(topic_key)
            if current is None or sort_key < current[0]:
                selected_by_topic[topic_key] = (sort_key, recommendation)

        return [
            entry[1]
            for entry in sorted(selected_by_topic.values(), key=lambda item: item[0])
        ]

    @staticmethod
    def _recommendation_topic_key(recommendation: Dict) -> str:
        recommendation_type = str(recommendation.get("tipo", "")).lower()
        topic_aliases = {
            "liquidez_excesiva": "liquidity_excess",
            "analytics_v2_expected_return_liquidity_drag": "liquidity_excess",
            "analytics_v2_local_liquidity_real_carry_negative": "liquidity_excess",
            "concentracion_argentina_alta": "argentina_concentration",
            "analytics_v2_risk_concentration_argentina": "argentina_concentration",
            "analytics_v2_local_sovereign_risk_excess": "argentina_concentration",
            "riesgo_concentracion_alto": "portfolio_concentration",
            "riesgo_concentracion_media": "portfolio_concentration",
            "analytics_v2_risk_concentration_top_assets": "portfolio_concentration",
        }
        return topic_aliases.get(recommendation_type, recommendation_type)

    def _recommendation_sort_key(self, recommendation: Dict, index: int) -> tuple:
        priority = self.PRIORITY_RANK.get(
            str(recommendation.get("prioridad", "media")).lower(),
            3,
        )
        origin = 0 if recommendation.get("origen") == "analytics_v2" else 1
        specificity = self._recommendation_specificity_rank(recommendation)
        has_assets = 0 if recommendation.get("activos_sugeridos") else 1
        return (priority, origin, specificity, has_assets, index)

    @staticmethod
    def _recommendation_specificity_rank(recommendation: Dict) -> int:
        recommendation_type = str(recommendation.get("tipo", "")).lower()
        specificity_rank = {
            "analytics_v2_local_liquidity_real_carry_negative": 0,
            "analytics_v2_local_sovereign_risk_excess": 0,
            "analytics_v2_expected_return_liquidity_drag": 1,
            "analytics_v2_risk_concentration_argentina": 1,
            "liquidez_excesiva": 2,
            "concentracion_argentina_alta": 2,
        }
        return specificity_rank.get(recommendation_type, 1)

    def _map_signal_to_recommendation(self, signal: Dict) -> Dict:
        severity = str(signal.get("severity", "medium")).lower()
        prioridad = {"high": "alta", "medium": "media", "low": "baja"}.get(severity, "media")
        evidence = signal.get("evidence") or {}

        recommendation = {
            "tipo": f"analytics_v2_{signal.get('signal_key', 'signal')}",
            "prioridad": prioridad,
            "titulo": signal.get("title", "Señal Analytics v2"),
            "descripcion": signal.get("description", ""),
            "acciones_sugeridas": self._build_signal_actions(signal),
            "impacto_esperado": "Mejor trazabilidad entre riesgo, escenarios y planeación",
            "origen": "analytics_v2",
        }

        suggested_assets = self._extract_signal_assets(evidence)
        if suggested_assets:
            recommendation["activos_sugeridos"] = suggested_assets
        if signal.get("risk_model_variant"):
            recommendation["modelo_riesgo"] = signal["risk_model_variant"]
        return recommendation

    @staticmethod
    def _extract_signal_assets(evidence: Dict) -> List[str]:
        top_symbols = evidence.get("top_symbols")
        if isinstance(top_symbols, list) and top_symbols:
            return [str(symbol) for symbol in top_symbols[:3]]
        factor = evidence.get("factor")
        if factor:
            return [str(factor)]
        return []

    @staticmethod
    def _build_signal_actions(signal: Dict) -> List[str]:
        key = str(signal.get("signal_key", ""))
        if "liquidity_drag" in key:
            return [
                "Reducir gradualmente liquidez excedente si no cumple una función táctica explícita",
                "Dirigir nuevos flujos a buckets con mejor retorno esperado estructural",
            ]
        if "real_carry" in key:
            return [
                "Revisar si la liquidez en ARS sigue cumpliendo una función táctica clara",
                "Comparar BADLAR contra inflación antes de mantener saldos altos en pesos",
            ]
        if "fx_gap" in key:
            return [
                "Revisar cuánta exposición argentina depende de una brecha cambiaria tensionada",
                "Evitar sumar riesgo local en ARS o soberano sin una convicción táctica explícita",
            ]
        if "country_risk" in key:
            return [
                "Revisar si el peso de soberanos locales sigue siendo consistente con el nivel actual de riesgo país",
                "Reducir dependencia de crédito soberano argentino si el bloque local ya es material",
            ]
        if "single_name" in key and "sovereign" in key:
            return [
                "Reducir dependencia de un solo bono soberano dentro del bloque argentino",
                "Distribuir el riesgo local entre instrumentos con drivers distintos si la convicción sigue siendo local",
            ]
        if "inflation_hedge" in key:
            return [
                "Evaluar si la cobertura CER es suficiente para la exposición argentina actual",
                "Evitar depender solo de carry nominal cuando la inflación local sigue alta",
            ]
        if "sovereign_risk" in key:
            return [
                "Reducir dependencia de soberanos locales si ya dominan el bloque argentino",
                "Diversificar riesgo local entre instrumentos menos concentrados o exposición internacional",
            ]
        if "argentina" in key or "local_crisis" in key:
            return [
                "Bajar vulnerabilidad local con diversificación internacional adicional",
                "Evitar sumar riesgo argentino sin convicción táctica explícita",
            ]
        if "tech" in key or "growth" in key:
            return [
                "Balancear exposición growth/tech con factores defensivos o dividend",
                "Reforzar diversificación sectorial antes de ampliar posiciones dominantes",
            ]
        if "defensive_gap" in key or "dividend_gap" in key:
            return [
                "Canalizar nuevos aportes a segmentos defensivos o generadores de renta",
                "Usar diversificación por estilo además de diversificación geográfica",
            ]
        if "fragility" in key or "stress" in key:
            return [
                "Reducir concentración en activos o sectores que dominan la pérdida bajo stress",
                "Usar liquidez y diversificación para bajar fragilidad extrema",
            ]
        if "real_weak" in key or "nominal_weak" in key:
            return [
                "Revisar si la composición actual justifica el retorno esperado estructural",
                "Comparar el peso de liquidez y renta fija contra los objetivos de crecimiento real",
            ]
        return [
            "Revisar la señal analítica antes de sumar exposición en los bloques dominantes",
            "Usar nuevos aportes para corregir el desbalance detectado",
        ]

