"""
Zona 5: orquestadores de Decision Engine y Planeacion Incremental.

Extraído de selectors.py – depende de múltiples módulos ya extraídos.
Las funciones todavía en selectors.py (get_macro_local_context, etc.) se
importan de forma diferida (lazy) para evitar importaciones circulares.
"""
import hashlib
from typing import Dict

from apps.dashboard.decision_engine import (
    _annotate_preferred_proposal_with_execution_quality,
    _build_decision_action_suggestions,
    _build_decision_engine_query_stamp,
    _build_decision_execution_gate,
    _build_decision_expected_impact,
    _build_decision_explanation,
    _build_decision_macro_state,
    _build_decision_market_history_signal,
    _build_decision_operation_execution_signal,
    _build_decision_parking_signal,
    _build_decision_portfolio_state,
    _build_decision_preferred_proposal,
    _build_decision_recommendation,
    _build_decision_recommendation_context,
    _build_decision_strategy_bias,
    _build_decision_suggested_assets,
    _build_decision_tracking_payload,
    _compute_decision_confidence,
    _compute_decision_score,
)
from apps.dashboard.incremental_comparators import (
    _build_incremental_comparator_activity_summary,
    _build_incremental_comparator_hidden_inputs,
    _build_planeacion_aportes_reset_url,
    _ensure_incremental_comparator_display_summary,
    _query_param_value,
)
from apps.dashboard.incremental_future_purchases import (
    get_incremental_manual_decision_summary,
    get_incremental_proposal_tracking_baseline,
)
from apps.dashboard.incremental_reactivation_workflow import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_reactivation_vs_backlog_summary,
    get_incremental_reactivation_summary,
)
from apps.dashboard.incremental_simulation import (
    get_candidate_asset_ranking,
    get_candidate_incremental_portfolio_comparison,
    get_candidate_split_incremental_portfolio_comparison,
    get_incremental_portfolio_simulation,
    get_incremental_portfolio_simulation_comparison,
    get_manual_incremental_portfolio_simulation_comparison,
    get_monthly_allocation_plan,
    get_operation_execution_feature_context,
    get_preferred_incremental_portfolio_proposal,
)
from apps.dashboard.incremental_backlog import (
    get_incremental_backlog_prioritization,
    get_incremental_decision_executive_summary,
    get_incremental_proposal_history,
)
from apps.dashboard.portfolio_enrichment import (
    build_portfolio_scope_summary,
    extract_resumen_cash_components,
)
from apps.dashboard.selector_cache import _get_cached_selector_result


def _build_portfolio_scope_summary() -> Dict:
    """Explicita el universo broker vs capital invertido para Planeacion."""
    # Lazy: get_dashboard_kpis y get_latest_resumen_data siguen en selectors.py
    from apps.dashboard.selectors import get_dashboard_kpis, get_latest_resumen_data
    kpis = get_dashboard_kpis()
    resumen = get_latest_resumen_data()
    cash_components = extract_resumen_cash_components(resumen)
    return build_portfolio_scope_summary(kpis, cash_components)


