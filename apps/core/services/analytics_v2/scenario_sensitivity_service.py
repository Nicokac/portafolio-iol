from __future__ import annotations

from apps.core.services.analytics_v2.helpers import normalize_country_label
from apps.core.services.analytics_v2.scenario_catalog import ScenarioCatalogService
from apps.core.services.analytics_v2.schemas import NormalizedPosition


class ScenarioSensitivityService:
    """Motor heuristico de sensibilidad por activo para escenarios MVP."""

    def __init__(self, catalog_service: ScenarioCatalogService | None = None):
        self.catalog_service = catalog_service or ScenarioCatalogService()

    def resolve_asset_sensitivity(self, scenario_key: str, position: NormalizedPosition) -> dict:
        self.catalog_service.require_scenario(scenario_key)

        handlers = {
            "spy_down_10": self._spy_down_10,
            "spy_down_20": self._spy_down_20,
            "tech_shock": self._tech_shock,
            "argentina_stress": self._argentina_stress,
            "ars_devaluation": self._ars_devaluation,
            "em_stress": self._em_stress,
            "usa_rates_up_200bps": self._usa_rates_up_200bps,
        }
        return handlers[scenario_key](position)

    def _spy_down_10(self, position: NormalizedPosition) -> dict:
        if self._is_us_equity(position):
            return self._response(-0.10, "equity_usa")
        if self._is_global_equity(position):
            return self._response(-0.06, "equity_global")
        if self._is_bond(position):
            return self._response(-0.02, "risk_off_spread")
        return self._response(0.0, "cash_like")

    def _spy_down_20(self, position: NormalizedPosition) -> dict:
        if self._is_us_equity(position):
            return self._response(-0.20, "equity_usa")
        if self._is_global_equity(position):
            return self._response(-0.12, "equity_global")
        if self._is_bond(position):
            return self._response(-0.04, "risk_off_spread")
        return self._response(0.0, "cash_like")

    def _tech_shock(self, position: NormalizedPosition) -> dict:
        if self._is_technology(position):
            return self._response(-0.18, "sector_technology")
        if self._is_us_equity(position):
            return self._response(-0.06, "equity_usa_secondary")
        return self._response(0.0, "non_tech_or_cash")

    def _argentina_stress(self, position: NormalizedPosition) -> dict:
        if normalize_country_label(position.country) == "Argentina":
            if self._is_bond(position):
                return self._response(-0.30, "country_argentina_bond")
            return self._response(-0.25, "country_argentina_equity")
        return self._response(0.0, "non_argentina")

    def _ars_devaluation(self, position: NormalizedPosition) -> dict:
        if self._is_us_exposure(position):
            return self._response(0.20, "usd_exposure")
        if normalize_country_label(position.country) == "Argentina":
            return self._response(-0.08, "ars_local_assets")
        return self._response(0.0, "neutral_fx")

    def _em_stress(self, position: NormalizedPosition) -> dict:
        country = normalize_country_label(position.country)
        if country in {"Argentina", "Brasil", "EM"}:
            if self._is_bond(position):
                return self._response(-0.12, "em_bond")
            return self._response(-0.10, "em_equity")
        return self._response(0.0, "non_em")

    def _usa_rates_up_200bps(self, position: NormalizedPosition) -> dict:
        if normalize_country_label(position.country) == "USA":
            if self._is_bond(position):
                return self._response(-0.10, "rates_usa_bond")
            if self._is_us_equity(position):
                return self._response(-0.05, "rates_usa_equity")
        return self._response(0.0, "non_usa_or_cash")

    @staticmethod
    def _response(multiplier: float, transmission_channel: str) -> dict:
        return {
            "shock_multiplier": multiplier,
            "transmission_channel": transmission_channel,
        }

    @staticmethod
    def _is_bond(position: NormalizedPosition) -> bool:
        asset_type = (position.asset_type or "").strip().lower()
        patrimonial = (position.patrimonial_type or "").strip().lower()
        return asset_type == "bond" or patrimonial == "bond"

    @staticmethod
    def _is_us_equity(position: NormalizedPosition) -> bool:
        return (
            normalize_country_label(position.country) == "USA"
            and (position.asset_type or "").strip().lower() in {"equity", "etf"}
        )

    @staticmethod
    def _is_global_equity(position: NormalizedPosition) -> bool:
        return (position.asset_type or "").strip().lower() in {"equity", "etf"}

    @staticmethod
    def _is_us_exposure(position: NormalizedPosition) -> bool:
        country = normalize_country_label(position.country)
        currency = (position.currency or "").strip().upper()
        return country == "USA" or currency == "USD"

    @staticmethod
    def _is_technology(position: NormalizedPosition) -> bool:
        sector = (position.sector or "").strip().lower()
        bucket = (position.strategic_bucket or "").strip().lower()
        return "tecnolog" in sector or "tech" in sector or bucket == "growth"
