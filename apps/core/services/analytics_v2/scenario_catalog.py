from __future__ import annotations

from dataclasses import dataclass

from .schemas import ScenarioDefinition


@dataclass(frozen=True)
class ScenarioCatalogEntry:
    definition: ScenarioDefinition
    category: str
    legacy_mapping_key: str | None = None

    def to_dict(self) -> dict:
        payload = self.definition.to_dict()
        payload["category"] = self.category
        payload["legacy_mapping_key"] = self.legacy_mapping_key
        return payload


SCENARIO_CATALOG: tuple[ScenarioCatalogEntry, ...] = (
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="spy_down_10",
            label="SPY -10%",
            description="Shock moderado sobre equity USA de referencia.",
        ),
        category="global_equity",
        legacy_mapping_key="equity_drop_15",
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="spy_down_20",
            label="SPY -20%",
            description="Shock severo sobre equity USA de referencia.",
        ),
        category="global_equity",
        legacy_mapping_key="equity_drop_15",
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="tech_shock",
            label="Shock Tech",
            description="Caida sectorial concentrada en tecnologia y growth.",
        ),
        category="sector",
        legacy_mapping_key=None,
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="argentina_stress",
            label="Stress Argentina",
            description="Stress local sobre instrumentos con exposicion argentina.",
        ),
        category="country",
        legacy_mapping_key="argentina_crisis",
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="ars_devaluation",
            label="Devaluacion ARS",
            description="Shock cambiario sobre exposicion dolarizada y activos locales en ARS.",
        ),
        category="fx",
        legacy_mapping_key="usd_plus_20",
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="em_stress",
            label="Stress Emergentes",
            description="Compresion negativa sobre mercados emergentes y deuda relacionada.",
        ),
        category="emerging_markets",
        legacy_mapping_key=None,
    ),
    ScenarioCatalogEntry(
        definition=ScenarioDefinition(
            scenario_key="usa_rates_up_200bps",
            label="Tasas USA +200bps",
            description="Suba abrupta de tasas en Estados Unidos con impacto en bonos y equity sensible.",
        ),
        category="rates",
        legacy_mapping_key="usa_rates_up_200bps",
    ),
)


class ScenarioCatalogService:
    """Catalogo cerrado de escenarios MVP para scenario analysis."""

    def list_scenarios(self) -> list[dict]:
        return [entry.to_dict() for entry in SCENARIO_CATALOG]

    def get_scenario(self, scenario_key: str) -> dict | None:
        for entry in SCENARIO_CATALOG:
            if entry.definition.scenario_key == scenario_key:
                return entry.to_dict()
        return None

    def require_scenario(self, scenario_key: str) -> dict:
        scenario = self.get_scenario(scenario_key)
        if scenario is None:
            raise ValueError(f"Unknown scenario_key: {scenario_key}")
        return scenario
