from decimal import Decimal

from apps.core.services.monthly_allocation_rules import (
    build_candidate_map,
    fallback_liquidity_candidate,
    should_use_liquidity_fallback,
)


def test_build_candidate_map_seeds_base_biases():
    candidates = build_candidate_map(
        {
            "dividend": {"label": "Dividend"},
            "fixed_income_ar": {"label": "Renta fija"},
        }
    )

    assert candidates["dividend"]["score"] == Decimal("0.5")
    assert candidates["fixed_income_ar"]["score"] == Decimal("0.25")


def test_should_use_liquidity_fallback_requires_overload_and_no_positive_edges():
    use_fallback = should_use_liquidity_fallback(
        analytics={
            "factor_result": {"underrepresented_factors": []},
            "expected_return_result": {"by_bucket": []},
        },
        avoided_blocks={"a": {}, "b": {}},
    )

    assert use_fallback is True


def test_fallback_liquidity_candidate_preserves_expected_bucket():
    candidate = fallback_liquidity_candidate(liquidity_label="Liquidez tactica ARS")

    assert candidate["bucket"] == "liquidity_ars"
    assert candidate["score_breakdown"]["positive_signals"][0]["signal"] == "fallback_liquidity_preservation"
