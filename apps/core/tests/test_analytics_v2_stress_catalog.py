import pytest

from apps.core.services.analytics_v2.stress_catalog import (
    STRESS_CATALOG,
    StressCatalogService,
)


def test_stress_catalog_contains_expected_mvp_keys():
    keys = [entry.definition.stress_key for entry in STRESS_CATALOG]

    assert keys == [
        "usa_crash_severe",
        "local_crisis_severe",
        "rates_equity_double_shock",
        "em_deterioration",
    ]


def test_stress_catalog_service_lists_serializable_stresses():
    service = StressCatalogService()

    stresses = service.list_stresses()

    assert len(stresses) == 4
    assert stresses[0]["stress_key"] == "usa_crash_severe"
    assert "category" in stresses[0]
    assert "scenario_keys" in stresses[0]
    assert "legacy_mapping_keys" in stresses[0]


def test_stress_catalog_service_can_resolve_single_stress():
    service = StressCatalogService()

    stress = service.get_stress("local_crisis_severe")

    assert stress is not None
    assert stress["label"] == "Crisis local severa"
    assert stress["scenario_keys"] == ["argentina_stress", "ars_devaluation"]


def test_stress_catalog_service_returns_none_for_unknown_key():
    service = StressCatalogService()

    assert service.get_stress("unknown_stress") is None


def test_stress_catalog_service_requires_known_stress():
    service = StressCatalogService()

    with pytest.raises(ValueError, match="Unknown stress_key"):
        service.require_stress("unknown_stress")
