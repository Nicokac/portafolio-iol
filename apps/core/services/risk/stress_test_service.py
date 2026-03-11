from dataclasses import dataclass
from typing import Dict, Iterable

from django.db.models import Max

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


@dataclass(frozen=True)
class StressScenario:
    key: str
    name: str


class StressTestService:
    """
    Stress testing simple por factores.
    Impacto expresado como % sobre Total IOL.
    """

    SCENARIOS: Iterable[StressScenario] = (
        StressScenario("usd_plus_20", "USD +20%"),
        StressScenario("usa_rates_up_200bps", "Tasas USA +200bps"),
        StressScenario("equity_drop_15", "Caída equity -15%"),
        StressScenario("argentina_crisis", "Crisis argentina"),
    )

    def run_all(self) -> Dict[str, Dict[str, float]]:
        activos, resumen, total_iol = self._load_portfolio_state()
        if total_iol <= 0:
            return {}

        parameters = self._load_parameters(activos)
        scenarios = {}
        for scenario in self.SCENARIOS:
            impact_value = self._scenario_impact_value(scenario.key, activos, resumen, parameters)
            impact_pct = (impact_value / total_iol) * 100 if total_iol else 0
            scenarios[scenario.key] = {
                "label": scenario.name,
                "impact_value": round(impact_value, 2),
                "impact_portfolio_pct": round(impact_pct, 2),
            }
        return scenarios

    def _load_portfolio_state(self):
        latest_portafolio = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]
        latest_resumen = ResumenCuentaSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]

        activos = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_portafolio)
        ) if latest_portafolio else []
        resumen = list(
            ResumenCuentaSnapshot.objects.filter(fecha_extraccion=latest_resumen)
        ) if latest_resumen else []

        total_activos = sum(float(a.valorizado) for a in activos)
        total_cash = sum(float(c.disponible) for c in resumen)
        return activos, resumen, total_activos + total_cash

    @staticmethod
    def _load_parameters(activos):
        symbols = [a.simbolo for a in activos]
        return {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=symbols)}

    def _scenario_impact_value(self, scenario_key, activos, resumen, parameters):
        impact = 0.0

        for activo in activos:
            value = float(activo.valorizado)
            symbol = activo.simbolo
            param = parameters.get(symbol)
            asset_type = (activo.tipo or "").upper()
            exposure_country = (param.pais_exposicion if param else "").lower()
            patrimonial_type = (param.tipo_patrimonial if param else "").lower()
            currency = (activo.moneda or "").lower()

            shock = 0.0
            if scenario_key == "usd_plus_20":
                if "dolar" in currency or exposure_country in {"usa", "estados unidos"}:
                    shock = 0.20
            elif scenario_key == "usa_rates_up_200bps":
                if exposure_country in {"usa", "estados unidos"} and (
                    "bond" in patrimonial_type or "titulospublicos" in asset_type
                ):
                    shock = -0.10
                elif exposure_country in {"usa", "estados unidos"}:
                    shock = -0.05
            elif scenario_key == "equity_drop_15":
                if asset_type in {"ACCIONES", "CEDEARS"} or "equity" in patrimonial_type or "etf" in symbol.lower():
                    shock = -0.15
            elif scenario_key == "argentina_crisis":
                if exposure_country == "argentina":
                    if "bond" in patrimonial_type or "titulospublicos" in asset_type:
                        shock = -0.30
                    else:
                        shock = -0.25

            impact += value * shock

        if scenario_key == "argentina_crisis":
            for cuenta in resumen:
                if (cuenta.moneda or "").upper() == "ARS":
                    impact += float(cuenta.disponible) * -0.10

        return impact
