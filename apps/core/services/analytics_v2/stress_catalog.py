from __future__ import annotations

from dataclasses import dataclass

from .schemas import StressDefinition


@dataclass(frozen=True)
class StressCatalogEntry:
    definition: StressDefinition
    category: str
    scenario_keys: tuple[str, ...]
    legacy_mapping_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = self.definition.to_dict()
        payload["category"] = self.category
        payload["scenario_keys"] = list(self.scenario_keys)
        payload["legacy_mapping_keys"] = list(self.legacy_mapping_keys)
        return payload


STRESS_CATALOG: tuple[StressCatalogEntry, ...] = (
    StressCatalogEntry(
        definition=StressDefinition(
            stress_key="usa_crash_severe",
            label="Crash USA severo",
            description="Shock severo sobre equity USA con sesgo de mercado amplio y caida superior al escenario moderado.",
        ),
        category="global_equity_extreme",
        scenario_keys=("spy_down_20",),
        legacy_mapping_keys=("equity_drop_15",),
    ),
    StressCatalogEntry(
        definition=StressDefinition(
            stress_key="local_crisis_severe",
            label="Crisis local severa",
            description="Stress extremo sobre instrumentos argentinos, incluyendo deuda y equity local.",
        ),
        category="local_country_extreme",
        scenario_keys=("argentina_stress", "ars_devaluation"),
        legacy_mapping_keys=("argentina_crisis", "usd_plus_20"),
    ),
    StressCatalogEntry(
        definition=StressDefinition(
            stress_key="rates_equity_double_shock",
            label="Doble shock tasas + equity",
            description="Combinacion de suba severa de tasas USA con deterioro simultaneo de equity sensible.",
        ),
        category="rates_and_equity_extreme",
        scenario_keys=("usa_rates_up_200bps", "spy_down_10"),
        legacy_mapping_keys=("usa_rates_up_200bps", "equity_drop_15"),
    ),
    StressCatalogEntry(
        definition=StressDefinition(
            stress_key="em_deterioration",
            label="Deterioro emergente",
            description="Stress severo sobre mercados emergentes y activos ligados a deuda o equity EM.",
        ),
        category="emerging_markets_extreme",
        scenario_keys=("em_stress",),
        legacy_mapping_keys=(),
    ),
)


class StressCatalogService:
    """Catalogo cerrado de stresses extremos MVP para stress fragility."""

    def list_stresses(self) -> list[dict]:
        return [entry.to_dict() for entry in STRESS_CATALOG]

    def get_stress(self, stress_key: str) -> dict | None:
        normalized = str(stress_key or "").strip().lower()
        for entry in STRESS_CATALOG:
            if entry.definition.stress_key == normalized:
                return entry.to_dict()
        return None

    def require_stress(self, stress_key: str) -> dict:
        stress = self.get_stress(stress_key)
        if stress is None:
            raise ValueError(f"Unknown stress_key: {stress_key}")
        return stress
