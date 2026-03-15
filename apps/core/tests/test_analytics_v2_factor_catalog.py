import pytest

from apps.core.services.analytics_v2.factor_catalog import (
    FACTOR_CATALOG,
    FactorCatalogService,
)


def test_factor_catalog_contains_expected_mvp_keys():
    keys = [entry.definition.factor_key for entry in FACTOR_CATALOG]

    assert keys == [
        "growth",
        "value",
        "quality",
        "dividend",
        "defensive",
        "cyclical",
    ]


def test_factor_catalog_service_lists_serializable_factors():
    service = FactorCatalogService()

    factors = service.list_factors()

    assert len(factors) == 6
    assert factors[0]["factor_key"] == "growth"
    assert "description" in factors[0]
    assert "classification_notes" in factors[0]
    assert "style_family" in factors[0]


def test_factor_catalog_service_can_resolve_single_factor():
    service = FactorCatalogService()

    factor = service.get_factor("defensive")

    assert factor is not None
    assert factor["label"] == "Defensive"
    assert factor["style_family"] == "risk_style"


def test_factor_catalog_service_returns_none_for_unknown_key():
    service = FactorCatalogService()

    assert service.get_factor("unknown_factor") is None


def test_factor_catalog_service_requires_known_factor():
    service = FactorCatalogService()

    with pytest.raises(ValueError, match="Unknown factor_key"):
        service.require_factor("unknown_factor")
