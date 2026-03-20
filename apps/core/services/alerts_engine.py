import logging
from typing import Dict, List

from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_sector,
    get_dashboard_kpis,
    get_liquidity_contract_summary,
    get_senales_rebalanceo,
)

logger = logging.getLogger(__name__)


class AlertRule:
    """Clase base para reglas de alerta."""

    def __init__(self, name: str, severity: str, description: str):
        self.name = name
        self.severity = severity  # 'info', 'warning', 'critical'
        self.description = description

    def check(self, data: Dict) -> Dict:
        """Verifica la regla y retorna alerta si se cumple."""
        raise NotImplementedError


class ConcentrationAlert(AlertRule):
    """Alerta de concentración excesiva."""

    def __init__(self, threshold: float = 15.0):
        super().__init__(
            name="concentracion_excesiva",
            severity="warning",
            description=f"Posición individual > {threshold}% del portafolio"
        )
        self.threshold = threshold

    def check(self, data: Dict) -> Dict:
        # Esta sería una verificación más compleja con datos de posiciones
        # Por ahora, usar top_10_concentracion
        if data.get('top_10_concentracion', 0) > 50:  # Ejemplo simplificado
            return {
                'tipo': self.name,
                'mensaje': f"Alta concentración en top 10 posiciones ({data['top_10_concentracion']:.1f}%)",
                'severidad': self.severity,
                'valor': data['top_10_concentracion']
            }
        return {}


class LiquidityAlert(AlertRule):
    """Alerta de liquidez excesiva."""

    def __init__(self, threshold: float = 40.0):
        super().__init__(
            name="liquidez_excesiva",
            severity="info",
            description=f"Liquidez > {threshold}% del total"
        )
        self.threshold = threshold

    def check(self, data: Dict) -> Dict:
        pct_liquidez = data.get('pct_liquidez_desplegable_total', data.get('pct_liquidez_operativa', 0))
        if pct_liquidez > self.threshold:
            return {
                'tipo': self.name,
                'mensaje': f"Liquidez desplegable elevada ({pct_liquidez:.1f}%)",
                'severidad': self.severity,
                'valor': pct_liquidez
            }
        return {}


class CountryExposureAlert(AlertRule):
    """Alerta de exposición país excesiva."""

    def __init__(self, threshold: float = 60.0):
        super().__init__(
            name="exposicion_pais",
            severity="warning",
            description=f"Exposición a un país > {threshold}%"
        )
        self.threshold = threshold

    def check(self, data: Dict) -> Dict:
        concentracion_pais = data.get('concentracion_pais', {})
        for pais, porcentaje in concentracion_pais.items():
            if porcentaje > self.threshold:
                return {
                    'tipo': self.name,
                    'mensaje': f"Alta exposición a {pais} ({porcentaje:.1f}%)",
                    'severidad': self.severity,
                    'valor': porcentaje,
                    'pais': pais
                }
        return {}


class SectorExposureAlert(AlertRule):
    """Alerta de exposición sectorial excesiva."""

    def __init__(self, threshold: float = 30.0):
        super().__init__(
            name="exposicion_sector",
            severity="warning",
            description=f"Exposición a un sector > {threshold}%"
        )
        self.threshold = threshold

    def check(self, data: Dict) -> Dict:
        concentracion_sector = data.get('concentracion_sector', {})
        for sector, porcentaje in concentracion_sector.items():
            if porcentaje > self.threshold:
                return {
                    'tipo': self.name,
                    'mensaje': f"Alta exposición al sector {sector} ({porcentaje:.1f}%)",
                    'severidad': self.severity,
                    'valor': porcentaje,
                    'sector': sector
                }
        return {}


class LossAlert(AlertRule):
    """Alerta de pérdida significativa en activo."""

    def __init__(self, threshold: float = -20.0):
        super().__init__(
            name="perdida_significativa",
            severity="critical",
            description=f"Pérdida en activo > {abs(threshold)}%"
        )
        self.threshold = threshold

    def check(self, data: Dict) -> Dict:
        # Esta requeriría datos detallados de posiciones
        # Por ahora, placeholder
        return {}


class AlertsEngine:
    """Motor de alertas patrimoniales."""

    def __init__(self):
        self.rules = [
            ConcentrationAlert(),
            LiquidityAlert(),
            CountryExposureAlert(),
            SectorExposureAlert(),
            LossAlert(),
        ]

    def generate_alerts(self) -> List[Dict]:
        """
        Genera todas las alertas activas basadas en el estado actual del portafolio.

        Returns:
            List[Dict]: Lista de alertas activas
        """
        logger.info("Generating portfolio alerts")

        # Obtener datos actuales
        kpis = get_dashboard_kpis()
        concentracion_pais = get_concentracion_pais()
        concentracion_sector = get_concentracion_sector()
        liquidity_contract = get_liquidity_contract_summary(kpis)

        # Datos para reglas
        data = {
            'kpis': kpis,
            'concentracion_pais': concentracion_pais,
            'concentracion_sector': concentracion_sector,
            'top_10_concentracion': kpis.get('top_10_concentracion', 0),
            'pct_liquidez_operativa': kpis.get('pct_liquidez_operativa', 0),
            'pct_liquidez_desplegable_total': liquidity_contract.get('pct_liquidez_desplegable_total', 0),
        }

        alerts = []
        for rule in self.rules:
            alert = rule.check(data)
            if alert:
                alerts.append(alert)
                logger.info(f"Alert triggered: {alert['mensaje']}")

        logger.info(f"Generated {len(alerts)} alerts")
        return alerts

    def get_alerts_by_severity(self, severity: str) -> List[Dict]:
        """Obtiene alertas filtradas por severidad."""
        all_alerts = self.generate_alerts()
        return [alert for alert in all_alerts if alert['severidad'] == severity]
