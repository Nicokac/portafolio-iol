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
    build_operation_execution_feature_context,
    classify_observed_operation_cost,
    classify_operation_type,
    get_effective_operation_amount,
)


SELECTOR_CACHE_TTL_SECONDS = 60
DATA_STAMP_CACHE_KEY = "dashboard_selector:data_stamp"


def _safe_percentage(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"))


def _get_data_stamp() -> str:
    from apps.operaciones_iol.models import OperacionIOL

    cached = cache.get(DATA_STAMP_CACHE_KEY)
    if cached is not None:
        return cached

    latest_portafolio = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_resumen = ResumenCuentaSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_parametro_id = ParametroActivo.objects.aggregate(latest=Max("id"))["latest"] or 0
    latest_operacion = OperacionIOL.objects.aggregate(latest=Max("fecha_orden"))["latest"]
    stamp = f"{latest_portafolio}|{latest_resumen}|{latest_parametro_id}|{latest_operacion}"
    cache.set(DATA_STAMP_CACHE_KEY, stamp, timeout=SELECTOR_CACHE_TTL_SECONDS)
    return stamp


def _get_cached_selector_result(cache_key_prefix: str, builder):
    stamp = _get_data_stamp()
    stamp_hash = hashlib.md5(stamp.encode("utf-8")).hexdigest()
    cache_key = f"dashboard_selector:{cache_key_prefix}:{stamp_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    value = builder()
    cache.set(cache_key, value, timeout=SELECTOR_CACHE_TTL_SECONDS)
    return value


def get_latest_portafolio_data() -> List[ActivoPortafolioSnapshot]:
    """Obtiene los datos más recientes del portafolio."""
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_latest_resumen_data() -> List[ResumenCuentaSnapshot]:
    """Obtiene los datos más recientes del resumen de cuenta."""
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

    relevant_positions = get_portafolio_enriquecido_actual()["inversion"][: max(int(top_limit or 0), 1)]
    snapshot_rows_by_key = {
        (
            str(row.get("simbolo") or "").strip().upper(),
            str(row.get("mercado") or "").strip().upper(),
        ): row
        for row in cached_rows
    }

    top_rows = []
    for item in relevant_positions:
        activo = item["activo"]
        snapshot_row = snapshot_rows_by_key.get(
            (
                str(activo.simbolo or "").strip().upper(),
                str(activo.mercado or "").strip().upper(),
            )
        )
        snapshot_status = str((snapshot_row or {}).get("snapshot_status") or "missing")
        top_rows.append(
            {
                "simbolo": activo.simbolo,
                "mercado": activo.mercado,
                "descripcion": (snapshot_row or {}).get("descripcion") or activo.descripcion,
                "peso_porcentual": item.get("peso_porcentual") or 0,
                "valorizado": activo.valorizado,
                "snapshot_status": snapshot_status,
                "snapshot_status_label": {
                    "available": "Disponible",
                    "unsupported": "No elegible",
                    "missing": "Sin snapshot",
                }.get(snapshot_status, "Sin snapshot"),
                "snapshot_source_key": (snapshot_row or {}).get("snapshot_source_key") or "",
                "snapshot_source_label": (snapshot_row or {}).get("snapshot_source_label") or "",
                "snapshot_reason": (snapshot_row or {}).get("snapshot_reason") or "",
                "fecha_hora_label": (snapshot_row or {}).get("fecha_hora_label") or "",
                "ultimo_precio": (snapshot_row or {}).get("ultimo_precio"),
                "variacion": (snapshot_row or {}).get("variacion"),
                "cantidad_operaciones": int((snapshot_row or {}).get("cantidad_operaciones") or 0),
                "puntas_count": int((snapshot_row or {}).get("puntas_count") or 0),
                "spread_abs": (snapshot_row or {}).get("spread_abs"),
                "spread_pct": (snapshot_row or {}).get("spread_pct"),
                "plazo": (snapshot_row or {}).get("plazo") or "",
                "has_order_book": int((snapshot_row or {}).get("puntas_count") or 0) > 0,
            }
        )

    top_available_count = sum(1 for row in top_rows if row["snapshot_status"] == "available")
    top_missing_count = sum(1 for row in top_rows if row["snapshot_status"] == "missing")
    wide_spread_rows = [
        row for row in top_rows
        if row["snapshot_status"] == "available"
        and row.get("spread_pct") is not None
        and Decimal(str(row["spread_pct"])) >= Decimal("1.0")
    ]

    alerts = []
    if not payload:
        alerts.append(
            {
                "tone": "secondary",
                "title": "Snapshot puntual pendiente",
                "message": "Todavía no hay market snapshot IOL cacheado para enriquecer la lectura táctica de estas pantallas.",
            }
        )
    else:
        if top_missing_count > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Cobertura parcial en posiciones relevantes",
                    "message": f"{top_missing_count} posicion(es) relevantes siguen sin snapshot puntual disponible.",
                }
            )
        if wide_spread_rows:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Spreads anchos en posiciones relevantes",
                    "message": ", ".join(row["simbolo"] for row in wide_spread_rows[:3]),
                }
            )
        if int(summary.get("fallback_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "info",
                    "title": "Parte de la cobertura viene por fallback",
                    "message": f"{summary['fallback_count']} simbolo(s) usan Cotizacion simple en lugar de CotizacionDetalle.",
                }
            )
        if int(summary.get("order_book_count") or 0) == 0 and int(summary.get("available_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "secondary",
                    "title": "Sin libro visible",
                    "message": "Hay precios puntuales disponibles, pero sin puntas visibles para lectura de spread.",
                }
            )

    return {
        "has_cached_snapshot": bool(payload),
        "refreshed_at_label": refreshed_at_label,
        "summary": summary,
        "top_rows": top_rows,
        "top_available_count": top_available_count,
        "top_missing_count": top_missing_count,
        "wide_spread_count": len(wide_spread_rows),
        "alerts": alerts[:3],
    }


def get_market_snapshot_history_feature_context(*, top_limit: int = 5, lookback_days: int = 7) -> Dict:
    def build():
        service = IOLHistoricalPriceService()
        history_rows = service.get_recent_market_history_rows(lookback_days=lookback_days)
        summary = service.summarize_recent_market_history_rows(history_rows)

        current_portafolio = get_portafolio_enriquecido_actual()
        position_rows = current_portafolio["inversion"] + current_portafolio["fci_cash_management"]
        metadata_by_key = {
            (
                str(item["activo"].simbolo or "").strip().upper(),
                str(item["activo"].mercado or "").strip().upper(),
            ): {
                "valorizado": item["activo"].valorizado,
                "peso_porcentual": item.get("peso_porcentual") or 0,
                "bloque_estrategico": item.get("bloque_estrategico") or "N/A",
            }
            for item in position_rows
        }

        enriched_rows = []
        weak_blocks = {}
        for row in history_rows:
            metadata = metadata_by_key.get(
                (
                    str(row.get("simbolo") or "").strip().upper(),
                    str(row.get("mercado") or "").strip().upper(),
                ),
                {},
            )
            enriched_row = {
                **row,
                "valorizado": metadata.get("valorizado") or Decimal("0"),
                "peso_porcentual": metadata.get("peso_porcentual") or 0,
                "bloque_estrategico": metadata.get("bloque_estrategico") or "N/A",
            }
            enriched_rows.append(enriched_row)
            if enriched_row["quality_status"] == "weak" and enriched_row["bloque_estrategico"] != "N/A":
                weak_blocks[enriched_row["bloque_estrategico"]] = (
                    weak_blocks.get(enriched_row["bloque_estrategico"], Decimal("0")) + enriched_row["valorizado"]
                )

        severity_order = {"weak": 0, "watch": 1, "insufficient": 2, "strong": 3}
        top_rows = sorted(
            enriched_rows,
            key=lambda item: (
                severity_order.get(str(item.get("quality_status") or ""), 9),
                -(item.get("valorizado") or Decimal("0")),
                str(item.get("simbolo") or ""),
            ),
        )[: max(int(top_limit or 0), 1)]
        weak_block_rows = [
            {"label": label, "value_total": value_total}
            for label, value_total in sorted(weak_blocks.items(), key=lambda item: item[1], reverse=True)
        ]

        alerts = []
        if int(summary.get("weak_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Liquidez reciente debil en posiciones actuales",
                    "message": f"{summary['weak_count']} simbolo(s) muestran spread o actividad reciente debil para reforzar compras.",
                }
            )
        if int(summary.get("insufficient_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "secondary",
                    "title": "Historial puntual todavia corto",
                    "message": f"{summary['insufficient_count']} simbolo(s) todavia no acumulan observaciones suficientes para lectura reciente.",
                }
            )

        return {
            "lookback_days": lookback_days,
            "summary": summary,
            "rows": enriched_rows,
            "top_rows": top_rows,
            "weak_blocks": weak_block_rows,
            "alerts": alerts[:3],
            "has_history": bool(enriched_rows),
        }

    return _get_cached_selector_result(f"market_snapshot_history_feature:{int(lookback_days)}", build)


