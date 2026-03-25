from typing import Dict, List
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from urllib.parse import urlencode
from django.core.cache import cache
from django.db.models import Max, Sum
from django.urls import reverse
from django.utils import timezone

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.selectors import build_portafolio_row
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.core.models import Alert
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.candidate_asset_ranking_service import CandidateAssetRankingService
from apps.core.services.incremental_proposal_contracts import (
    build_incremental_purchase_plan_summary,
    normalize_incremental_proposal_payload,
)
from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.core.services.monthly_allocation_service import MonthlyAllocationService
from apps.core.services.analytics_v2 import (
    AnalyticsExplanationService,
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    LocalMacroSignalsService,
    RiskContributionService,
    ScenarioCatalogService,
    ScenarioAnalysisService,
    StressCatalogService,
    StressFragilityService,
)
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
    _build_manual_incremental_execution_readiness,
    _build_manual_incremental_execution_readiness_summary,
    _coerce_optional_float,
    _compute_decision_confidence,
    _compute_decision_score,
    _manual_execution_readiness_rank,
)
from apps.dashboard.incremental_comparators import (
    _build_comparable_candidate_blocks,
    _build_incremental_comparator_activity_summary,
    _build_incremental_comparator_hidden_inputs,
    _build_incremental_comparator_summary,
    _build_incremental_readiness_filter_metadata,
    _build_incremental_readiness_filter_options,
    _build_manual_incremental_comparison_form_state,
    _build_planeacion_aportes_reset_url,
    _build_preferred_incremental_explanation,
    _build_preferred_proposal_context,
    _build_runner_up_purchase_plan,
    _build_split_largest_block_purchase_plan,
    _build_top_candidate_purchase_plan,
    _coerce_manual_amount,
    _ensure_incremental_comparator_display_summary,
    _extract_best_incremental_proposal,
    _format_incremental_readiness_filter_label,
    _normalize_incremental_proposal_item,
    _normalize_incremental_readiness_filter,
    _preferred_source_priority_rank,
    _query_param_value,
    _resolve_manual_incremental_operational_tiebreak,
    _score_incremental_simulation,
)
from apps.dashboard.incremental_future_purchases import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_reactivation_vs_backlog_summary,
    get_incremental_manual_decision_summary,
    get_incremental_proposal_tracking_baseline,
    get_incremental_reactivation_summary,
)
from apps.dashboard.analytics_v2_builders import (
    build_analytics_v2_dashboard_summary,
    build_expected_return_detail,
    build_factor_exposure_detail,
    build_risk_contribution_detail,
    build_scenario_analysis_detail,
    build_stress_fragility_detail,
    resolve_active_risk_contribution_result,
)
from apps.dashboard.operation_execution import (
    build_operation_execution_feature_context as _build_operation_execution_feature_context,
    classify_observed_operation_cost,
    classify_operation_type,
    get_effective_operation_amount,
)
from apps.dashboard.historical_rebalance import (
    build_active_alerts,
    build_evolucion_historica,
    build_portafolio_clasificado_fecha,
    build_senales_rebalanceo,
    build_snapshot_coverage_summary,
    get_objetivos_rebalanceo as _historical_get_objetivos_rebalanceo,
    mapear_sector_a_categoria as _historical_mapear_sector_a_categoria,
)
from apps.dashboard.market_signals import (
    build_market_snapshot_feature_context,
    build_market_snapshot_history_feature_context,
    build_portfolio_parking_feature_context,
)
from apps.dashboard.portfolio_distribution import (
    _aggregate_sector_labels,
    _is_technology_sector,
    _normalize_account_currency,
    build_concentracion_from_distribucion,
    build_concentracion_patrimonial,
    build_concentracion_sectorial,
    build_distribucion_moneda,
    build_distribucion_moneda_operativa,
    build_distribucion_pais,
    build_distribucion_sector,
    build_distribucion_tipo_patrimonial,
    build_resumen_cash_distribution_by_country,
)
from apps.dashboard.portfolio_risk import (
    build_riesgo_portafolio,
    build_riesgo_portafolio_detallado,
)
from apps.dashboard.portfolio_analytics import build_analytics_mensual
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
    build_portafolio_enriquecido,
    build_dashboard_kpis as _build_dashboard_kpis,
    extract_resumen_cash_components,
    build_liquidity_contract_summary,
    build_portfolio_scope_summary,
)
from apps.dashboard.selector_cache import (
    _get_cached_selector_result,
    _safe_percentage,
)