def get_decision_engine_summary(
    user,
    *,
    query_params=None,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compone una sintesis unica de decision mensual reutilizando selectors existentes."""
    # Lazy: estas funciones siguen en selectors.py
    from apps.dashboard.selectors import (
        get_analytics_v2_dashboard_summary,
        get_macro_local_context,
        get_market_snapshot_history_feature_context,
        get_portfolio_parking_feature_context,
    )

    query_params = query_params or {}
    query_stamp = _build_decision_engine_query_stamp(query_params)
    query_signature = hashlib.md5(query_stamp.encode("utf-8")).hexdigest()
    cache_key = f"decision_engine_summary:{getattr(user, 'pk', 'anon')}:{int(capital_amount)}:{query_signature}"

    def build():
        portfolio_scope = _build_portfolio_scope_summary()
        macro_local = get_macro_local_context()
        analytics = get_analytics_v2_dashboard_summary()
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        preferred_payload = get_preferred_incremental_portfolio_proposal(
            query_params,
            capital_amount=capital_amount,
        )
        simulation = get_incremental_portfolio_simulation(capital_amount=capital_amount)

        macro_state = _build_decision_macro_state(macro_local)
        portfolio_state = _build_decision_portfolio_state(analytics)
        parking_feature = get_portfolio_parking_feature_context()
        market_history_feature = get_market_snapshot_history_feature_context()
        recommendation = _build_decision_recommendation(
            monthly_plan,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        suggested_assets = _build_decision_suggested_assets(
            ranking,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        preferred_proposal = _build_decision_preferred_proposal(
            preferred_payload,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        operation_execution_feature = get_operation_execution_feature_context(
            purchase_plan=(preferred_proposal or {}).get("purchase_plan") or [],
            lookback_days=180,
            symbol_limit=3,
        )
        preferred_proposal = _annotate_preferred_proposal_with_execution_quality(
            preferred_proposal,
            operation_execution_feature=operation_execution_feature,
        )
        expected_impact = _build_decision_expected_impact(simulation)
        recommendation_context = _build_decision_recommendation_context(portfolio_scope)
        strategy_bias = _build_decision_strategy_bias(recommendation_context)
        parking_signal = _build_decision_parking_signal(parking_feature)
        market_history_signal = _build_decision_market_history_signal(
            market_history_feature=market_history_feature,
            recommendation=recommendation,
            preferred_proposal=preferred_proposal,
        )
        operation_execution_signal = _build_decision_operation_execution_signal(
            operation_execution_feature=operation_execution_feature,
            preferred_proposal=preferred_proposal,
        )
        execution_gate = _build_decision_execution_gate(
            parking_signal=parking_signal,
            operation_execution_signal=operation_execution_signal,
            preferred_proposal=preferred_proposal,
        )
        action_suggestions = _build_decision_action_suggestions(
            strategy_bias,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            operation_execution_signal=operation_execution_signal,
        )
        score = _compute_decision_score(
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            recommendation=recommendation,
            suggested_assets=suggested_assets,
            preferred_proposal=preferred_proposal,
            expected_impact=expected_impact,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            operation_execution_signal=operation_execution_signal,
        )
        confidence = _compute_decision_confidence(
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            preferred_proposal=preferred_proposal,
            expected_impact=expected_impact,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            operation_execution_signal=operation_execution_signal,
        )
        explanation = _build_decision_explanation(
            macro_state=macro_state,
            recommendation=recommendation,
            expected_impact=expected_impact,
            confidence=confidence,
            preferred_proposal=preferred_proposal,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            operation_execution_signal=operation_execution_signal,
        )
        tracking_payload = _build_decision_tracking_payload(
            preferred_proposal=preferred_proposal,
            recommendation=recommendation,
            expected_impact=expected_impact,
            score=score,
            confidence=confidence,
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            operation_execution_signal=operation_execution_signal,
            execution_gate=execution_gate,
        )

        return {
            "portfolio_scope": portfolio_scope,
            "recommendation_context": recommendation_context,
            "strategy_bias": strategy_bias,
            "parking_signal": parking_signal,
            "market_history_signal": market_history_signal,
            "operation_execution_signal": operation_execution_signal,
            "execution_gate": execution_gate,
            "action_suggestions": action_suggestions,
            "macro_state": macro_state,
            "portfolio_state": portfolio_state,
            "recommendation": recommendation,
            "suggested_assets": suggested_assets,
            "preferred_proposal": preferred_proposal,
            "expected_impact": expected_impact,
            "score": score,
            "confidence": confidence,
            "explanation": explanation,
            "tracking_payload": tracking_payload,
        }

    return _get_cached_selector_result(cache_key, build)


def get_planeacion_incremental_context(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    history_limit: int = 5,
) -> Dict:
    """Concentra el contrato incremental consumido por Planeacion en una sola fachada."""
    portfolio_scope_summary = _build_portfolio_scope_summary()
    monthly_allocation_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_asset_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    incremental_portfolio_simulation = get_incremental_portfolio_simulation(capital_amount=capital_amount)
    incremental_portfolio_simulation_comparison = _ensure_incremental_comparator_display_summary(
        get_incremental_portfolio_simulation_comparison(query_params, capital_amount=capital_amount),
        lead_label="Mejor balance actual",
    )
    candidate_incremental_portfolio_comparison = _ensure_incremental_comparator_display_summary(
        get_candidate_incremental_portfolio_comparison(
            query_params,
            capital_amount=capital_amount,
        ),
        lead_label="Mejor candidato actual",
    )
    candidate_split_incremental_portfolio_comparison = _ensure_incremental_comparator_display_summary(
        get_candidate_split_incremental_portfolio_comparison(
            query_params,
            capital_amount=capital_amount,
        ),
        lead_label="Mejor construccion actual",
    )
    manual_incremental_portfolio_simulation_comparison = _ensure_incremental_comparator_display_summary(
        get_manual_incremental_portfolio_simulation_comparison(
            query_params,
            default_capital_amount=capital_amount,
        ),
        lead_label="Mejor balance manual",
    )
    comparator_form_state = {
        "general_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"comparison_readiness_filter"},
        ),
        "general_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"comparison_readiness_filter"},
        ),
        "candidate_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"candidate_compare", "candidate_compare_block", "candidate_compare_readiness_filter"},
        ),
        "candidate_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"candidate_compare", "candidate_compare_block", "candidate_compare_readiness_filter"},
        ),
        "split_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={"candidate_split_compare", "candidate_split_block", "candidate_split_readiness_filter"},
        ),
        "split_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={"candidate_split_compare", "candidate_split_block", "candidate_split_readiness_filter"},
        ),
        "manual_hidden_inputs": _build_incremental_comparator_hidden_inputs(
            query_params,
            exclude_keys={
                "manual_compare",
                "manual_compare_readiness_filter",
                "plan_a_capital",
                "plan_a_execution_order_label",
                "plan_a_execution_order_summary",
                "plan_b_capital",
                "plan_b_execution_order_label",
                "plan_b_execution_order_summary",
                "plan_a_symbol_1",
                "plan_a_amount_1",
                "plan_a_symbol_2",
                "plan_a_amount_2",
                "plan_a_symbol_3",
                "plan_a_amount_3",
                "plan_b_symbol_1",
                "plan_b_amount_1",
                "plan_b_symbol_2",
                "plan_b_amount_2",
                "plan_b_symbol_3",
                "plan_b_amount_3",
            },
        ),
        "manual_reset_url": _build_planeacion_aportes_reset_url(
            query_params,
            exclude_keys={
                "manual_compare",
                "manual_compare_readiness_filter",
                "plan_a_capital",
                "plan_a_execution_order_label",
                "plan_a_execution_order_summary",
                "plan_b_capital",
                "plan_b_execution_order_label",
                "plan_b_execution_order_summary",
                "plan_a_symbol_1",
                "plan_a_amount_1",
                "plan_a_symbol_2",
                "plan_a_amount_2",
                "plan_a_symbol_3",
                "plan_a_amount_3",
                "plan_b_symbol_1",
                "plan_b_amount_1",
                "plan_b_symbol_2",
                "plan_b_amount_2",
                "plan_b_symbol_3",
                "plan_b_amount_3",
            },
        ),
    }
    incremental_comparator_activity_summary = _build_incremental_comparator_activity_summary(
        auto=incremental_portfolio_simulation_comparison,
        candidate=candidate_incremental_portfolio_comparison,
        split=candidate_split_incremental_portfolio_comparison,
        manual=manual_incremental_portfolio_simulation_comparison,
    )
    preferred_incremental_portfolio_proposal = get_preferred_incremental_portfolio_proposal(
        query_params,
        capital_amount=capital_amount,
    )
    operation_execution_feature = get_operation_execution_feature_context(
        purchase_plan=((preferred_incremental_portfolio_proposal.get("preferred") or {}).get("purchase_plan") or []),
        lookback_days=180,
        symbol_limit=3,
    )
    decision_engine_summary = get_decision_engine_summary(
        user,
        query_params=query_params,
        capital_amount=capital_amount,
    )
    incremental_backlog_prioritization = get_incremental_backlog_prioritization(
        user=user,
        limit=history_limit,
        followup_filter=_query_param_value(query_params, "backlog_followup_filter"),
    )
    incremental_reactivation_summary = get_incremental_reactivation_summary(
        user=user,
        limit=min(history_limit, 3),
    )
    incremental_reactivation_vs_backlog_summary = _build_incremental_reactivation_vs_backlog_summary(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
    )
    incremental_proposal_history = get_incremental_proposal_history(
        user=user,
        limit=history_limit,
        decision_status=_query_param_value(query_params, "decision_status_filter"),
        priority_filter=_query_param_value(query_params, "history_priority_filter"),
        deferred_fit_filter=_query_param_value(query_params, "history_deferred_fit_filter"),
        future_purchase_source_filter=_query_param_value(query_params, "history_future_purchase_source_filter"),
        sort_mode=_query_param_value(query_params, "history_sort"),
        preferred_source=incremental_reactivation_vs_backlog_summary.get("preferred_source"),
        reactivated_snapshot_ids=[
            item.get("snapshot_id")
            for item in list(incremental_reactivation_summary.get("items") or [])
            if item.get("snapshot_id") is not None
        ],
    )
    incremental_proposal_tracking_baseline = get_incremental_proposal_tracking_baseline(user=user)
    incremental_manual_decision_summary = get_incremental_manual_decision_summary(user=user)
    incremental_future_purchase_shortlist = _build_incremental_future_purchase_shortlist(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
        incremental_reactivation_vs_backlog_summary,
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        limit=3,
    )
    incremental_future_purchase_source_guidance = _build_incremental_future_purchase_source_guidance(
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        incremental_future_purchase_shortlist,
        incremental_backlog_prioritization,
        incremental_reactivation_summary,
    )
    incremental_future_purchase_shortlist, incremental_proposal_history = _annotate_incremental_future_purchase_recommended_items(
        incremental_future_purchase_shortlist,
        incremental_proposal_history,
        incremental_future_purchase_source_guidance,
    )
    incremental_future_purchase_workflow_summary = _build_incremental_future_purchase_workflow_summary(
        incremental_future_purchase_shortlist,
        incremental_future_purchase_source_guidance,
    )
    incremental_decision_executive_summary = get_incremental_decision_executive_summary(
        query_params,
        user=user,
        capital_amount=capital_amount,
        limit=history_limit,
    )

    return {
        "portfolio_scope_summary": portfolio_scope_summary,
        "monthly_allocation_plan": monthly_allocation_plan,
        "candidate_asset_ranking": candidate_asset_ranking,
        "incremental_portfolio_simulation": incremental_portfolio_simulation,
        "incremental_portfolio_simulation_comparison": incremental_portfolio_simulation_comparison,
        "candidate_incremental_portfolio_comparison": candidate_incremental_portfolio_comparison,
        "candidate_split_incremental_portfolio_comparison": candidate_split_incremental_portfolio_comparison,
        "manual_incremental_portfolio_simulation_comparison": manual_incremental_portfolio_simulation_comparison,
        "incremental_comparator_form_state": comparator_form_state,
        "incremental_comparator_activity_summary": incremental_comparator_activity_summary,
        "preferred_incremental_portfolio_proposal": preferred_incremental_portfolio_proposal,
        "operation_execution_feature": operation_execution_feature,
        "decision_engine_summary": decision_engine_summary,
        "incremental_proposal_history": incremental_proposal_history,
        "incremental_proposal_tracking_baseline": incremental_proposal_tracking_baseline,
        "incremental_backlog_prioritization": incremental_backlog_prioritization,
        "incremental_manual_decision_summary": incremental_manual_decision_summary,
        "incremental_reactivation_summary": incremental_reactivation_summary,
        "incremental_reactivation_vs_backlog_summary": incremental_reactivation_vs_backlog_summary,
        "incremental_future_purchase_shortlist": incremental_future_purchase_shortlist,
        "incremental_future_purchase_source_guidance": incremental_future_purchase_source_guidance,
        "incremental_future_purchase_workflow_summary": incremental_future_purchase_workflow_summary,
        "incremental_decision_executive_summary": incremental_decision_executive_summary,
    }
