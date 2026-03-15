from dataclasses import dataclass

from apps.core.services.analytics_v2.helpers import (
    aggregate_aliases,
    aggregate_numeric_items,
    aggregate_positions_by_field,
    build_data_quality_flags,
    build_group_items,
    derive_confidence,
    normalize_country_label,
    normalize_percentage_allocation,
    rank_top_items,
    safe_percentage,
)


@dataclass
class DummyPosition:
    symbol: str
    sector: str | None
    country: str | None
    market_value: float


def test_safe_percentage_returns_zero_when_denominator_is_zero():
    assert safe_percentage(10, 0) == 0.0


def test_normalize_percentage_allocation_closes_rounding_drift():
    result = normalize_percentage_allocation({"A": 1, "B": 1, "C": 1})

    assert result
    assert round(sum(result.values()), 2) == 100.0


def test_aggregate_numeric_items_groups_unknown_and_applies_normalizer():
    items = [
        {"country": "Estados Unidos", "value": 10},
        {"country": "USA", "value": 5},
        {"country": None, "value": 3},
    ]

    result = aggregate_numeric_items(
        items,
        key_getter=lambda item: item["country"],
        value_getter=lambda item: item["value"],
        normalizer=normalize_country_label,
    )

    assert result == {"USA": 15.0, "unknown": 3.0}


def test_aggregate_positions_by_field_groups_objects():
    positions = [
        DummyPosition(symbol="AAPL", sector="Tecnologia", country="USA", market_value=100),
        DummyPosition(symbol="MSFT", sector="Tecnologia", country="Estados Unidos", market_value=50),
        DummyPosition(symbol="AL30", sector=None, country="Argentina", market_value=25),
    ]

    result = aggregate_positions_by_field(
        positions,
        "country",
        value_getter=lambda item: item.market_value,
        normalizer=normalize_country_label,
    )

    assert result == {"USA": 150.0, "Argentina": 25.0}


def test_aggregate_aliases_merges_multiple_labels():
    result = aggregate_aliases(
        {
            "Tecnologia": 10,
            "Tecnologia / E-commerce": 5,
            "Utilities": 3,
        },
        alias_resolver=lambda key: "Tecnologia Total" if key.startswith("Tecnologia") else key,
    )

    assert result == {"Tecnologia Total": 15.0, "Utilities": 3.0}


def test_build_group_items_orders_desc_and_calculates_weight_pct():
    items = build_group_items({"USA": 60, "Argentina": 40}, basis_total=200)

    assert [item.key for item in items] == ["USA", "Argentina"]
    assert items[0].contribution_pct == 60.0
    assert items[0].weight_pct == 30.0


def test_rank_top_items_respects_limit_and_order():
    positions = [
        DummyPosition(symbol="AAPL", sector="Tecnologia", country="USA", market_value=100),
        DummyPosition(symbol="MSFT", sector="Tecnologia", country="USA", market_value=200),
        DummyPosition(symbol="AL30", sector="Bond", country="Argentina", market_value=50),
    ]

    ranked = rank_top_items(positions, lambda item: item.market_value, limit=2)

    assert [item.symbol for item in ranked] == ["MSFT", "AAPL"]


def test_derive_confidence_degrades_for_missing_data_and_fallbacks():
    assert derive_confidence() == "high"
    assert derive_confidence(used_fallback=True) == "medium"
    assert derive_confidence(has_missing_metadata=True, used_fallback=True) == "low"
    assert derive_confidence(has_insufficient_history=True) == "low"


def test_build_data_quality_flags_deduplicates_warnings():
    flags = build_data_quality_flags(
        has_missing_metadata=True,
        used_fallback=True,
        warnings=["missing_metadata", "missing_metadata", "used_fallback"],
    )

    payload = flags.to_dict()

    assert payload["confidence"] == "low"
    assert payload["warnings"] == ["missing_metadata", "used_fallback"]
