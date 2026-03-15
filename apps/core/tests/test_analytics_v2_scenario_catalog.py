import pytest

from apps.core.services.analytics_v2.scenario_catalog import (
    SCENARIO_CATALOG,
    ScenarioCatalogService,
)


def test_scenario_catalog_contains_expected_mvp_keys():
    keys = [entry.definition.scenario_key for entry in SCENARIO_CATALOG]

    assert keys == [
        "spy_down_10",
        "spy_down_20",
        "tech_shock",
        "argentina_stress",
        "ars_devaluation",
        "em_stress",
        "usa_rates_up_200bps",
    ]


def test_scenario_catalog_service_lists_serializable_scenarios():
    service = ScenarioCatalogService()

    scenarios = service.list_scenarios()

    assert len(scenarios) == 7
    assert scenarios[0]["scenario_key"] == "spy_down_10"
    assert "category" in scenarios[0]
    assert "legacy_mapping_key" in scenarios[0]


def test_scenario_catalog_service_can_resolve_single_scenario():
    service = ScenarioCatalogService()

    scenario = service.get_scenario("argentina_stress")

    assert scenario is not None
    assert scenario["label"] == "Stress Argentina"
    assert scenario["legacy_mapping_key"] == "argentina_crisis"


def test_scenario_catalog_service_returns_none_for_unknown_key():
    service = ScenarioCatalogService()

    assert service.get_scenario("unknown_scenario") is None


def test_scenario_catalog_service_requires_known_scenario():
    service = ScenarioCatalogService()

    with pytest.raises(ValueError, match="Unknown scenario_key"):
        service.require_scenario("unknown_scenario")
