from unittest.mock import ANY, patch

import pytest

from apps.dashboard.selectors import get_decision_engine_summary, get_planeacion_incremental_context

_MOD = "apps.dashboard.incremental_planeacion"


@pytest.mark.django_db
class TestDecisionEngineSummary:
    def test_get_decision_engine_summary_returns_complete_payload(self):
        class DummyUser:
            pk = 17
            is_authenticated = True

        with (
            patch(
                f"{_MOD}._build_portfolio_scope_summary",
                return_value={
                    "portfolio_total_broker": 15863589.0,
                    "invested_portfolio": 13330704.0,
                    "cash_management_fci": 2532885.0,
                    "cash_available_broker": 11039915.47,
                    "cash_ratio_total": 0.6959,
                    "invested_ratio_total": 0.8403,
                    "fci_ratio_total": 0.1597,
                },
            ),
            # lazy-imported via selectors → se parchea en selectors
            patch(
                "apps.dashboard.selectors.get_macro_local_context",
                return_value={
                    "fx_signal_state": "normal",
                    "riesgo_pais_arg": 540,
                    "uva_annualized_pct_30d": 24.5,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_analytics_v2_dashboard_summary",
                return_value={
                    "stress_testing": {"fragility_score": 48, "total_loss_pct": -11.0},
                    "expected_return": {"real_expected_return_pct": 2.1},
                    "risk_contribution": {"top_asset": {"contribution_pct": 0.18}},
                },
            ),
            patch(
                f"{_MOD}.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [
                        {
                            "label": "Defensivos USD",
                            "suggested_amount": 600000,
                            "reason": "mejora la resiliencia sin sumar complejidad",
                        }
                    ]
                },
            ),
            patch(
                f"{_MOD}.get_candidate_asset_ranking",
                return_value={
                    "candidate_assets": [
                        {"asset": "KO", "block_label": "Defensivos USD", "score": 9.4, "main_reason": "defensive_sector_match"},
                        {"asset": "MCD", "block_label": "Defensivos USD", "score": 8.8, "main_reason": "quality_dividend_mix"},
                        {"asset": "PEP", "block_label": "Defensivos USD", "score": 8.3, "main_reason": "stable_cash_flows"},
                        {"asset": "PG", "block_label": "Defensivos USD", "score": 7.9, "main_reason": "backup_option"},
                    ]
                },
            ),
            patch(
                f"{_MOD}.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "top_candidate_per_block",
                        "proposal_label": "Top candidato por bloque",
                        "source_label": "Comparador automático",
                        "comparison_score": 5.2,
                        "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                        "purchase_summary": "KO · 600000",
                        "simulation": {
                            "delta": {
                                "expected_return_change": 0.5,
                                "fragility_change": -2.1,
                                "scenario_loss_change": 0.7,
                                "risk_concentration_change": -0.6,
                            },
                            "interpretation": "Mejora el balance riesgo/retorno con una sola compra.",
                        },
                    }
                },
            ),
            patch(
                f"{_MOD}.get_incremental_portfolio_simulation",
                return_value={
                    "delta": {
                        "expected_return_change": 0.5,
                        "fragility_change": -2.1,
                        "scenario_loss_change": 0.7,
                        "risk_concentration_change": -0.6,
                    },
                    "interpretation": "La propuesta mejora el perfil sin aumentar la fragilidad.",
                },
            ),
            patch(
                f"{_MOD}.get_operation_execution_feature_context",
                return_value={
                    "tracked_symbols": ["KO"],
                    "matched_symbols_count": 1,
                    "missing_symbols_count": 0,
                    "coverage_pct": 100,
                    "rows": [],
                    "execution_analytics": {"fragmented_pct": 0},
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), capital_amount=600000)

        assert detail["macro_state"]["label"] == "Normal"
        assert detail["portfolio_state"]["label"] == "OK"
        assert detail["portfolio_scope"]["cash_ratio_total"] == 0.6959
        assert detail["recommendation_context"] == "high_cash"
        assert detail["strategy_bias"] == "deploy_cash"
        assert detail["action_suggestions"] == [
            {
                "type": "allocation",
                "message": "Tenés capital disponible para invertir",
                "suggestion": "Evaluar asignar entre 20% y 40% del cash.",
            }
        ]
        assert detail["recommendation"]["block"] == "Defensivos USD"
        assert detail["recommendation"]["amount"] == 600000
        assert len(detail["suggested_assets"]) == 3
        assert [item["symbol"] for item in detail["suggested_assets"]] == ["KO", "MCD", "PEP"]
        assert detail["preferred_proposal"]["proposal_label"] == "Top candidato por bloque"
        assert detail["expected_impact"]["status"] == "positive"
        assert 0 <= detail["score"] <= 100
        assert detail["confidence"] in {"Alta", "Media", "Baja"}
        assert detail["confidence"] == "Alta"
        assert 1 <= len(detail["explanation"]) <= 8
        assert all(isinstance(item, str) and item for item in detail["explanation"])
        assert detail["tracking_payload"]["score"] == detail["score"]
        assert detail["tracking_payload"]["confidence"] == "Alta"
        assert detail["tracking_payload"]["purchase_plan"] == [{"symbol": "KO", "amount": 600000}]
        assert detail["tracking_payload"]["governance"]["parking_signal_active"] is False
        assert detail["tracking_payload"]["governance"]["market_history_signal_active"] is False

    def test_get_decision_engine_summary_handles_missing_macro_preferred_and_simulation(self):
        class DummyUser:
            pk = 19
            is_authenticated = True

        with (
            patch(
                f"{_MOD}._build_portfolio_scope_summary",
                return_value={
                    "portfolio_total_broker": 15863589.0,
                    "invested_portfolio": 15000000.0,
                    "cash_management_fci": 300000.0,
                    "cash_available_broker": 100000.0,
                    "cash_ratio_total": 0.006,
                    "invested_ratio_total": 0.945,
                    "fci_ratio_total": 0.02,
                },
            ),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch(
                "apps.dashboard.selectors.get_analytics_v2_dashboard_summary",
                return_value={"stress_testing": {}, "expected_return": {}, "risk_contribution": {}},
            ),
            patch(f"{_MOD}.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch(f"{_MOD}.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(f"{_MOD}.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch(f"{_MOD}.get_incremental_portfolio_simulation", return_value=None),
        ):
            detail = get_decision_engine_summary(DummyUser(), capital_amount=600000)

        assert detail["macro_state"]["key"] == "indefinido"
        assert detail["portfolio_state"]["key"] == "indefinido"
        assert detail["recommendation_context"] == "fully_invested"
        assert detail["strategy_bias"] == "rebalance"
        assert detail["action_suggestions"] == [
            {
                "type": "rebalance",
                "message": "Cartera altamente invertida",
                "suggestion": "Evaluar reducción de concentración en top posiciones.",
            }
        ]
        assert detail["recommendation"]["has_recommendation"] is False
        assert detail["suggested_assets"] == []
        assert detail["preferred_proposal"] is None
        assert detail["expected_impact"]["status"] == "neutral"
        assert detail["confidence"] == "Baja"
        assert 0 <= detail["score"] <= 100
        assert len(detail["explanation"]) <= 4
        assert detail["tracking_payload"]["purchase_plan"] == []

    def test_get_planeacion_incremental_context_exposes_decision_engine_summary(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(f"{_MOD}.get_monthly_allocation_plan", return_value={"capital_total": 600000}),
            patch(f"{_MOD}.get_candidate_asset_ranking", return_value={"candidate_assets_count": 2}),
            patch(f"{_MOD}.get_incremental_portfolio_simulation", return_value={"interpretation": "ok"}),
            patch(f"{_MOD}.get_incremental_portfolio_simulation_comparison", return_value={"best_label": "Top candidato por bloque"}),
            patch(f"{_MOD}.get_candidate_incremental_portfolio_comparison", return_value={"selected_block": "defensive"}),
            patch(f"{_MOD}.get_candidate_split_incremental_portfolio_comparison", return_value={"selected_block": "defensive"}),
            patch(f"{_MOD}.get_manual_incremental_portfolio_simulation_comparison", return_value={"submitted": False}),
            patch(f"{_MOD}.get_preferred_incremental_portfolio_proposal", return_value={"preferred": {"proposal_label": "Split KO + MCD"}}),
            patch(f"{_MOD}.get_decision_engine_summary", return_value={"score": 78, "confidence": "Alta"}) as decision_engine,
            patch(f"{_MOD}.get_incremental_proposal_history", return_value={"count": 1, "active_filter": "pending"}),
            patch(f"{_MOD}.get_incremental_proposal_tracking_baseline", return_value={"has_baseline": True}),
            patch(f"{_MOD}.get_incremental_backlog_prioritization", return_value={"has_priorities": True, "count": 2}),
            patch(f"{_MOD}.get_incremental_manual_decision_summary", return_value={"has_decision": True}),
            patch(f"{_MOD}.get_incremental_decision_executive_summary", return_value={"status": "review_backlog"}),
        ):
            detail = get_planeacion_incremental_context(
                {"decision_status_filter": "pending"},
                user=DummyUser(),
                capital_amount=700000,
                history_limit=7,
            )

        assert detail["decision_engine_summary"]["score"] == 78
        assert detail["decision_engine_summary"]["confidence"] == "Alta"
        assert detail["incremental_backlog_prioritization"]["count"] == 2
        decision_engine.assert_called_once_with(ANY, query_params={"decision_status_filter": "pending"}, capital_amount=700000)
