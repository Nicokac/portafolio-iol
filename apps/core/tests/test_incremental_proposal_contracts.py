from apps.core.services.incremental_proposal_contracts import (
    build_incremental_purchase_plan_summary,
    normalize_incremental_proposal_payload,
)


def test_build_incremental_purchase_plan_summary_limits_to_first_three_items():
    summary = build_incremental_purchase_plan_summary(
        [
            {"symbol": "KO", "amount": 200000},
            {"symbol": "MCD", "amount": 200000},
            {"symbol": "XLU", "amount": 200000},
            {"symbol": "PEP", "amount": 100000},
        ]
    )

    assert summary == "KO (200000), MCD (200000), XLU (200000)"


def test_normalize_incremental_proposal_payload_builds_common_aliases():
    normalized = normalize_incremental_proposal_payload(
        {
            "label": "Plan manual A",
            "purchase_plan": [{"symbol": "KO", "amount": 200000}],
            "simulation": {
                "delta": {"expected_return_change": 0.12},
                "interpretation": "Mejora el balance defensivo.",
            },
        }
    )

    assert normalized["proposal_label"] == "Plan manual A"
    assert normalized["label"] == "Plan manual A"
    assert normalized["purchase_summary"] == "KO (200000)"
    assert normalized["simulation_delta"]["expected_return_change"] == 0.12
    assert normalized["simulation"]["interpretation"] == "Mejora el balance defensivo."