def get_portfolio_parking_feature_context(*, top_limit: int = 5) -> Dict:
    def build():
        portafolio = get_portafolio_enriquecido_actual()
        relevant_items = portafolio["inversion"] + portafolio["fci_cash_management"]
        rows = []
        parking_blocks: Dict[str, Decimal] = {}
        for item in relevant_items:
            row = build_portafolio_row(item["activo"])
            row["bloque_estrategico"] = item.get("bloque_estrategico") or "N/A"
            rows.append(row)
            if row["has_parking"]:
                block_label = str(item.get("bloque_estrategico") or "N/A")
                parking_blocks[block_label] = parking_blocks.get(block_label, Decimal("0")) + row["valorizado"]
        total_positions = len(rows)
        parking_rows = [row for row in rows if row["has_parking"]]
        parking_count = len(parking_rows)
        parking_value_total = sum((row["valorizado"] for row in parking_rows), Decimal("0"))
        top_rows = sorted(parking_rows, key=lambda row: row["valorizado"], reverse=True)[: max(int(top_limit or 0), 1)]
        parking_block_summary = [
            {"label": label, "value_total": value_total}
            for label, value_total in sorted(parking_blocks.items(), key=lambda item: item[1], reverse=True)
        ]

        alerts = []
        if parking_count > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Parking visible en posiciones actuales",
                    "message": f"{parking_count} posicion(es) del portafolio invertido siguen mostrando parking visible en IOL.",
                }
            )

        return {
            "has_visible_parking": parking_count > 0,
            "summary": {
                "total_positions": total_positions,
                "parking_count": parking_count,
                "parking_pct": _safe_percentage(parking_count, total_positions),
                "parking_value_total": parking_value_total,
            },
            "parking_blocks": parking_block_summary,
            "top_rows": top_rows,
            "alerts": alerts,
        }

    return _get_cached_selector_result("portfolio_parking_feature", build)