def get_latest_portafolio_data() -> List[ActivoPortafolioSnapshot]:
    """Obtiene los datos mÃƒÆ’Ã‚Â¡s recientes del portafolio."""
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_latest_resumen_data() -> List[ResumenCuentaSnapshot]:
    """Obtiene los datos mÃƒÆ’Ã‚Â¡s recientes del resumen de cuenta."""
    latest_date = ResumenCuentaSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_market_snapshot_feature_context(*, top_limit: int = 5) -> Dict:
    payload = IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot() or {}
    cached_rows = payload.get("rows") or []
    summary = payload.get("summary") or IOLHistoricalPriceService.summarize_market_snapshot_rows(cached_rows)
    refreshed_at_label = IOLHistoricalPriceService._format_snapshot_datetime(payload.get("refreshed_at"))

    return build_market_snapshot_feature_context(
        payload={
            **payload,
            "_has_cached_snapshot": bool(payload),
            "summary": summary,
            "refreshed_at_label": refreshed_at_label,
        },
        relevant_positions=get_portafolio_enriquecido_actual()["inversion"],
        top_limit=top_limit,
    )

def get_market_snapshot_history_feature_context(*, top_limit: int = 5, lookback_days: int = 7) -> Dict:
    def build():
        service = IOLHistoricalPriceService()
        history_rows = service.get_recent_market_history_rows(lookback_days=lookback_days)
        summary = service.summarize_recent_market_history_rows(history_rows)
        return build_market_snapshot_history_feature_context(
            history_rows=history_rows,
            summary=summary,
            current_portafolio=get_portafolio_enriquecido_actual(),
            top_limit=top_limit,
            lookback_days=lookback_days,
        )

    return _get_cached_selector_result(f"market_snapshot_history_feature:{int(lookback_days)}", build)

def get_portfolio_parking_feature_context(*, top_limit: int = 5) -> Dict:
    def build():
        return build_portfolio_parking_feature_context(
            portafolio=get_portafolio_enriquecido_actual(),
            top_limit=top_limit,
            safe_percentage=_safe_percentage,
        )

    return _get_cached_selector_result("portfolio_parking_feature", build)

def get_portafolio_enriquecido_actual() -> Dict[str, List[Dict]]:
    """Obtiene el portafolio actual enriquecido con metadata, separado en liquidez e inversion."""
    def build():
        portafolio = get_latest_portafolio_data()
        simbolos = [activo.simbolo for activo in portafolio]
        parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
        return build_portafolio_enriquecido(portafolio, parametros)

    return _get_cached_selector_result("portafolio_enriquecido_actual", build)


def _get_activos_invertidos() -> List[Dict]:

    return get_portafolio_enriquecido_actual()['inversion']


def _get_activos_valorizados_con_metadata() -> List[Dict]:
    portafolio = get_portafolio_enriquecido_actual()
    return portafolio['liquidez'] + portafolio['fci_cash_management'] + portafolio['inversion']



_extract_resumen_cash_components = extract_resumen_cash_components


def get_dashboard_kpis() -> Dict:
    """Calcula los KPIs principales del dashboard con metricas separadas por categoria."""
    def build():
        portafolio = get_latest_portafolio_data()
        resumen = get_latest_resumen_data()
        portafolio_clasificado = get_portafolio_enriquecido_actual()
        return _build_dashboard_kpis(portafolio, portafolio_clasificado, resumen)

    return _get_cached_selector_result("dashboard_kpis", build)


def get_macro_local_context(total_iol: float | None = None) -> Dict:
    """Obtiene contexto macro local persistido para enriquecer el analisis."""

    def build():
        return LocalMacroSeriesService().get_context_summary(total_iol=total_iol)

    total_stamp = round(float(total_iol), 2) if total_iol is not None else "none"
    return _get_cached_selector_result(f"macro_local_context:{total_stamp}", build)


def get_liquidity_contract_summary(kpis: Dict | None = None) -> Dict:
    """Normaliza el contrato de liquidez para consumidores heredados."""
    kpis = kpis or get_dashboard_kpis()
    return build_liquidity_contract_summary(kpis)


def _build_portfolio_scope_summary() -> Dict:
    """Explicita el universo broker vs capital invertido para Planeacion."""
    kpis = get_dashboard_kpis()
    resumen = get_latest_resumen_data()
    cash_components = _extract_resumen_cash_components(resumen)
    return build_portfolio_scope_summary(kpis, cash_components)


