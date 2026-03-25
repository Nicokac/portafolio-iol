from apps.dashboard.decision_recommendation import _build_decision_recommendation


def test_build_decision_recommendation_reprioritizes_clean_alternative_when_market_history_is_weak():
    result = _build_decision_recommendation(
        {
            "recommended_blocks": [
                {
                    "label": "Defensivos USD",
                    "suggested_amount": 600000,
                    "reason": "bloque original",
                },
                {
                    "label": "Calidad global",
                    "suggested_amount": 400000,
                    "reason": "alternativa limpia",
                },
            ]
        },
        market_history_feature={
            "weak_blocks": [{"label": "Defensivos USD"}],
        },
    )

    assert result["block"] == "Calidad global"
    assert result["was_reprioritized_by_market_history"] is True
