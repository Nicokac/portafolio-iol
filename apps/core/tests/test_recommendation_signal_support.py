from apps.core.services.recommendation_signal_support import (
    build_analytics_v2_recommendations,
    recommendation_topic_key,
    recommendation_sort_key,
)


def test_build_analytics_v2_recommendations_uses_service_mappers():
    empty_service = lambda: type("DummySignals", (), {"build_recommendation_signals": lambda self: []})()

    class DummyService:
        def _build_risk_contribution_signals(self):
            return [{"signal_key": "alpha", "severity": "high"}]

        def _map_signal_to_recommendation(self, signal):
            return {
                "tipo": f"mapped_{signal['signal_key']}",
                "prioridad": "alta",
            }

    result = build_analytics_v2_recommendations(
        DummyService(),
        empty_service,
        empty_service,
        empty_service,
        empty_service,
        empty_service,
    )

    assert result == [{"tipo": "mapped_alpha", "prioridad": "alta"}]


def test_recommendation_topic_key_groups_argentina_country_overconcentration():
    result = recommendation_topic_key(
        {
            "tipo": "analytics_v2_country_risk_overconcentration",
            "evidence": {"country": "Argentina"},
        }
    )

    assert result == "argentina_concentration"


def test_recommendation_sort_key_prefers_analytics_with_assets():
    analytics_key = recommendation_sort_key(
        {
            "tipo": "analytics_v2_expected_return_liquidity_drag",
            "prioridad": "media",
            "origen": "analytics_v2",
            "activos_sugeridos": ["SPY"],
        },
        1,
        {"alta": 0, "media": 1, "baja": 2},
    )
    classic_key = recommendation_sort_key(
        {
            "tipo": "liquidez_excesiva",
            "prioridad": "media",
        },
        0,
        {"alta": 0, "media": 1, "baja": 2},
    )

    assert analytics_key < classic_key