def get_distribucion_sector(base: str = 'total_activos') -> Dict[str, float]:
    return build_distribucion_sector(
        activos_invertidos=_get_activos_invertidos(),
        activos_con_metadata=_get_activos_valorizados_con_metadata(),
        base=base,
    )


def get_distribucion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    return build_distribucion_pais(
        activos_invertidos=_get_activos_invertidos(),
        activos_con_metadata=_get_activos_valorizados_con_metadata(),
        resumen_cash_by_country=build_resumen_cash_distribution_by_country(get_latest_resumen_data()),
        base=base,
    )


def get_distribucion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    return build_distribucion_tipo_patrimonial(
        activos_invertidos=_get_activos_invertidos(),
        activos_con_metadata=_get_activos_valorizados_con_metadata(),
        base=base,
    )


def get_distribucion_moneda() -> Dict[str, float]:
    return build_distribucion_moneda(
        portafolio=get_latest_portafolio_data(),
        resumen=get_latest_resumen_data(),
    )


def get_distribucion_moneda_operativa() -> Dict[str, float]:
    return build_distribucion_moneda_operativa(
        portafolio=get_latest_portafolio_data(),
        resumen=get_latest_resumen_data(),
    )


def get_concentracion_patrimonial() -> Dict[str, float]:
    return build_concentracion_patrimonial(kpis=get_dashboard_kpis())


def get_concentracion_sectorial() -> Dict[str, float]:
    return build_concentracion_sectorial(
        portafolio_inversion=get_portafolio_enriquecido_actual()['inversion']
    )


def get_concentracion_sector() -> Dict[str, float]:
    return build_concentracion_from_distribucion(get_distribucion_sector(base='portafolio_invertido'))


def get_concentracion_sector_agregado() -> Dict[str, float]:
    return build_concentracion_from_distribucion(
        _aggregate_sector_labels(get_distribucion_sector(base='portafolio_invertido'))
    )


def get_concentracion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    return build_concentracion_from_distribucion(get_distribucion_pais(base=base))


def get_concentracion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    return build_concentracion_from_distribucion(get_distribucion_tipo_patrimonial(base=base))


def get_concentracion_moneda() -> Dict[str, float]:
    return build_concentracion_from_distribucion(get_distribucion_moneda())


def get_concentracion_moneda_operativa() -> Dict[str, float]:
    return build_concentracion_from_distribucion(get_distribucion_moneda_operativa())


def get_riesgo_portafolio_detallado() -> Dict[str, float]:
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    kpis = get_dashboard_kpis()
    return build_riesgo_portafolio_detallado(
        portafolio=portafolio,
        total_portafolio=sum(activo.valorizado for activo in portafolio),
        liquidez_operativa=kpis.get('liquidez_operativa', 0),
        total_iol=kpis.get('total_iol', 0),
    )


def get_riesgo_portafolio() -> Dict[str, float]:
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    kpis = get_dashboard_kpis()
    return build_riesgo_portafolio(
        portafolio=portafolio,
        total_portafolio=sum(activo.valorizado for activo in portafolio),
        liquidez_operativa=kpis.get('liquidez_operativa', 0),
        total_iol=kpis.get('total_iol', 0),
    )

def get_analytics_mensual() -> Dict[str, float]:
    return build_analytics_mensual()

def get_portafolio_clasificado_fecha(portafolio_fecha) -> Dict[str, List[Dict]]:
    """Clasifica un portafolio historico en categorias (version simplificada para evolucion historica)."""
    return build_portafolio_clasificado_fecha(portafolio_fecha)


def get_evolucion_historica(days: int = 30, max_points: int = 14) -> Dict[str, list]:
    """Obtiene evolucion historica consolidada por dia calendario."""
    return build_evolucion_historica(days=days, max_points=max_points)


def get_objetivos_rebalanceo() -> Dict[str, Dict[str, float]]:
    """Define objetivos de asignacion por bloque patrimonial y sectorial."""
    return _historical_get_objetivos_rebalanceo()


def mapear_sector_a_categoria(sector: str) -> str:
    """Mapea sectores especificos a categorias objetivo."""
    return _historical_mapear_sector_a_categoria(sector)


def get_senales_rebalanceo() -> Dict[str, list]:
    """Genera seÃƒÂ±ales de rebalanceo basadas en objetivos definidos."""
    return build_senales_rebalanceo(
        concentracion_patrimonial=get_concentracion_patrimonial(),
        concentracion_sectorial=get_concentracion_sectorial(),
        latest_portafolio_data=get_latest_portafolio_data(),
    )


