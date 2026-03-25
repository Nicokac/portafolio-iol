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
from apps.dashboard.incremental_followup import (
    _build_incremental_adoption_check_item,
    _build_incremental_adoption_checklist_headline,
    _build_incremental_baseline_drift_alerts,
    _build_incremental_baseline_drift_explanation,
    _build_incremental_baseline_drift_summary,
    _build_incremental_followup_headline,
    _build_incremental_followup_summary_items,
    _build_incremental_snapshot_comparison,
    _build_incremental_snapshot_reapply_payload,
    _format_incremental_followup_status,
    _format_incremental_purchase_plan_summary,
    _summarize_incremental_drift_alerts,
)
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_front_summary_headline,
    _build_incremental_backlog_front_summary_items,
    _build_incremental_backlog_next_action,
    _build_incremental_backlog_prioritization_explanation,
    _build_incremental_backlog_prioritization_headline,
    _build_incremental_decision_executive_headline,
    _build_incremental_decision_executive_items,
    _build_incremental_history_available_filters,
    _build_incremental_history_headline,
    _build_incremental_manual_decision_headline,
    _build_incremental_operational_semaphore_headline,
    _build_incremental_operational_semaphore_items,
    _build_incremental_pending_backlog_explanation,
    _build_incremental_pending_backlog_headline,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
    _format_incremental_history_decision_filter_label,
    _format_incremental_history_deferred_fit_filter_label,
    _format_incremental_history_priority_filter_label,
    _format_incremental_history_sort_mode_label,
    _format_incremental_future_purchase_source_filter_label,
    _format_incremental_manual_decision_status,
    _format_incremental_operational_semaphore,
    _incremental_backlog_priority_order,
    _normalize_incremental_future_purchase_source_filter,
    _normalize_incremental_history_decision_filter,
    _normalize_incremental_history_deferred_fit_filter,
    _normalize_incremental_history_priority_filter,
    _normalize_incremental_history_sort_mode,
)
from apps.dashboard.incremental_future_purchases import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_backlog_conviction,
    _build_incremental_backlog_deferred_review_summary,
    _build_incremental_backlog_focus_item,
    _build_incremental_backlog_followup,
    _build_incremental_backlog_followup_filter_options,
    _build_incremental_backlog_manual_review_summary,
    _build_incremental_backlog_shortlist_item,
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_counts,
    _build_incremental_future_purchase_source_filter_options,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_source_quality_item,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_history_baseline_trace,
    _build_incremental_history_deferred_fit,
    _build_incremental_history_deferred_fit_counts,
    _build_incremental_history_deferred_fit_filter_options,
    _build_incremental_history_priority,
    _build_incremental_history_priority_counts,
    _build_incremental_history_priority_filter_options,
    _build_incremental_history_sort_options,
    _build_incremental_reactivation_vs_backlog_summary,
    _build_incremental_tactical_trace,
    _format_incremental_backlog_followup_filter_label,
    _is_incremental_history_tactical_clean,
    _normalize_incremental_backlog_followup_filter,
    _sort_incremental_history_items,
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