def get_portafolio_enriquecido_actual() -> Dict[str, List[Dict]]:
    """Obtiene el portafolio actual enriquecido con metadata, separado en liquidez e inversión."""
    def build():
        portafolio = get_latest_portafolio_data()
        simbolos = [activo.simbolo for activo in portafolio]
        parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

        # Calcular total del portafolio para pesos porcentuales
        total_portafolio = sum(activo.valorizado for activo in portafolio)

        # Traducciones de tipos
        tipo_traducciones = {
            'CEDEARS': 'CEDEAR',
            'ACCIONES': 'Acción',
            'TitulosPublicos': 'Título Público',
            'FondoComundeInversion': 'FCI',
            'CAUCIONESPESOS': 'Caución',
        }

        # Traducciones de monedas
        moneda_traducciones = {
            'peso_Argentino': 'ARS',
            'dolar_Estadounidense': 'USD',
        }

        liquidez = []
        inversion = []
        fci_cash_management = []  # Categoría intermedia para FCI de cash management

        for activo in portafolio:
            param = parametros.get(activo.simbolo)
            tipo_traducido = tipo_traducciones.get(activo.tipo, activo.tipo)
            moneda_traducida = moneda_traducciones.get(activo.moneda, activo.moneda)

            # Calcular peso porcentual
            peso_porcentual = (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0

            item = {
                'activo': activo,
                'sector': param.sector if param else 'N/A',
                'bloque_estrategico': param.bloque_estrategico if param else 'N/A',
                'pais_exposicion': param.pais_exposicion if param else 'N/A',
                'tipo_patrimonial': param.tipo_patrimonial if param else 'N/A',
                'observaciones': param.observaciones if param else '',
                'tipo_traducido': tipo_traducido,
                'moneda_traducida': moneda_traducida,
                'peso_porcentual': peso_porcentual,
            }

            # Clasificación refinada
            simbolo_upper = activo.simbolo.upper()
            if activo.tipo == 'CAUCIONESPESOS' or 'CAUCIÓN' in simbolo_upper:
                # Caución como liquidez operativa
                liquidez.append(item)
            elif simbolo_upper in ['ADBAICA', 'IOLPORA', 'PRPEDOB']:
                # FCI de cash management como categoría intermedia
                fci_cash_management.append(item)
            elif activo.tipo == 'FondoComundeInversion':
                # Otros FCI van al portafolio invertido
                inversion.append(item)
            elif activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in simbolo_upper:
                # Activos tradicionales van al portafolio invertido
                inversion.append(item)
            else:
                # Resto va al portafolio invertido por defecto
                inversion.append(item)

        # Ordenar inversión por valorizado descendente
        inversion.sort(key=lambda x: x['activo'].valorizado, reverse=True)
        fci_cash_management.sort(key=lambda x: x['activo'].valorizado, reverse=True)

        return {
            'liquidez': liquidez,
            'fci_cash_management': fci_cash_management,
            'inversion': inversion,
            'total_portafolio': total_portafolio,
        }

    return _get_cached_selector_result("portafolio_enriquecido_actual", build)


def _get_activos_invertidos() -> List[Dict]:
    return get_portafolio_enriquecido_actual()['inversion']


def _get_activos_valorizados_con_metadata() -> List[Dict]:
    portafolio = get_portafolio_enriquecido_actual()
    return portafolio['liquidez'] + portafolio['fci_cash_management'] + portafolio['inversion']


def _build_distribution_from_items(items: List[Dict], field: str) -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for item in items:
        key = item.get(field) or 'Sin clasificar'
        if field == 'pais_exposicion' and key in {'Estados Unidos', 'USA'}:
            key = 'USA'
        distribucion[key] = distribucion.get(key, 0) + float(item['activo'].valorizado)
    return distribucion


def _is_technology_sector(sector: str | None) -> bool:
    if not sector:
        return False
    normalized = str(sector).strip().lower()
    return normalized.startswith('tecnolog')




def _aggregate_sector_labels(distribucion: Dict[str, float]) -> Dict[str, float]:
    aggregated: Dict[str, float] = {}
    for sector, valor in distribucion.items():
        label = 'Tecnologia Total' if _is_technology_sector(sector) else sector
        aggregated[label] = aggregated.get(label, 0) + float(valor)
    return aggregated


def _get_resumen_cash_distribution_by_country() -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for cuenta in get_latest_resumen_data():
        monto = float(cuenta.disponible)
        if monto <= 0:
            continue
        pais = 'USA' if _normalize_account_currency(cuenta.moneda) == 'USD' else 'Argentina'
        distribucion[pais] = distribucion.get(pais, 0) + monto
    return distribucion


def _normalize_account_currency(moneda: str | None) -> str:
    normalized = str(moneda or '').strip()
    mapping = {
        'ARS': 'ARS',
        'peso_Argentino': 'ARS',
        'USD': 'USD',
        'dolar_Estadounidense': 'USD',
    }
    return mapping.get(normalized, normalized)


def _extract_resumen_cash_components(resumen: List[ResumenCuentaSnapshot]) -> Dict[str, Decimal]:
    cash_immediate_ars = Decimal('0')
    cash_immediate_usd = Decimal('0')
    cash_pending_ars = Decimal('0')
    cash_pending_usd = Decimal('0')
    fallback_cash_ars = Decimal('0')
    fallback_cash_usd = Decimal('0')
    total_broker_en_pesos = None

    for cuenta in resumen:
        currency_code = _normalize_account_currency(cuenta.moneda)
        disponible = Decimal(cuenta.disponible or 0)
        if currency_code == 'ARS':
            fallback_cash_ars += disponible
        elif currency_code == 'USD':
            fallback_cash_usd += disponible

        if total_broker_en_pesos is None and getattr(cuenta, 'total_en_pesos', None) is not None:
            total_broker_en_pesos = Decimal(cuenta.total_en_pesos)

        saldos_detalle = getattr(cuenta, 'saldos_detalle', None) or []
        if not saldos_detalle:
            continue

        immediate_found = False
        for saldo_row in saldos_detalle:
            liquidacion = str(saldo_row.get('liquidacion') or '').strip()
            disponible_row = Decimal(str(saldo_row.get('disponible', 0) or 0))
            if liquidacion == 'inmediato':
                immediate_found = True
                if currency_code == 'ARS':
                    cash_immediate_ars += disponible_row
                elif currency_code == 'USD':
                    cash_immediate_usd += disponible_row
            else:
                if currency_code == 'ARS':
                    cash_pending_ars += disponible_row
                elif currency_code == 'USD':
                    cash_pending_usd += disponible_row

        if not immediate_found:
            if currency_code == 'ARS':
                cash_immediate_ars += disponible
            elif currency_code == 'USD':
                cash_immediate_usd += disponible

    if cash_immediate_ars == 0 and fallback_cash_ars > 0:
        cash_immediate_ars = fallback_cash_ars
    if cash_immediate_usd == 0 and fallback_cash_usd > 0:
        cash_immediate_usd = fallback_cash_usd

    return {
        'cash_immediate_ars': cash_immediate_ars,
        'cash_immediate_usd': cash_immediate_usd,
        'cash_pending_ars': cash_pending_ars,
        'cash_pending_usd': cash_pending_usd,
        'cash_disponible_ars': fallback_cash_ars,
        'cash_disponible_usd': fallback_cash_usd,
        'total_broker_en_pesos': total_broker_en_pesos or Decimal('0'),
    }


def get_dashboard_kpis() -> Dict:
    """Calcula los KPIs principales del dashboard con métricas separadas por categoría."""
    def build():
        portafolio = get_latest_portafolio_data()
        resumen = get_latest_resumen_data()

        # Obtener clasificación del portafolio
        portafolio_clasificado = get_portafolio_enriquecido_actual()

        # Cash inmediato y a liquidar desde estadocuenta
        cash_components = _extract_resumen_cash_components(resumen)
        cash_ars = cash_components['cash_immediate_ars']
        cash_usd = cash_components['cash_immediate_usd']
        cash_a_liquidar_ars = cash_components['cash_pending_ars']
        cash_a_liquidar_usd = cash_components['cash_pending_usd']
        total_broker_en_pesos = cash_components['total_broker_en_pesos']

        # 1. Total IOL = SUM(valorizado de todos los activos) + cash ARS + cash USD
        total_activos_valorizados = sum(activo.valorizado for activo in portafolio)
        total_iol_calculado = total_activos_valorizados + cash_ars + cash_usd
        total_iol = total_broker_en_pesos if total_broker_en_pesos > 0 else total_iol_calculado

        # KPIs separados por categoría
        # 2. Liquidez Operativa = caución + saldo ARS disponible + saldo USD disponible
        caucion_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['liquidez'] if item['tipo_traducido'] == 'Caución')
        liquidez_operativa = caucion_valor + cash_ars + cash_usd

        # 3. FCI Cash Management = suma de FCI de cash management
        fci_cash_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['fci_cash_management'])

        # 4. Portafolio Invertido = activos de inversión (CEDEAR, acciones, bonos, ETF, otros FCI)
        portafolio_invertido = sum(item['activo'].valorizado for item in portafolio_clasificado['inversion'])

        cash_disponible_broker = cash_ars + cash_usd
        caucion_colocada = caucion_valor
        liquidez_estrategica = fci_cash_valor
        liquidez_total_combinada = cash_disponible_broker + caucion_colocada + liquidez_estrategica
        total_patrimonio_modelado = (
            portafolio_invertido
            + liquidez_estrategica
            + cash_disponible_broker
            + caucion_colocada
        )

        # KPIs heredados para compatibilidad
        titulos_valorizados = sum(
            activo.valorizado for activo in portafolio
            if activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in activo.simbolo.upper()
        )
        capital_invertido_real = total_iol - liquidez_operativa - fci_cash_valor

        # Rendimiento simple sobre costo estimado del capital realmente invertido.
        inversion = portafolio_clasificado['inversion']
        rendimiento_total_dinero = sum(item['activo'].ganancia_dinero for item in inversion)
        costo_estimado_invertido = portafolio_invertido - rendimiento_total_dinero
        rendimiento_total_porcentaje = (
            rendimiento_total_dinero / costo_estimado_invertido * 100
        ) if costo_estimado_invertido > 0 else 0

        # Concentraci?n de posiciones sobre portafolio invertido.
        portafolio_ordenado = sorted(
            (item['activo'] for item in inversion),
            key=lambda activo: activo.valorizado,
            reverse=True,
        )
        top_5_valor = sum(activo.valorizado for activo in portafolio_ordenado[:5])
        top_5_concentracion = (top_5_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Top 10 concentraci?n
        top_10_valor = sum(activo.valorizado for activo in portafolio_ordenado[:10])
        top_10_concentracion = (top_10_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Porcentajes de los bloques patrimoniales
        pct_fci_cash_management = (fci_cash_valor / total_iol * 100) if total_iol else 0
        pct_portafolio_invertido = (portafolio_invertido / total_iol * 100) if total_iol else 0
        pct_liquidez_total = ((liquidez_operativa + fci_cash_valor) / total_iol * 100) if total_iol else 0
        pct_liquidez_operativa = (cash_disponible_broker / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_caucion_colocada = (caucion_colocada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_liquidez_estrategica = (liquidez_estrategica / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_liquidez_total_combinada = (liquidez_total_combinada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_portafolio_invertido_modelado = (portafolio_invertido / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0

        return {
            'total_iol': total_iol,
            'total_iol_legacy_calculated': total_iol_calculado,
            'total_broker_en_pesos': total_broker_en_pesos,
            'total_patrimonio_modelado': total_patrimonio_modelado,
            'titulos_valorizados': titulos_valorizados,
            'cash_ars': cash_ars,
            'cash_usd': cash_usd,
            'cash_a_liquidar_ars': cash_a_liquidar_ars,
            'cash_a_liquidar_usd': cash_a_liquidar_usd,
            'cash_a_liquidar_broker': cash_a_liquidar_ars + cash_a_liquidar_usd,
            'cash_disponible_broker': cash_disponible_broker,
            'caucion_valor': caucion_valor,
            'caucion_colocada': caucion_colocada,
            'liquidez_operativa': liquidez_operativa,
            'liquidez_estrategica': liquidez_estrategica,
            'liquidez_total_combinada': liquidez_total_combinada,
            'fci_cash_management': fci_cash_valor,
            'portafolio_invertido': portafolio_invertido,
            'capital_invertido_real': capital_invertido_real,
            'rendimiento_total_porcentaje': rendimiento_total_porcentaje,
            'rendimiento_total_dinero': rendimiento_total_dinero,
            'rendimiento_total_cost_basis': costo_estimado_invertido,
            'top_5_concentracion': top_5_concentracion,
            'top_10_concentracion': top_10_concentracion,
            'pct_liquidez_operativa': pct_liquidez_operativa,
            'pct_caucion_colocada': pct_caucion_colocada,
            'pct_liquidez_estrategica': pct_liquidez_estrategica,
            'pct_liquidez_total_combinada': pct_liquidez_total_combinada,
            'pct_fci_cash_management': pct_fci_cash_management,
            'pct_portafolio_invertido': pct_portafolio_invertido,
            'pct_portafolio_invertido_modelado': pct_portafolio_invertido_modelado,
            'pct_liquidez_total': pct_liquidez_total,
            'methodology': {
                'top_5_concentracion': 'sum(top_5 valorizado del portafolio invertido) / portafolio invertido',
                'top_10_concentracion': 'sum(top_10 valorizado del portafolio invertido) / portafolio invertido',
                'top_positions_basis': 'portafolio_invertido',
                'rendimiento_total_porcentaje': 'ganancia acumulada / costo estimado del portafolio invertido',
                'rendimiento_total_basis': 'portafolio_invertido_costo_estimado',
                'pct_liquidez_total': '(liquidez operativa + cash management) / total iol',
                'pct_portafolio_invertido': 'portafolio invertido / total iol',
                'total_iol': 'si existe total_en_pesos desde estadocuenta se usa como ancla broker; si no, fallback a activos + cash inmediato',
                'total_patrimonio_modelado': 'portafolio invertido + cash disponible broker + caucion colocada + fci cash management',
                'pct_liquidez_operativa': 'cash disponible broker / total patrimonio modelado',
                'pct_caucion_colocada': 'caucion colocada / total patrimonio modelado',
                'pct_liquidez_estrategica': 'fci cash management / total patrimonio modelado',
                'pct_liquidez_total_combinada': '(cash disponible broker + caucion colocada + fci cash management) / total patrimonio modelado',
                'pct_portafolio_invertido_modelado': 'portafolio invertido / total patrimonio modelado',
            },
        }

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

    total = float(kpis.get("total_patrimonio_modelado") or kpis.get("total_iol") or 0.0)
    cash_operativo = float(kpis.get("cash_disponible_broker") or 0.0)
    caucion_tactica = float(kpis.get("caucion_colocada") or 0.0)
    fci_estrategico = float(
        kpis.get("liquidez_estrategica")
        if kpis.get("liquidez_estrategica") is not None
        else (kpis.get("fci_cash_management") or 0.0)
    )

    # Fallback para payloads viejos que solo exponen liquidez_operativa.
    if (
        "cash_disponible_broker" not in kpis
        and "caucion_colocada" not in kpis
        and "liquidez_operativa" in kpis
    ):
        cash_operativo = float(kpis.get("liquidez_operativa") or 0.0)
        caucion_tactica = 0.0

    liquidez_desplegable_total = cash_operativo + caucion_tactica + fci_estrategico

    return {
        "cash_operativo": cash_operativo,
        "caucion_tactica": caucion_tactica,
        "fci_estrategico": fci_estrategico,
        "liquidez_desplegable_total": liquidez_desplegable_total,
        "pct_cash_operativo": (cash_operativo / total * 100) if total > 0 else 0.0,
        "pct_caucion_tactica": (caucion_tactica / total * 100) if total > 0 else 0.0,
        "pct_fci_estrategico": (fci_estrategico / total * 100) if total > 0 else 0.0,
        "pct_liquidez_desplegable_total": (
            liquidez_desplegable_total / total * 100
        ) if total > 0 else 0.0,
        "total_base": total,
        "methodology": {
            "cash_operativo": "cash disponible broker",
            "caucion_tactica": "caucion colocada",
            "fci_estrategico": "fci cash management",
            "liquidez_desplegable_total": "cash operativo + caucion tactica + fci estrategico",
            "total_base": "total patrimonio modelado",
        },
    }


def _build_portfolio_scope_summary() -> Dict:
    """Explicita el universo broker vs capital invertido para Planeacion."""

    kpis = get_dashboard_kpis()
    resumen = get_latest_resumen_data()

    cash_components = _extract_resumen_cash_components(resumen)
    cash_ars = float(cash_components['cash_immediate_ars'])
    cash_usd = float(cash_components['cash_immediate_usd'])
    cash_a_liquidar_ars = float(cash_components['cash_pending_ars'])
    cash_a_liquidar_usd = float(cash_components['cash_pending_usd'])
    portfolio_total_broker = float(kpis.get("total_broker_en_pesos") or kpis.get("total_iol") or 0.0)
    invested_portfolio = float(kpis.get("portafolio_invertido") or 0.0)
    caucion_colocada = float(kpis.get("caucion_colocada") or 0.0)
    cash_management_fci = float(kpis.get("fci_cash_management") or 0.0)
    cash_available_broker = cash_ars

    cash_ratio_total = (cash_available_broker / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    caucion_ratio_total = (caucion_colocada / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    invested_ratio_total = (invested_portfolio / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    fci_ratio_total = (cash_management_fci / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0

    return {
        "portfolio_total_broker": portfolio_total_broker,
        "invested_portfolio": invested_portfolio,
        "caucion_colocada": caucion_colocada,
        "cash_management_fci": cash_management_fci,
        "cash_available_broker": cash_available_broker,
        "cash_available_broker_ars": cash_ars,
        "cash_available_broker_usd": cash_usd,
        "cash_settling_broker": cash_a_liquidar_ars,
        "cash_settling_broker_ars": cash_a_liquidar_ars,
        "cash_settling_broker_usd": cash_a_liquidar_usd,
        "cash_ratio_total": cash_ratio_total,
        "caucion_ratio_total": caucion_ratio_total,
        "invested_ratio_total": invested_ratio_total,
        "fci_ratio_total": fci_ratio_total,
    }


def get_distribucion_sector(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por sector o bloque patrimonial seg?n la base."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'sector')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'sector')


def get_distribucion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Obtiene la distribuci?n por pa?s de exposici?n real."""
    if base == 'total_iol':
        distribucion = _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'pais_exposicion')
        for pais, monto in _get_resumen_cash_distribution_by_country().items():
            distribucion[pais] = distribucion.get(pais, 0) + monto
        return distribucion
    return _build_distribution_from_items(_get_activos_invertidos(), 'pais_exposicion')


def get_distribucion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por tipo patrimonial."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'tipo_patrimonial')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'tipo_patrimonial')


def get_distribucion_moneda() -> Dict[str, float]:
    """Obtiene la distribución por moneda de exposición real/económica."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    distribucion = {}
    # Agregar activos del portafolio
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)

        # Moneda económica/subyacente (exposición real)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            moneda = 'USD'
        elif activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            # Para otros casos, intentar inferir de tipo_patrimonial
            if parametro and parametro.tipo_patrimonial == 'Hard Assets':
                moneda = 'Hard Assets'
            else:
                moneda = 'ARS'  # Default a ARS

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_distribucion_moneda_operativa() -> Dict[str, float]:
    """Obtiene la distribución por moneda operativa (de cotización)."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    distribucion = {}

    # Agregar activos del portafolio por moneda de cotización
    for activo in portafolio:
        if activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            moneda = 'ARS'  # Default

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_concentracion_patrimonial() -> Dict[str, float]:
    """Obtiene la concentración por bloque patrimonial (Liquidez, Cash Management, Invertido)."""
    kpis = get_dashboard_kpis()
    total_iol = kpis['total_iol']

    if total_iol == 0:
        return {}

    return {
        'Liquidez': (kpis['liquidez_operativa'] / total_iol * 100),
        'Cash Management': (kpis['fci_cash_management'] / total_iol * 100),
        'Invertido': (kpis['portafolio_invertido'] / total_iol * 100),
    }


def get_concentracion_sectorial() -> Dict[str, float]:
    """Obtiene la concentración por sector económico (excluyendo liquidez)."""
    # Solo considerar activos de inversión (excluir liquidez y cash management)
    portafolio_invertido = get_portafolio_enriquecido_actual()['inversion']
    distribucion = {}

    for item in portafolio_invertido:
        sector = item['sector']
        if sector and sector != 'N/A':
            distribucion[sector] = distribucion.get(sector, 0) + float(item['activo'].valorizado)

    total = sum(distribucion.values())
    if total == 0:
        return {}
    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_sector() -> Dict[str, float]:
    """Calcula la concentraci?n sectorial pura del capital invertido."""
    distribucion = get_distribucion_sector(base='portafolio_invertido')
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}




def get_concentracion_sector_agregado() -> Dict[str, float]:
    """Calcula concentracion sectorial agregando subsectores tecnol?gicos."""
    distribucion = _aggregate_sector_labels(get_distribucion_sector(base='portafolio_invertido'))
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Calcula la concentraci?n por pa?s en porcentajes."""
    distribucion = get_distribucion_pais(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {pais: (valor / total * 100) for pais, valor in distribucion.items()}


def get_concentracion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Calcula la concentraci?n por tipo patrimonial en porcentajes."""
    distribucion = get_distribucion_tipo_patrimonial(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {tipo: (valor / total * 100) for tipo, valor in distribucion.items()}


def get_concentracion_moneda() -> Dict[str, float]:
    """Calcula la concentracion por moneda economica en porcentajes."""
    distribucion = get_distribucion_moneda()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_concentracion_moneda_operativa() -> Dict[str, float]:
    """Calcula la concentracion por moneda operativa en porcentajes."""
    distribucion = get_distribucion_moneda_operativa()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_riesgo_portafolio_detallado() -> Dict[str, float]:
    """Calcula métricas detalladas de riesgo del portafolio."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición geográfica
    exposicion_usa = 0
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
        elif parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado

    # Exposición por tipo
    exposicion_tech = 0
    exposicion_renta_fija_ar = 0
    exposicion_defensivo = 0
    exposicion_growth = 0

    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro:
            if _is_technology_sector(parametro.sector):
                exposicion_tech += activo.valorizado
            if parametro.tipo_patrimonial == 'Bond' and parametro.pais_exposicion == 'Argentina':
                exposicion_renta_fija_ar += activo.valorizado
            if parametro.bloque_estrategico == 'Defensivo':
                exposicion_defensivo += activo.valorizado
            if parametro.bloque_estrategico == 'Growth':
                exposicion_growth += activo.valorizado

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)


    # Calcular porcentajes
    pct_usa = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_argentina = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_tech = (exposicion_tech / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_renta_fija_ar = (exposicion_renta_fija_ar / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_defensivo = (exposicion_defensivo / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_growth = (exposicion_growth / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_liquidez = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

    return {
        'pct_usa': pct_usa,
        'pct_argentina': pct_argentina,
        'pct_tech': pct_tech,
        'pct_bonos_soberanos': pct_renta_fija_ar,
        'pct_renta_fija_ar': pct_renta_fija_ar,
        'pct_defensivo': pct_defensivo,
        'pct_growth': pct_growth,
        'pct_liquidez': pct_liquidez,
        'methodology': {
            'pct_usa': 'exposicion USA / portafolio invertido',
            'pct_argentina': 'exposicion Argentina / portafolio invertido',
            'pct_tech': 'sectores que comienzan con Tecnología / portafolio invertido',
            'pct_renta_fija_ar': 'Bonos argentinos (soberanos, CER y corporativos) / portafolio invertido',
            'pct_defensivo': 'bloque Defensivo / portafolio invertido',
            'pct_growth': 'bloque Growth / portafolio invertido',
            'pct_liquidez': 'liquidez operativa / total iol',
        },
    }


def get_riesgo_portafolio() -> Dict[str, float]:
    """Calcula métricas de riesgo del portafolio (versión simplificada para compatibilidad)."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición USA
    exposicion_usa = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
    exposicion_usa_pct = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0

    # Exposición Argentina
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado
    exposicion_argentina_pct = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)

    liquidez_pct = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

    volatility_metrics = VolatilityService().calculate_volatility(days=90)
    var_metrics = VaRService().calculate_var_set(confidence=0.95, lookback_days=252)
    cvar_metrics = CVaRService().calculate_cvar_set(confidence=0.95, lookback_days=252)
    stress_metrics = StressTestService().run_all()
    benchmarking = TrackingErrorService().calculate(days=90)
    liquidity = LiquidityService().analyze_portfolio_liquidity()
    metadata_quality = MetadataAuditService().run_audit()
    volatilidad_pct = volatility_metrics.get('annualized_volatility')

    result = {
        'volatilidad_estimada': volatilidad_pct,
        'volatilidad_status': 'ok' if volatilidad_pct is not None else 'insufficient_history',
        'volatilidad_warning': volatility_metrics.get('warning'),
        'volatilidad_observations': volatility_metrics.get('observations'),
        'volatilidad_required_min_observations': volatility_metrics.get('required_min_observations'),
        'exposicion_usa': exposicion_usa_pct,
        'exposicion_argentina': exposicion_argentina_pct,
        'liquidez': liquidez_pct,
    }
    result.update(var_metrics)
    result.update(cvar_metrics)
    result.update(benchmarking)
    if liquidity:
        result["liquidity_score"] = liquidity.get("portfolio_liquidity_score")
        result["days_to_liquidate"] = liquidity.get("days_to_liquidate")
    if metadata_quality:
        result["metadata_unclassified_count"] = metadata_quality.get("unclassified_assets_count", 0)
        result["metadata_inconsistent_count"] = metadata_quality.get("inconsistent_assets_count", 0)
    if stress_metrics:
        worst_case = min(
            stress_metrics.values(),
            key=lambda scenario: scenario.get("impact_portfolio_pct", 0)
        )
        result["stress_worst_case_label"] = worst_case["label"]
        result["stress_worst_case_pct"] = worst_case["impact_portfolio_pct"]
    return result


def get_analytics_mensual() -> Dict[str, float]:
    """Calcula m?tricas operativas del mes actual a partir de operaciones ejecutadas."""
    from apps.operaciones_iol.models import OperacionIOL
    from apps.parametros.models import ConfiguracionDashboard
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin_mes = (inicio_mes + relativedelta(months=1)) - timezone.timedelta(seconds=1)

    operaciones_mes = OperacionIOL.objects.filter(
        fecha_operada__gte=inicio_mes,
        fecha_operada__lte=fin_mes,
        estado__in=['terminada', 'Terminada', 'TERMINADA']
    )

    if not operaciones_mes.exists():
        operaciones_mes = OperacionIOL.objects.filter(
            fecha_orden__gte=inicio_mes,
            fecha_orden__lte=fin_mes,
            estado__in=['terminada', 'Terminada', 'TERMINADA']
        )

    operaciones_mes_list = list(operaciones_mes.order_by('-fecha_operada', '-fecha_orden'))
    monto_compras = Decimal('0')
    monto_ventas = Decimal('0')
    dividendos_mes = Decimal('0')
    suscripciones_fci_mes = Decimal('0')
    rescates_fci_mes = Decimal('0')
    compras_count = 0
    ventas_count = 0
    dividendos_count = 0
    suscripciones_fci_count = 0
    rescates_fci_count = 0
    recent_operations = []

    for op in operaciones_mes_list:
        operation_type_key = classify_operation_type(op.tipo)
        effective_amount = get_effective_operation_amount(op)

        if operation_type_key == 'buy':
            compras_count += 1
            monto_compras += effective_amount
        elif operation_type_key == 'sell':
            ventas_count += 1
            monto_ventas += effective_amount
        elif operation_type_key == 'dividend':
            dividendos_count += 1
            dividendos_mes += effective_amount
        elif operation_type_key == 'fci_subscription':
            suscripciones_fci_count += 1
            suscripciones_fci_mes += effective_amount
        elif operation_type_key == 'fci_redemption':
            rescates_fci_count += 1
            rescates_fci_mes += effective_amount

        if len(recent_operations) < 5:
            event_at = op.fecha_operada or op.fecha_orden
            recent_operations.append(
                {
                    'numero': op.numero,
                    'simbolo': op.simbolo,
                    'tipo': op.tipo,
                    'tipo_key': operation_type_key,
                    'estado': op.estado_actual or op.estado,
                    'fecha_label': timezone.localtime(event_at).strftime("%Y-%m-%d %H:%M") if event_at else '',
                    'monto': effective_amount,
                    'plazo': op.plazo or '',
                    'moneda': op.moneda or '',
                }
            )

    try:
        config_objetivo = ConfiguracionDashboard.objects.get(clave='contribucion_mensual')
        aporte_mensual_objetivo = float(config_objetivo.valor)
    except (ConfiguracionDashboard.DoesNotExist, ValueError):
        aporte_mensual_objetivo = 50000.0

    aporte_mensual_objetivo = Decimal(str(aporte_mensual_objetivo))
    aporte_ejecutado = monto_compras - monto_ventas
    aporte_pendiente = aporte_mensual_objetivo - aporte_ejecutado

    return {
        'compras_mes': monto_compras,
        'ventas_mes': monto_ventas,
        'compras_count': compras_count,
        'ventas_count': ventas_count,
        'dividendos_mes': dividendos_mes,
        'dividendos_count': dividendos_count,
        'suscripciones_fci_mes': suscripciones_fci_mes,
        'suscripciones_fci_count': suscripciones_fci_count,
        'rescates_fci_mes': rescates_fci_mes,
        'rescates_fci_count': rescates_fci_count,
        'operaciones_ejecutadas_count': len(operaciones_mes_list),
        'aporte_mensual_ejecutado': aporte_ejecutado,
        'aporte_pendiente': max(0, aporte_pendiente),
        'recent_operations': recent_operations,
    }

def get_portafolio_clasificado_fecha(portafolio_fecha) -> Dict[str, List[Dict]]:
    """Clasifica un portafolio histórico en categorías (versión simplificada para evolución histórica)."""
    simbolos = [activo.simbolo for activo in portafolio_fecha]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    liquidez = []
    fci_cash_management = []
    inversion = []

    for activo in portafolio_fecha:
        parametro = parametros.get(activo.simbolo)

        # Determinar tipo traducido
        tipo_traducido = 'Desconocido'
        if activo.tipo == 'CEDEARS':
            tipo_traducido = 'CEDEAR'
        elif activo.tipo == 'ACCIONES':
            tipo_traducido = 'Acción'
        elif activo.tipo == 'TitulosPublicos':
            tipo_traducido = 'Título Público'
        elif activo.tipo == 'FondoComundeInversion':
            tipo_traducido = 'FCI'
        elif activo.tipo == 'CAUCIONESPESOS':
            tipo_traducido = 'Caución'

        item = {
            'activo': activo,
            'tipo_traducido': tipo_traducido,
            'parametro': parametro
        }

        # Clasificar por bloque estratégico
        if parametro and parametro.bloque_estrategico == 'Liquidez':
            liquidez.append(item)
        elif parametro and parametro.bloque_estrategico == 'FCI Cash Management':
            fci_cash_management.append(item)
        else:
            # Por defecto va a inversión
            inversion.append(item)

    return {
        'liquidez': liquidez,
        'fci_cash_management': fci_cash_management,
        'inversion': inversion,
    }


def get_evolucion_historica(days: int = 30, max_points: int = 14) -> Dict[str, list]:
    """Obtiene evolución histórica consolidada por día calendario."""
    from collections import defaultdict
    from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
    from apps.resumen_iol.models import ResumenCuentaSnapshot
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    fecha_fin = timezone.now()
    fecha_inicio = fecha_fin - relativedelta(days=days)

    portafolio_snapshots = ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")
    resumen_snapshots = ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")

    portafolio_por_dia = defaultdict(list)
    for activo in portafolio_snapshots:
        portafolio_por_dia[activo.fecha_extraccion.date()].append(activo)

    resumen_por_dia = defaultdict(list)
    for cuenta in resumen_snapshots:
        resumen_por_dia[cuenta.fecha_extraccion.date()].append(cuenta)

    fechas_unicas = sorted(set(portafolio_por_dia.keys()) | set(resumen_por_dia.keys()))
    if len(fechas_unicas) < 2:
        return {
            "tiene_datos": False,
            "mensaje": "Aún no hay historial suficiente para mostrar evolución",
            "fechas": [],
            "total_iol": [],
            "liquidez_operativa": [],
            "portafolio_invertido": [],
            "cash_management": [],
        }

    fechas_a_procesar = fechas_unicas[-max_points:] if max_points and max_points > 0 else fechas_unicas

    fechas_str = []
    total_iol_vals = []
    liquidez_vals = []
    portafolio_vals = []
    cash_vals = []

    for fecha in fechas_a_procesar:
        portafolio_fecha = portafolio_por_dia.get(fecha, [])
        resumen_fecha = resumen_por_dia.get(fecha, [])

        total_portafolio = sum(activo.valorizado for activo in portafolio_fecha)
        total_cash = sum(cuenta.disponible for cuenta in resumen_fecha)
        total_iol = total_portafolio + total_cash

        portafolio_clasificado = get_portafolio_clasificado_fecha(portafolio_fecha)

        caucion_valor = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("liquidez", [])
            if item["tipo_traducido"] == "Caución"
        )
        cash_ars = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "ARS")
        cash_usd = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "USD")
        liquidez_operativa = caucion_valor + cash_ars + cash_usd
        portafolio_invertido = sum(
            item["activo"].valorizado for item in portafolio_clasificado.get("inversion", [])
        )
        cash_management = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("fci_cash_management", [])
        )

        fechas_str.append(fecha.strftime("%Y-%m-%d"))
        total_iol_vals.append(float(total_iol))
        liquidez_vals.append(float(liquidez_operativa))
        portafolio_vals.append(float(portafolio_invertido))
        cash_vals.append(float(cash_management))

    return {
        "tiene_datos": True,
        "fechas": fechas_str,
        "total_iol": total_iol_vals,
        "liquidez_operativa": liquidez_vals,
        "portafolio_invertido": portafolio_vals,
        "cash_management": cash_vals,
    }


def get_objetivos_rebalanceo() -> Dict[str, Dict[str, float]]:
    """Define objetivos de asignación por bloque patrimonial y sectorial."""
    return {
        'patrimonial': {
            'Liquidez': 25.0,        # Objetivo: 20-30%
            'Cash Management': 7.5,  # Objetivo: 5-10%
            'Invertido': 67.5,       # Objetivo: 60-75%
        },
        'sectorial': {
            'Tecnología': 17.5,      # Objetivo: 15-20%
            'ETF core': 22.5,        # Objetivo: 20-25% (Índice, etc.)
            'Argentina': 12.5,       # Objetivo: 10-15%
            'Bonos': 12.5,           # Objetivo: 10-15% (Soberano, Corporativo)
            'Defensivos': 12.5,      # Objetivo: 10-15% (Consumo defensivo, Utilities)
            # Otros sectores se evalúan vs umbral mínimo
        }
    }


def mapear_sector_a_categoria(sector: str) -> str:
    """Mapea sectores específicos a categorías objetivo."""
    mapeo = {
        # ETF core
        'Índice': 'ETF core',
        'ETF': 'ETF core',
        # Bonos
        'Soberano': 'Bonos',
        'Corporativo': 'Bonos',
        'Título Público': 'Bonos',
        # Defensivos
        'Consumo defensivo': 'Defensivos',
        'Utilities': 'Defensivos',
        'Finanzas': 'Defensivos',
        # Argentina
        'Argentina': 'Argentina',
        # Tecnología (mantener como está)
        'Tecnología': 'Tecnología',
        'Tecnología / E-commerce': 'Tecnología',
        'Tecnología / Semiconductores': 'Tecnología',
    }
    return mapeo.get(sector, sector)


def get_senales_rebalanceo() -> Dict[str, list]:
    """Genera señales de rebalanceo basadas en objetivos definidos."""
    concentracion_patrimonial = get_concentracion_patrimonial()
    concentracion_sectorial = get_concentracion_sectorial()
    objetivos = get_objetivos_rebalanceo()

    # Umbrales para evaluación
    TOLERANCIA_SOBRE = 5.0   # +5% sobre objetivo = sobreponderado
    TOLERANCIA_SUB = 3.0     # -3% bajo objetivo = subponderado
    UMBRAL_MINIMO = 2.0      # Sectores sin objetivo: <2% = subponderado
    UMBRAL_POSICION_ALTA = 10.0  # >10% = posición alta

    # A. Rebalanceo patrimonial (vs objetivos definidos)
    patrimonial_sobreponderado = []
    patrimonial_subponderado = []

    for categoria, actual in concentracion_patrimonial.items():
        objetivo = objetivos['patrimonial'].get(categoria, actual)  # Si no hay objetivo, usar actual como baseline

        if actual > objetivo + TOLERANCIA_SOBRE:
            patrimonial_sobreponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(actual) - float(objetivo)
            })
        elif actual < objetivo - TOLERANCIA_SUB:
            patrimonial_subponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(objetivo) - float(actual)
            })

    # B. Rebalanceo sectorial (vs objetivos definidos o umbral mínimo)
    # Primero agrupar por categorías objetivo
    concentracion_agrupada = {}
    for sector, actual in concentracion_sectorial.items():
        categoria = mapear_sector_a_categoria(sector)
        concentracion_agrupada[categoria] = concentracion_agrupada.get(categoria, 0) + actual

    sectorial_sobreponderado = []
    sectorial_subponderado = []

    for categoria, actual in concentracion_agrupada.items():
        objetivo = objetivos['sectorial'].get(categoria)

        if objetivo is not None:
            # Categoría con objetivo definido
            if actual > objetivo + TOLERANCIA_SOBRE:
                sectorial_sobreponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(actual) - float(objetivo)
                })
            elif actual < objetivo - TOLERANCIA_SUB:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(objetivo) - float(actual)
                })
        else:
            # Categoría sin objetivo definido: evaluar vs umbral mínimo
            if actual < UMBRAL_MINIMO:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': actual,
                    'objetivo': None,
                    'diferencia': UMBRAL_MINIMO - actual
                })

    # Activos sin metadata (mantener igual)
    portafolio = get_latest_portafolio_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    activos_sin_metadata = []
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if not parametro or not all([
            parametro.sector != 'N/A',
            parametro.bloque_estrategico != 'N/A',
            parametro.pais_exposicion != 'N/A',
            parametro.tipo_patrimonial != 'N/A'
        ]):
            activos_sin_metadata.append({
                'simbolo': activo.simbolo,
                'valorizado': float(activo.valorizado)
            })

    # Posiciones con mayor peso (mantener igual)
    total_portafolio = sum(activo.valorizado for activo in portafolio)
    posiciones_altas = [
        {
            'simbolo': activo.simbolo,
            'peso': (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0,
            'valorizado': float(activo.valorizado)
        }
        for activo in portafolio
        if (activo.valorizado / total_portafolio * 100) > UMBRAL_POSICION_ALTA
    ]
    posiciones_altas.sort(key=lambda x: x['peso'], reverse=True)

    return {
        'patrimonial_sobreponderado': patrimonial_sobreponderado,
        'patrimonial_subponderado': patrimonial_subponderado,
        'sectorial_sobreponderado': sectorial_sobreponderado,
        'sectorial_subponderado': sectorial_subponderado,
        'activos_sin_metadata': activos_sin_metadata,
        'posiciones_mayor_peso': posiciones_altas,
    }


def get_snapshot_coverage_summary(days: int = 90) -> Dict[str, float | int | str | bool | None]:
    """Resume la cobertura reciente de snapshots para diagnosticar metricas temporales."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    snapshots = list(
        PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date)).order_by("fecha")
    )

    count = len(snapshots)
    if count == 0:
        return {
            "requested_days": days,
            "snapshots_count": 0,
            "latest_snapshot_date": None,
            "history_span_days": 0,
            "missing_days_estimate": days,
            "max_gap_days": None,
            "is_sufficient_for_volatility": False,
            "status": "insufficient_history",
        }

    latest_snapshot = snapshots[-1]
    earliest_snapshot = snapshots[0]
    history_span_days = (latest_snapshot.fecha - earliest_snapshot.fecha).days if count >= 2 else 0

    max_gap_days = 0
    for prev, curr in zip(snapshots, snapshots[1:]):
        gap_days = (curr.fecha - prev.fecha).days
        if gap_days > max_gap_days:
            max_gap_days = gap_days

    missing_days_estimate = max(days - count, 0)
    is_sufficient = count >= 5 and history_span_days >= 7

    return {
        "requested_days": days,
        "snapshots_count": count,
        "latest_snapshot_date": latest_snapshot.fecha.isoformat() if latest_snapshot else None,
        "latest_snapshot_at": (
            timezone.localtime(latest_snapshot.updated_at).strftime("%Y-%m-%d %H:%M")
            if latest_snapshot and latest_snapshot.updated_at
            else None
        ),
        "history_span_days": history_span_days,
        "missing_days_estimate": missing_days_estimate,
        "max_gap_days": max_gap_days if count >= 2 else None,
        "is_sufficient_for_volatility": is_sufficient,
        "status": "ok" if is_sufficient else "insufficient_history",
    }


def get_active_alerts() -> list:
    """Obtiene todas las alertas activas ordenadas por severidad y fecha."""
    from django.db.models import Case, When, IntegerField

    # Ordenar por severidad (critical > warning > info) y luego por fecha
    severity_order = Case(
        When(severidad='critical', then=3),
        When(severidad='warning', then=2),
        When(severidad='info', then=1),
        default=0,
        output_field=IntegerField(),
    )

    alerts = Alert.objects.filter(is_active=True).order_by(
        -severity_order, '-created_at'
    )

    return list(alerts.values(
        'id', 'tipo', 'mensaje', 'severidad', 'valor',
        'simbolo', 'sector', 'pais', 'created_at', 'is_acknowledged'
    ))


def _get_active_risk_contribution_result() -> Dict:
    base_risk_service = RiskContributionService()
    covariance_risk_service = CovarianceAwareRiskContributionService(base_service=base_risk_service)
    return resolve_active_risk_contribution_result(
        base_risk_service=base_risk_service,
        covariance_risk_service=covariance_risk_service,
    )


def get_risk_contribution_detail() -> Dict:
    """Devuelve el drill-down completo del modelo de risk contribution activo."""

    def build():
        return build_risk_contribution_detail(
            resolved=_get_active_risk_contribution_result(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("risk_contribution_detail", build)


def get_scenario_analysis_detail() -> Dict:
    """Devuelve el drill-down analitico completo de scenario analysis."""

    def build():
        return build_scenario_analysis_detail(
            scenario_service=ScenarioAnalysisService(),
            catalog_service=ScenarioCatalogService(),
        )

    return _get_cached_selector_result("scenario_analysis_detail", build)


def get_factor_exposure_detail() -> Dict:
    """Devuelve el drill-down analitico completo de factor exposure."""

    def build():
        factor_service = FactorExposureService()
        return build_factor_exposure_detail(
            factor_result=factor_service.calculate(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("factor_exposure_detail", build)


def get_stress_fragility_detail() -> Dict:
    """Devuelve el drill-down analitico completo de stress fragility."""

    def build():
        stress_service = StressFragilityService()
        stress_catalog_service = StressCatalogService()
        explanation_service = AnalyticsExplanationService()

        stress_rows = []
        for stress in stress_catalog_service.list_stresses():
            result = stress_service.calculate(stress["stress_key"])
            top_sector = result.get("vulnerable_sectors", [{}])[0] if result.get("vulnerable_sectors") else None
            top_country = result.get("vulnerable_countries", [{}])[0] if result.get("vulnerable_countries") else None
            stress_rows.append(
                {
                    "stress_key": stress["stress_key"],
                    "scenario_key": result.get("scenario_key", stress["stress_key"]),
                    "label": stress.get("label"),
                    "description": stress.get("description"),
                    "fragility_score": float(result.get("fragility_score") or 0.0),
                    "total_loss_pct": float(result.get("total_loss_pct") or 0.0),
                    "total_loss_money": float(result.get("total_loss_money") or 0.0),
                    "top_sector": top_sector,
                    "top_country": top_country,
                    "vulnerable_assets": result.get("vulnerable_assets", []),
                    "vulnerable_sectors": result.get("vulnerable_sectors", []),
                    "vulnerable_countries": result.get("vulnerable_countries", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        return build_stress_fragility_detail(
            stress_rows=stress_rows,
            explanation_service=explanation_service,
        )

    return _get_cached_selector_result("stress_fragility_detail", build)


def get_expected_return_detail() -> Dict:
    """Devuelve el drill-down analitico completo de expected return."""

    def build():
        expected_return_service = ExpectedReturnService()
        return build_expected_return_detail(
            result=expected_return_service.calculate(),
            explanation_service=AnalyticsExplanationService(),
        )

    return _get_cached_selector_result("expected_return_detail", build)


def get_monthly_allocation_plan(capital_amount: int | float = 600000) -> Dict:
    """Devuelve la propuesta mvp de asignacion mensual incremental."""

    cache_key = f"monthly_allocation_plan:{int(capital_amount)}"

    def build():
        service = MonthlyAllocationService()
        return service.build_plan(capital_amount)

    return _get_cached_selector_result(cache_key, build)

def get_operation_execution_feature_context(
    *,
    purchase_plan: list[dict] | None = None,
    lookback_days: int = 180,
    symbol_limit: int = 3,
) -> Dict:
    plan = list(purchase_plan or [])
    tracked_symbols = []
    for item in plan:
        symbol = str((item or {}).get("symbol") or "").strip().upper()
        if symbol and symbol not in tracked_symbols:
            tracked_symbols.append(symbol)
    cache_key = "operation_execution_feature:no_symbols"
    if tracked_symbols:
        cache_key = f"operation_execution_feature:{','.join(tracked_symbols)}:{int(lookback_days)}:{int(symbol_limit)}"

    def build():
        return build_operation_execution_feature_context(
            purchase_plan=plan,
            lookback_days=lookback_days,
            symbol_limit=symbol_limit,
            safe_percentage=_safe_percentage,
        )

    return _get_cached_selector_result(cache_key, build)


def get_candidate_asset_ranking(capital_amount: int | float = 600000) -> Dict:
    """Devuelve el ranking de activos candidatos dentro de los bloques recomendados."""

    cache_key = f"candidate_asset_ranking:{int(capital_amount)}"

    def build():
        service = CandidateAssetRankingService()
        return service.build_ranking(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation(capital_amount: int | float = 600000) -> Dict:
    """Construye una simulacion incremental default usando top candidato por bloque recomendado."""

    cache_key = f"incremental_portfolio_simulation:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        proposal = _build_top_candidate_purchase_plan(monthly_plan, candidate_ranking)
        if not proposal["purchase_plan"]:
            return {
                "capital_amount": float(capital_amount),
                "purchase_plan": [],
                "selected_candidates": [],
                "unmapped_blocks": proposal["unmapped_blocks"],
                "before": {},
                "after": {},
                "delta": {},
                "interpretation": "Todavia no hay candidatos suficientes para construir una simulacion incremental base.",
                "warnings": [],
                "selection_basis": "top_candidate_per_recommended_block",
            }

        simulator = IncrementalPortfolioSimulator()
        simulation = simulator.simulate(
            {
                "capital_amount": capital_amount,
                "purchase_plan": proposal["purchase_plan"],
            }
        )
        result = {
            "capital_amount": float(capital_amount),
            "purchase_plan": proposal["purchase_plan"],
            "selected_candidates": proposal["selected_candidates"],
            "unmapped_blocks": proposal["unmapped_blocks"],
            "before": simulation["before"],
            "after": simulation["after"],
            "delta": simulation["delta"],
            "interpretation": simulation["interpretation"],
            "warnings": simulation.get("warnings", []),
            "selection_basis": "top_candidate_per_recommended_block",
        }
        return result

    return _get_cached_selector_result(cache_key, build)

def get_incremental_portfolio_simulation_comparison(
    query_params=None,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara variantes simples de propuestas incrementales sobre el mismo capital mensual."""

    cache_key = f"incremental_portfolio_simulation_comparison:{int(capital_amount)}"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "comparison_readiness_filter")
    )

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        simulator = IncrementalPortfolioSimulator()

        proposals = []
        for proposal_key, label, builder in (
            ("top_candidate_per_block", "Top candidato por bloque", _build_top_candidate_purchase_plan),
            ("runner_up_when_available", "Segundo candidato si existe", _build_runner_up_purchase_plan),
            ("split_largest_block_top_two", "Split del bloque más grande", _build_split_largest_block_purchase_plan),
        ):
            proposal = builder(monthly_plan, candidate_ranking)
            if not proposal["purchase_plan"]:
                proposals.append(
                    _normalize_incremental_proposal_item(
                        {
                            "proposal_key": proposal_key,
                            "label": label,
                            "purchase_plan": [],
                            "selected_candidates": [],
                            "unmapped_blocks": proposal["unmapped_blocks"],
                            "simulation": {
                                "before": {},
                                "after": {},
                                "delta": {
                                    "expected_return_change": None,
                                    "real_expected_return_change": None,
                                    "fragility_change": None,
                                    "scenario_loss_change": None,
                                    "risk_concentration_change": None,
                                },
                                "interpretation": "No hay candidatos suficientes para construir esta variante.",
                            },
                            "comparison_score": None,
                        }
                    )
                )
                continue

            simulation = simulator.simulate(
                {
                    "capital_amount": capital_amount,
                    "purchase_plan": proposal["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=proposal["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            enriched = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": proposal_key,
                        "label": label,
                        "purchase_plan": proposal["purchase_plan"],
                        "selected_candidates": proposal["selected_candidates"],
                        "unmapped_blocks": proposal["unmapped_blocks"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=enriched,
            )
            enriched["operation_execution_signal"] = operation_execution_signal
            enriched["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=enriched,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(enriched)

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        operational_tiebreak = {"has_tiebreak": False, "used_operational_tiebreak": False, "headline": "", "summary": ""}
        return {
            "capital_amount": float(capital_amount),
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance actual",
                best_label=best["label"] if best else None,
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_manual_incremental_portfolio_simulation_comparison(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    """Compara planes incrementales definidos manualmente desde Planeacion."""

    form_state = _build_manual_incremental_comparison_form_state(
        query_params,
        default_capital_amount=default_capital_amount,
    )
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "manual_compare_readiness_filter")
    )
    normalized_plans = form_state["normalized_plans"]
    if not normalized_plans:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance manual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    signature = hashlib.md5(
        json.dumps(
            [
                {
                    "proposal_key": plan["proposal_key"],
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
                for plan in normalized_plans
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"manual_incremental_portfolio_simulation_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for plan in normalized_plans:
            simulation = simulator.simulate(
                {
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=plan["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": plan["proposal_key"],
                        "label": plan["label"],
                        "purchase_plan": plan["purchase_plan"],
                        "capital_amount": plan["capital_amount"],
                        "input_warnings": plan["warnings"],
                        "execution_order_label": plan.get("execution_order_label") or "",
                        "execution_order_summary": plan.get("execution_order_summary") or "",
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor balance manual",
                best_label=best["label"] if best else None,
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara candidatos individuales dentro de un bloque recomendado."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    requested_block = str(_query_param_value(query_params, "candidate_compare_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_compare", "")).strip() == "1"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "candidate_compare_readiness_filter")
    )

    selected_block = requested_block if requested_block in {item["bucket"] for item in comparable_blocks} else None
    if selected_block is None and comparable_blocks:
        selected_block = comparable_blocks[0]["bucket"]

    if selected_block is None:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor candidato actual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    selected_block_data = next(item for item in comparable_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for candidate in selected_block_data["candidates"][:3]:
            purchase_plan = [
                {
                    "symbol": candidate["asset"],
                    "amount": round(float(selected_block_data["suggested_amount"]), 2),
                }
            ]
            simulation = simulator.simulate(
                {
                    "capital_amount": float(selected_block_data["suggested_amount"]),
                    "purchase_plan": purchase_plan,
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=purchase_plan,
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": candidate["asset"],
                        "label": candidate["asset"],
                        "candidate": candidate,
                        "purchase_plan": purchase_plan,
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": selected_block_data["suggested_amount"],
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor candidato actual",
                best_label=best["label"] if best else None,
                selected_label=selected_block_data["label"],
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_split_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara concentrar el bloque en un candidato vs repartirlo entre top 2."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    split_blocks = [block for block in comparable_blocks if len(block["candidates"]) >= 2]
    requested_block = str(_query_param_value(query_params, "candidate_split_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_split_compare", "")).strip() == "1"
    readiness_filter = _normalize_incremental_readiness_filter(
        _query_param_value(query_params, "candidate_split_readiness_filter")
    )

    selected_block = requested_block if requested_block in {item["bucket"] for item in split_blocks} else None
    if selected_block is None and split_blocks:
        selected_block = split_blocks[0]["bucket"]

    if selected_block is None:
        empty_readiness = _build_manual_incremental_execution_readiness_summary(None)
        empty_tiebreak = {
            "has_tiebreak": False,
            "used_operational_tiebreak": False,
            "headline": "",
            "summary": "",
        }
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
            "best_execution_readiness": empty_readiness,
            "operational_tiebreak": empty_tiebreak,
            "active_readiness_filter": readiness_filter,
            "active_readiness_filter_label": _format_incremental_readiness_filter_label(readiness_filter),
            "available_readiness_filters": _build_incremental_readiness_filter_options(readiness_filter),
            "visible_count": 0,
            "total_count": 0,
            "has_active_readiness_filter": readiness_filter != "all",
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor construccion actual",
                best_label=None,
                best_execution_readiness=empty_readiness,
                operational_tiebreak=empty_tiebreak,
            ),
        }

    selected_block_data = next(item for item in split_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"][:2],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_split_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        top_candidate = selected_block_data["candidates"][0]
        runner_up = selected_block_data["candidates"][1]
        total_amount = round(float(selected_block_data["suggested_amount"]), 2)
        half_amount = round(total_amount / 2.0, 2)
        remainder_amount = round(total_amount - half_amount, 2)

        variants = [
            {
                "proposal_key": "single_top_candidate",
                "label": f"Concentrado en {top_candidate['asset']}",
                "purchase_plan": [{"symbol": top_candidate["asset"], "amount": total_amount}],
                "composition": [top_candidate["asset"]],
            },
            {
                "proposal_key": "split_top_two",
                "label": f"Split {top_candidate['asset']} + {runner_up['asset']}",
                "purchase_plan": [
                    {"symbol": top_candidate["asset"], "amount": half_amount},
                    {"symbol": runner_up["asset"], "amount": remainder_amount},
                ],
                "composition": [top_candidate["asset"], runner_up["asset"]],
            },
        ]

        proposals = []
        for variant in variants:
            simulation = simulator.simulate(
                {
                    "capital_amount": total_amount,
                    "purchase_plan": variant["purchase_plan"],
                }
            )
            operation_execution_feature = get_operation_execution_feature_context(
                purchase_plan=variant["purchase_plan"],
                lookback_days=180,
                symbol_limit=3,
            )
            proposal = _annotate_preferred_proposal_with_execution_quality(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": variant["proposal_key"],
                        "label": variant["label"],
                        "purchase_plan": variant["purchase_plan"],
                        "composition": variant["composition"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                ),
                operation_execution_feature=operation_execution_feature,
            )
            operation_execution_signal = _build_decision_operation_execution_signal(
                operation_execution_feature=operation_execution_feature,
                preferred_proposal=proposal,
            )
            proposal["operation_execution_signal"] = operation_execution_signal
            proposal["execution_readiness"] = _build_manual_incremental_execution_readiness(
                proposal=proposal,
                operation_execution_signal=operation_execution_signal,
            )
            proposals.append(proposal)

        ranked, best, operational_tiebreak = _resolve_manual_incremental_operational_tiebreak(proposals)
        filter_metadata = _build_incremental_readiness_filter_metadata(
            proposals=ranked,
            readiness_filter=readiness_filter,
        )
        visible_ranked = filter_metadata["filtered_proposals"]
        best = next((item for item in visible_ranked if item["comparison_score"] is not None), None)
        if filter_metadata["has_active_readiness_filter"]:
            operational_tiebreak = {
                "has_tiebreak": False,
                "used_operational_tiebreak": False,
                "headline": "",
                "summary": "",
            }
        best_execution_readiness = _build_manual_incremental_execution_readiness_summary(best)
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": total_amount,
            "proposals": visible_ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
            "best_execution_readiness": best_execution_readiness,
            "operational_tiebreak": operational_tiebreak,
            "active_readiness_filter": filter_metadata["active_readiness_filter"],
            "active_readiness_filter_label": filter_metadata["active_readiness_filter_label"],
            "available_readiness_filters": filter_metadata["available_readiness_filters"],
            "visible_count": filter_metadata["visible_count"],
            "total_count": filter_metadata["total_count"],
            "has_active_readiness_filter": filter_metadata["has_active_readiness_filter"],
            "display_summary": _build_incremental_comparator_summary(
                lead_label="Mejor construcci?n actual",
                best_label=best["label"] if best else None,
                selected_label=selected_block_data["label"],
                best_execution_readiness=best_execution_readiness,
                operational_tiebreak=operational_tiebreak,
            ),
        }

    return _get_cached_selector_result(cache_key, build)


def get_preferred_incremental_portfolio_proposal(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza la mejor propuesta incremental disponible entre los comparadores activos."""

    auto = get_incremental_portfolio_simulation_comparison(capital_amount=capital_amount)
    candidate = get_candidate_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    split = get_candidate_split_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    manual = get_manual_incremental_portfolio_simulation_comparison(
        query_params,
        default_capital_amount=capital_amount,
    )

    candidates = []
    for source_key, label, payload in (
        ("automatic_variants", "Comparador automático", auto),
        ("candidate_block", "Comparador por candidato", candidate),
        ("candidate_split", "Comparador por split", split),
        ("manual_plan", "Comparador manual", manual),
    ):
        best_item = _extract_best_incremental_proposal(payload)
        if best_item is None:
            continue
        candidates.append(
            _normalize_incremental_proposal_item(
                {
                    "source_key": source_key,
                    "source_label": label,
                    "proposal_key": best_item["proposal_key"],
                    "proposal_label": best_item.get("proposal_label") or best_item.get("label"),
                    "purchase_plan": best_item.get("purchase_plan", []),
                    "comparison_score": best_item.get("comparison_score"),
                    "simulation": best_item.get("simulation", {}),
                    "selected_context": _build_preferred_proposal_context(source_key, payload),
                    "priority_rank": _preferred_source_priority_rank(source_key, payload),
                }
            )
        )

    best = None
    if candidates:
        best = sorted(
            candidates,
            key=lambda item: (
                float(item["comparison_score"] if item["comparison_score"] is not None else float("-inf")),
                item["priority_rank"],
            ),
            reverse=True,
        )[0]

    return {
        "candidates": candidates,
        "preferred": best,
        "has_manual_override": bool(manual.get("submitted") and manual.get("proposals")),
        "explanation": _build_preferred_incremental_explanation(best, manual),
    }


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