def get_snapshot_coverage_summary(days: int = 90) -> Dict[str, float | int | str | bool | None]:
    """Resume la cobertura reciente de snapshots para diagnosticar metricas temporales."""
    return build_snapshot_coverage_summary(days=days)


def get_active_alerts() -> list:
    """Obtiene todas las alertas activas ordenadas por severidad y fecha."""
    return build_active_alerts()



def get_decision_engine_summary(
    user,
    *,
    query_params=None,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compone una sintesis unica de decision mensual reutilizando selectors existentes."""

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



def _get_active_risk_contribution_result() -> Dict:
    def build():
        base_service = RiskContributionService()
        covariance_service = CovarianceAwareRiskContributionService(base_service=base_service)
        return resolve_active_risk_contribution_result(
            base_risk_service=base_service,
            covariance_risk_service=covariance_service,
        )

    return _get_cached_selector_result("analytics_v2_active_risk_contribution", build)


def get_risk_contribution_detail() -> Dict:
    """Construye el detalle server-rendered de contribucion al riesgo."""

    def build():
        return build_risk_contribution_detail(
            resolved=_get_active_risk_contribution_result(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("analytics_v2_risk_contribution_detail", build)


def get_scenario_analysis_detail() -> Dict:
    """Construye el detalle server-rendered de escenarios."""

    def build():
        return build_scenario_analysis_detail(
            scenario_service=ScenarioAnalysisService(),
            catalog_service=ScenarioCatalogService(),
        )

    return _get_cached_selector_result("analytics_v2_scenario_analysis_detail", build)


def get_factor_exposure_detail() -> Dict:
    """Construye el detalle server-rendered de exposicion factorial."""

    def build():
        return build_factor_exposure_detail(
            factor_result=FactorExposureService().calculate(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("analytics_v2_factor_exposure_detail", build)


def get_stress_fragility_detail() -> Dict:
    """Construye el detalle server-rendered de stress testing."""

    def build():
        catalog_service = StressCatalogService()
        stress_service = StressFragilityService()
        stress_rows = []
        for stress in catalog_service.list_stresses():
            result = stress_service.calculate(stress["stress_key"])
            stress_rows.append(
                {
                    "stress_key": stress.get("stress_key"),
                    "scenario_key": result.get("scenario_key") or stress.get("stress_key"),
                    "label": stress.get("label"),
                    "description": stress.get("description"),
                    "category": stress.get("category"),
                    "fragility_score": result.get("fragility_score"),
                    "total_loss_pct": float(result.get("total_loss_pct") or 0.0),
                    "total_loss_money": float(result.get("total_loss_money") or 0.0),
                    "top_sector": (result.get("vulnerable_sectors") or [{}])[0] if result.get("vulnerable_sectors") else None,
                    "top_country": (result.get("vulnerable_countries") or [{}])[0] if result.get("vulnerable_countries") else None,
                    "vulnerable_assets": result.get("vulnerable_assets", []),
                    "vulnerable_sectors": result.get("vulnerable_sectors", []),
                    "vulnerable_countries": result.get("vulnerable_countries", []),
                    "metadata": result.get("metadata", {}),
                }
            )
        return build_stress_fragility_detail(
            stress_rows=stress_rows,
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("analytics_v2_stress_fragility_detail", build)


def get_expected_return_detail() -> Dict:
    """Construye el detalle server-rendered de retorno esperado."""

    def build():
        return build_expected_return_detail(
            result=ExpectedReturnService().calculate(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("analytics_v2_expected_return_detail", build)


def get_analytics_v2_dashboard_summary() -> Dict:
    """Resume Analytics v2 para consumo server-rendered en dashboard."""

    def build():
        resolved_risk = _get_active_risk_contribution_result()
        return build_analytics_v2_dashboard_summary(
            resolved_risk=resolved_risk,
            base_risk_service=RiskContributionService(),
            scenario_service=ScenarioAnalysisService(),
            factor_service=FactorExposureService(),
            explanation_service=AnalyticsExplanationService(),
            stress_service=StressFragilityService(),
            expected_return_service=ExpectedReturnService(),
            local_macro_service=LocalMacroSignalsService(),
        )

    return _get_cached_selector_result("analytics_v2_dashboard_summary", build)