def get_incremental_proposal_history(
    *,
    user,
    limit: int = 5,
    decision_status: str | None = None,
    priority_filter: str | None = None,
    deferred_fit_filter: str | None = None,
    future_purchase_source_filter: str | None = None,
    sort_mode: str | None = None,
    preferred_source: str | None = None,
    reactivated_snapshot_ids: list[int] | set[int] | tuple[int, ...] | None = None,
) -> Dict:
    """Retorna historial reciente de propuestas incrementales guardadas por el usuario."""

    service = IncrementalProposalHistoryService()
    normalized_filter = _normalize_incremental_history_decision_filter(decision_status)
    normalized_priority_filter = _normalize_incremental_history_priority_filter(priority_filter)
    normalized_deferred_fit_filter = _normalize_incremental_history_deferred_fit_filter(deferred_fit_filter)
    normalized_future_purchase_source_filter = _normalize_incremental_future_purchase_source_filter(
        future_purchase_source_filter
    )
    normalized_sort_mode = _normalize_incremental_history_sort_mode(sort_mode)
    fetch_limit = max(int(limit), getattr(service, "MAX_SNAPSHOTS_PER_USER", 10))
    raw_items = service.list_recent(user=user, limit=fetch_limit, decision_status=normalized_filter)
    counts = service.get_decision_counts(user=user)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    baseline_item = baseline_payload.get("item")
    normalized_reactivated_snapshot_ids = {
        int(snapshot_id)
        for snapshot_id in list(reactivated_snapshot_ids or [])
        if str(snapshot_id).strip()
    }
    items = []
    for item in raw_items:
        reapply = _build_incremental_snapshot_reapply_payload(item)
        enriched = service.normalize_serialized_snapshot(item)
        enriched["manual_decision_status_label"] = _format_incremental_manual_decision_status(
            str(item.get("manual_decision_status") or "pending")
        )
        enriched["is_backlog_front_label"] = "Al frente del backlog" if item.get("is_backlog_front") else ""
        enriched["tactical_trace"] = _build_incremental_tactical_trace(item)
        enriched["baseline_trace"] = _build_incremental_history_baseline_trace(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["history_priority"] = _build_incremental_history_priority(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["deferred_fit"] = _build_incremental_history_deferred_fit(enriched)
        enriched["future_purchase_context"] = _build_incremental_future_purchase_history_context(
            enriched,
            reactivated_snapshot_ids=normalized_reactivated_snapshot_ids,
        )
        enriched.update(reapply)
        items.append(enriched)

    priority_counts = _build_incremental_history_priority_counts(items)
    deferred_fit_counts = _build_incremental_history_deferred_fit_counts(items)
    future_purchase_source_counts = _build_incremental_future_purchase_source_counts(items)
    if normalized_priority_filter:
        items = [
            item for item in items
            if str((item.get("history_priority") or {}).get("priority") or "") == normalized_priority_filter
        ]
    if normalized_deferred_fit_filter:
        items = [
            item for item in items
            if str((item.get("deferred_fit") or {}).get("status") or "") == normalized_deferred_fit_filter
        ]
    if normalized_future_purchase_source_filter:
        items = [
            item for item in items
            if str((item.get("future_purchase_context") or {}).get("source") or "") == normalized_future_purchase_source_filter
        ]

    items = _sort_incremental_history_items(
        items,
        sort_mode=normalized_sort_mode,
        preferred_source=preferred_source,
    )
    items = items[: max(int(limit), 0)]
    future_purchase_source_summary = _build_incremental_future_purchase_source_summary(
        future_purchase_source_counts,
        active_filter=normalized_future_purchase_source_filter,
    )
    future_purchase_source_quality_summary = _build_incremental_future_purchase_source_quality_summary(items)

    return {
        "items": items,
        "count": len(items),
        "has_history": bool(items),
        "active_filter": normalized_filter or "all",
        "active_filter_label": _format_incremental_history_decision_filter_label(normalized_filter),
        "active_priority_filter": normalized_priority_filter or "all",
        "active_priority_filter_label": _format_incremental_history_priority_filter_label(normalized_priority_filter),
        "active_deferred_fit_filter": normalized_deferred_fit_filter or "all",
        "active_deferred_fit_filter_label": _format_incremental_history_deferred_fit_filter_label(
            normalized_deferred_fit_filter
        ),
        "active_future_purchase_source_filter": normalized_future_purchase_source_filter or "all",
        "active_future_purchase_source_filter_label": _format_incremental_future_purchase_source_filter_label(
            normalized_future_purchase_source_filter
        ),
        "active_sort_mode": normalized_sort_mode,
        "active_sort_mode_label": _format_incremental_history_sort_mode_label(normalized_sort_mode),
        "decision_counts": counts,
        "available_filters": _build_incremental_history_available_filters(normalized_filter, counts),
        "available_priority_filters": _build_incremental_history_priority_filter_options(
            normalized_priority_filter,
            priority_counts,
        ),
        "available_deferred_fit_filters": _build_incremental_history_deferred_fit_filter_options(
            normalized_deferred_fit_filter,
            deferred_fit_counts,
        ),
        "available_future_purchase_source_filters": _build_incremental_future_purchase_source_filter_options(
            normalized_future_purchase_source_filter,
            future_purchase_source_counts,
        ),
        "available_sort_modes": _build_incremental_history_sort_options(normalized_sort_mode),
        "priority_counts": priority_counts,
        "deferred_fit_counts": deferred_fit_counts,
        "future_purchase_source_counts": future_purchase_source_counts,
        "future_purchase_source_summary": future_purchase_source_summary,
        "future_purchase_source_quality_summary": future_purchase_source_quality_summary,
        "headline": _build_incremental_history_headline(
            normalized_filter,
            counts,
            len(items),
            priority_filter=normalized_priority_filter,
            deferred_fit_filter=normalized_deferred_fit_filter,
            future_purchase_source_filter=normalized_future_purchase_source_filter,
            sort_mode=normalized_sort_mode,
        ),
    }


def get_incremental_baseline_drift(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara el baseline incremental activo contra la propuesta preferida actual."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)

    baseline = baseline_payload.get("item")
    current_preferred = preferred_payload.get("preferred")
    comparison = None
    if baseline and current_preferred:
        comparison = _build_incremental_snapshot_comparison(baseline, current_preferred)

    summary = _build_incremental_baseline_drift_summary(comparison)
    alerts = _build_incremental_baseline_drift_alerts(baseline, current_preferred, summary)
    return {
        "baseline": baseline,
        "current_preferred": current_preferred,
        "comparison": comparison,
        "summary": summary,
        "alerts": alerts,
        "alerts_count": len(alerts),
        "has_alerts": bool(alerts),
        "has_drift": comparison is not None,
        "has_baseline": baseline is not None,
        "explanation": _build_incremental_baseline_drift_explanation(baseline, current_preferred, comparison, summary),
    }


def get_incremental_pending_backlog_vs_baseline(*, user, limit: int = 5) -> Dict:
    """Compara el backlog pendiente de snapshots contra el baseline incremental activo."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    pending_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="pending")

    baseline = baseline_payload.get("item")
    pending_items = list(pending_history.get("items") or [])
    comparisons = []
    for item in pending_items:
        comparison = _build_incremental_snapshot_comparison(baseline, item) if baseline else None
        summary = _build_incremental_baseline_drift_summary(comparison)
        baseline_trace = dict(item.get("baseline_trace") or {})
        tactical_trace = dict(item.get("tactical_trace") or {})
        comparison_metrics = {metric.get("key"): metric for metric in (comparison or {}).get("metrics", [])}
        expected_direction = str((comparison_metrics.get("expected_return_change") or {}).get("direction") or "neutral")
        fragility_direction = str((comparison_metrics.get("fragility_change") or {}).get("direction") or "neutral")
        scenario_direction = str((comparison_metrics.get("scenario_loss_change") or {}).get("direction") or "neutral")
        tactical_clean = bool(
            not tactical_trace.get("has_trace")
            or any(str(badge.get("label") or "").strip() == "Alternativa promovida" for badge in tactical_trace.get("badges", []))
        )
        improves_profitability = expected_direction == "favorable"
        protects_fragility = fragility_direction != "unfavorable"
        comparisons.append(
            {
                "snapshot": item,
                "comparison": comparison,
                "summary": summary,
                "status_label": _format_incremental_followup_status(summary.get("status", "unavailable")),
                "score_difference": None if comparison is None else comparison.get("score_difference"),
                "beats_baseline": bool(comparison and comparison.get("winner") == "current"),
                "loses_vs_baseline": bool(comparison and comparison.get("winner") == "saved"),
                "ties_baseline": bool(comparison and comparison.get("winner") == "tie"),
                "improves_profitability": improves_profitability,
                "protects_fragility": protects_fragility,
                "tactical_clean": tactical_clean,
                "comparison_fit": {
                    "expected_direction": expected_direction,
                    "fragility_direction": fragility_direction,
                    "scenario_direction": scenario_direction,
                    "improves_profitability": improves_profitability,
                    "protects_fragility": protects_fragility,
                    "tactical_clean": tactical_clean,
                    "baseline_headline": baseline_trace.get("headline") or "",
                },
            }
        )

    better_count = sum(1 for item in comparisons if item["beats_baseline"])
    worse_count = sum(1 for item in comparisons if item["loses_vs_baseline"])
    tie_count = sum(1 for item in comparisons if item["ties_baseline"])
    comparable_items = [item for item in comparisons if item.get("comparison")]
    best_candidate = None
    if comparable_items:
        best_candidate = sorted(
            comparable_items,
            key=lambda item: (
                1 if item.get("improves_profitability") else 0,
                1 if item.get("protects_fragility") else 0,
                1 if item.get("tactical_clean") else 0,
                1 if item["beats_baseline"] else 0,
                1 if item["ties_baseline"] else 0,
                item.get("score_difference") if item.get("score_difference") is not None else float("-inf"),
            ),
            reverse=True,
        )[0]

    return {
        "baseline": baseline,
        "items": comparisons,
        "count": len(comparisons),
        "pending_count": pending_history.get("decision_counts", {}).get("pending", len(comparisons)),
        "decision_counts": dict(pending_history.get("decision_counts", {})),
        "has_baseline": baseline is not None,
        "has_pending_backlog": bool(pending_items),
        "has_comparable_items": bool(comparable_items),
        "better_count": better_count,
        "worse_count": worse_count,
        "tie_count": tie_count,
        "best_candidate": best_candidate,
        "headline": _build_incremental_pending_backlog_headline(baseline, pending_history, better_count, worse_count, tie_count),
        "explanation": _build_incremental_pending_backlog_explanation(baseline, pending_history, best_candidate, better_count, worse_count),
    }


def get_incremental_backlog_prioritization(*, user, limit: int = 5, followup_filter: str | None = None) -> Dict:
    """Ordena el backlog pendiente en prioridades operativas explicitas."""

    backlog_payload = get_incremental_pending_backlog_vs_baseline(user=user, limit=limit)
    deferred_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="deferred")
    items = []
    for item in backlog_payload.get("items", []):
        priority = _classify_incremental_backlog_priority(item)
        enriched = dict(item)
        enriched["priority"] = priority
        enriched["priority_label"] = _format_incremental_backlog_priority(priority)
        enriched["next_action"] = _build_incremental_backlog_next_action(priority, item)
        items.append(enriched)

    ordered_items = sorted(
        items,
        key=lambda item: (
            0 if item["snapshot"].get("is_backlog_front") else 1,
            _incremental_backlog_priority_order(item["priority"]),
            -(item.get("score_difference") if item.get("score_difference") is not None else float("-inf")),
            item["snapshot"].get("proposal_label") or "",
        ),
    )

    counts = {
        "high": sum(1 for item in ordered_items if item["priority"] == "high"),
        "medium": sum(1 for item in ordered_items if item["priority"] == "medium"),
        "watch": sum(1 for item in ordered_items if item["priority"] == "watch"),
        "low": sum(1 for item in ordered_items if item["priority"] == "low"),
    }
    decision_counts = dict(backlog_payload.get("decision_counts", {}))
    top_item = ordered_items[0] if ordered_items else None
    economic_leader = next(
        (
            item
            for item in ordered_items
            if item.get("improves_profitability") and item.get("protects_fragility")
        ),
        None,
    )
    tactical_leader = next(
        (
            item
            for item in ordered_items
            if item.get("tactical_clean")
        ),
        None,
    )
    normalized_followup_filter = _normalize_incremental_backlog_followup_filter(followup_filter)
    shortlist_items = [
        _build_incremental_backlog_shortlist_item(index=index + 1, item=item)
        for index, item in enumerate(ordered_items)
    ]
    followup_counts = {
        "review_now": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "review_now"),
        "monitor": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "monitor"),
        "hold": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "hold"),
    }
    if normalized_followup_filter:
        shortlist_items = [
            item for item in shortlist_items if str((item.get("followup") or {}).get("status") or "") == normalized_followup_filter
        ]
    shortlist = shortlist_items[:3]

    return {
        "baseline": backlog_payload.get("baseline"),
        "items": ordered_items,
        "count": len(ordered_items),
        "counts": counts,
        "manual_review_summary": _build_incremental_backlog_manual_review_summary(decision_counts),
        "deferred_review_summary": _build_incremental_backlog_deferred_review_summary(
            list(deferred_history.get("items") or []),
            decision_counts,
        ),
        "top_item": top_item,
        "economic_leader": _build_incremental_backlog_focus_item(economic_leader, focus="economic"),
        "tactical_leader": _build_incremental_backlog_focus_item(tactical_leader, focus="tactical"),
        "has_focus_split": bool(economic_leader or tactical_leader),
        "active_followup_filter": normalized_followup_filter or "all",
        "active_followup_filter_label": _format_incremental_backlog_followup_filter_label(normalized_followup_filter),
        "available_followup_filters": _build_incremental_backlog_followup_filter_options(
            normalized_followup_filter,
            followup_counts,
        ),
        "followup_counts": followup_counts,
        "shortlist": shortlist,
        "has_shortlist": bool(shortlist),
        "has_priorities": bool(ordered_items),
        "headline": _build_incremental_backlog_prioritization_headline(backlog_payload, counts, top_item),
        "explanation": _build_incremental_backlog_prioritization_explanation(backlog_payload, counts, top_item),
    }


def get_incremental_backlog_front_summary(*, user, limit: int = 5) -> Dict:
    """Resume en una sola lectura el baseline activo y el frente operativo del backlog."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    prioritization_payload = get_incremental_backlog_prioritization(user=user, limit=limit)

    baseline = baseline_payload.get("item")
    front_item = prioritization_payload.get("top_item")
    if baseline is None and front_item is None:
        status = "empty"
    elif baseline is None:
        status = "no_baseline"
    elif front_item is None:
        status = "baseline_only"
    elif front_item.get("snapshot", {}).get("is_backlog_front"):
        status = "manual_front"
    elif front_item.get("priority") == "high":
        status = "candidate_over_baseline"
    elif front_item.get("priority") == "medium":
        status = "watch"
    else:
        status = "baseline_holds"

    return {
        "status": status,
        "baseline": baseline,
        "front_item": front_item,
        "counts": prioritization_payload.get("counts", {}),
        "has_summary": bool(baseline or front_item),
        "headline": _build_incremental_backlog_front_summary_headline(status, baseline, front_item),
        "items": _build_incremental_backlog_front_summary_items(baseline, front_item, prioritization_payload),
    }


def get_incremental_backlog_operational_semaphore(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Clasifica el estado operativo incremental en semaforo reutilizando baseline, drift y backlog."""

    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)
    prioritization = get_incremental_backlog_prioritization(user=user, limit=limit)

    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    front_status = front_summary.get("status", "empty")
    high_count = int(prioritization.get("counts", {}).get("high", 0))

    if drift_status == "unfavorable":
        status = "red"
    elif front_status == "candidate_over_baseline" or high_count > 0:
        status = "yellow"
    elif front_status == "manual_front":
        status = "yellow"
    elif drift_status in {"favorable", "stable"} and front_status in {"baseline_only", "empty"}:
        status = "green"
    else:
        status = "gray"

    return {
        "status": status,
        "label": _format_incremental_operational_semaphore(status),
        "headline": _build_incremental_operational_semaphore_headline(status, front_summary, drift_payload),
        "items": _build_incremental_operational_semaphore_items(drift_payload, front_summary, prioritization),
        "has_signal": bool(drift_payload.get("has_baseline") or front_summary.get("has_summary")),
    }


def get_incremental_decision_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Consolida la lectura ejecutiva de decision incremental en una sola sintesis."""

    semaphore = get_incremental_backlog_operational_semaphore(
        query_params,
        user=user,
        capital_amount=capital_amount,
        limit=limit,
    )
    followup = get_incremental_followup_executive_summary(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    checklist = get_incremental_adoption_checklist(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)

    semaphore_status = semaphore.get("status", "gray")
    checklist_status = checklist.get("status", "pending")
    if checklist_status == "ready" and semaphore_status == "green":
        status = "adopt"
    elif semaphore_status == "red":
        status = "hold"
    elif semaphore_status == "yellow":
        status = "review_backlog"
    elif checklist_status == "review":
        status = "review_current"
    else:
        status = "pending"

    return {
        "status": status,
        "headline": _build_incremental_decision_executive_headline(status, semaphore, followup, checklist, front_summary),
        "items": _build_incremental_decision_executive_items(semaphore, followup, checklist, front_summary),
        "has_summary": bool(
            semaphore.get("has_signal")
            or followup.get("has_summary")
            or checklist.get("total_count")
            or front_summary.get("has_summary")
        ),
    }


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


def get_incremental_followup_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza una lectura ejecutiva de seguimiento incremental para Planeacion."""

    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)

    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")

    if preferred is None:
        status = "pending"
    elif baseline is None:
        status = "no_baseline"
    elif drift_status == "unfavorable":
        status = "review"
    elif drift_status == "mixed":
        status = "watch"
    elif drift_status in {"favorable", "stable"}:
        status = "aligned"
    else:
        status = "watch"

    headline = _build_incremental_followup_headline(status, preferred, baseline)
    summary_items = _build_incremental_followup_summary_items(preferred, baseline, drift_payload)
    return {
        "status": status,
        "headline": headline,
        "summary_items": summary_items,
        "preferred": preferred,
        "baseline": baseline,
        "drift": drift_payload,
        "has_preferred": preferred is not None,
        "has_baseline": baseline is not None,
        "has_summary": bool(preferred or baseline),
    }


def get_incremental_adoption_checklist(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Construye un checklist operativo para decidir adopcion de la propuesta incremental actual."""

    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    executive_payload = get_incremental_followup_executive_summary(query_params, user=user, capital_amount=capital_amount)

    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    drift_alerts = list(drift_payload.get("alerts") or [])

    items = [
        _build_incremental_adoption_check_item(
            key="preferred_available",
            label="Existe propuesta incremental preferida",
            passed=preferred is not None,
            detail=preferred.get("proposal_label") if preferred else "Todavia no hay propuesta incremental construible.",
        ),
        _build_incremental_adoption_check_item(
            key="purchase_plan_available",
            label="La propuesta tiene compra resumida",
            passed=bool((preferred or {}).get("purchase_plan")),
            detail=_format_incremental_purchase_plan_summary((preferred or {}).get("purchase_plan") or []),
        ),
        _build_incremental_adoption_check_item(
            key="baseline_defined",
            label="Existe baseline incremental activo",
            passed=baseline is not None,
            detail=baseline.get("proposal_label") if baseline else "Conviene fijar una referencia antes de adoptar.",
        ),
        _build_incremental_adoption_check_item(
            key="drift_not_unfavorable",
            label="El drift no es desfavorable frente al baseline",
            passed=drift_status != "unfavorable",
            detail=(
                _summarize_incremental_drift_alerts(drift_alerts)
                if drift_alerts
                else _format_incremental_followup_status(drift_status)
            ),
        ),
        _build_incremental_adoption_check_item(
            key="critical_drift_alerts",
            label="No hay alertas criticas de drift",
            passed=not any(str(alert.get("severity") or "") == "critical" for alert in drift_alerts),
            detail=_summarize_incremental_drift_alerts(drift_alerts),
        ),
    ]

    passed_count = sum(1 for item in items if item["passed"])
    adoption_ready = all(item["passed"] for item in items[:2]) and items[3]["passed"] and items[4]["passed"]
    status = "ready" if adoption_ready else "review"
    if preferred is None:
        status = "pending"

    return {
        "status": status,
        "adoption_ready": adoption_ready,
        "items": items,
        "passed_count": passed_count,
        "total_count": len(items),
        "headline": _build_incremental_adoption_checklist_headline(status, executive_payload, preferred, baseline),
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











