import logging
import math
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.core.services.alerts_engine import AlertsEngine
from apps.core.services.performance.attribution_service import AttributionService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.core.services.observability import get_state_summary, get_timing_summary
from apps.core.services.rebalance_engine import RebalanceEngine
from apps.core.services.security_audit import record_sensitive_action
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.temporal_metrics_service import TemporalMetricsService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_sector,
    get_dashboard_kpis,
    get_evolucion_historica,
    get_senales_rebalanceo,
)
from apps.portafolio_iol.models import PortfolioSnapshot

logger = logging.getLogger(__name__)

MAX_PORTFOLIO_PAYLOAD_ITEMS = 50
MAX_SYMBOL_LENGTH = 24
MAX_MONETARY_INPUT = 1_000_000_000_000
MAX_QUANTITY_INPUT = 1_000_000_000
MIN_TARGET_RETURN = -1.0
MAX_TARGET_RETURN = 10.0

METRIC_BASES = {
    'total_portfolio': 'Total IOL (activos + cash)',
    'invested_capital': 'Capital invertido en activos',
    'portfolio_ex_cash': 'Portafolio excluyendo cash',
    'invested_portfolio_market_value': 'Portafolio invertido a valor de mercado',
    'invested_portfolio_estimated_cost': 'Costo estimado del portafolio invertido (valor actual menos ganancia acumulada)',
    'total_iol_with_cash_country_mapping': 'Total IOL con cash y liquidez asignados por país económico',
}


def build_metric_metadata(
    methodology: str,
    data_basis: str,
    limitations: str,
    extra: dict | None = None,
) -> dict:
    metadata = {
        "methodology": methodology,
        "data_basis": data_basis,
        "limitations": limitations,
    }
    if extra:
        metadata.update(extra)
    return metadata


def internal_error_response(exc: Exception, endpoint: str) -> Response:
    logger.exception("API error in %s: %s", endpoint, exc)
    return Response(
        {"error": "Internal server error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def sanitize_json_payload(value):
    if isinstance(value, dict):
        return {key: sanitize_json_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json_payload(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _coerce_optional_float(value):
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _serialize_historical_snapshot(snapshot_like: dict | object, *, fallback: bool = False) -> dict:
    def read(field_name):
        if isinstance(snapshot_like, dict):
            return snapshot_like.get(field_name)
        return getattr(snapshot_like, field_name, None)

    cash_management = _coerce_optional_float(read("cash_management")) or 0.0
    legacy_liquidez_operativa = _coerce_optional_float(read("liquidez_operativa")) or 0.0
    cash_disponible_broker = _coerce_optional_float(read("cash_disponible_broker"))
    caucion_colocada = _coerce_optional_float(read("caucion_colocada"))
    total_patrimonio_modelado = _coerce_optional_float(read("total_patrimonio_modelado"))

    has_explicit_layers = any(
        value is not None
        for value in (cash_disponible_broker, caucion_colocada, total_patrimonio_modelado)
    )
    if has_explicit_layers:
        liquidity_contract_status = "explicit_layers"
        liquidez_desplegable_total = (
            (cash_disponible_broker or 0.0)
            + (caucion_colocada or 0.0)
            + cash_management
        )
        if total_patrimonio_modelado is None:
            total_patrimonio_modelado = (
                (_coerce_optional_float(read("portafolio_invertido")) or 0.0)
                + liquidez_desplegable_total
            )
    else:
        liquidity_contract_status = "legacy_aggregated_fallback" if fallback else "legacy_aggregated"
        liquidez_desplegable_total = legacy_liquidez_operativa + cash_management

    return {
        "fecha": read("fecha"),
        "total_iol": read("total_iol"),
        "portafolio_invertido": read("portafolio_invertido"),
        "rendimiento_total": read("rendimiento_total"),
        "liquidez_operativa": read("liquidez_operativa"),
        "cash_management": read("cash_management"),
        "total_patrimonio_modelado": total_patrimonio_modelado,
        "cash_disponible_broker": cash_disponible_broker,
        "caucion_colocada": caucion_colocada,
        "liquidez_estrategica": cash_management,
        "liquidez_desplegable_total": liquidez_desplegable_total,
        "liquidity_contract_status": liquidity_contract_status,
    }


def _coerce_positive_number(value, *, field_name: str, max_value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} debe ser numérico")

    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} debe ser numérico")
    if numeric <= 0:
        raise ValueError(f"{field_name} debe ser mayor a 0")
    if numeric > max_value:
        raise ValueError(f"{field_name} excede el máximo permitido")
    return numeric


def _validate_symbol(value, *, field_name: str = "activo") -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        raise ValueError(f"{field_name} es obligatorio")
    if len(symbol) > MAX_SYMBOL_LENGTH:
        raise ValueError(f"{field_name} excede la longitud permitida")
    return symbol


def _validate_symbol_list(symbols, *, field_name: str = "activos") -> list[str]:
    if not isinstance(symbols, list):
        raise ValueError(f"{field_name} debe ser una lista")
    if not symbols:
        raise ValueError(f"Se requieren {field_name}")
    if len(symbols) > MAX_PORTFOLIO_PAYLOAD_ITEMS:
        raise ValueError(f"{field_name} excede el máximo permitido")
    return [_validate_symbol(symbol, field_name="activo") for symbol in symbols]


def _validate_weight_mapping(mapping, *, field_name: str) -> dict[str, float]:
    if not isinstance(mapping, dict):
        raise ValueError(f"{field_name} debe ser un objeto")
    if not mapping:
        raise ValueError(f"Se requieren {field_name}")
    if len(mapping) > MAX_PORTFOLIO_PAYLOAD_ITEMS:
        raise ValueError(f"{field_name} excede el máximo permitido")

    validated = {}
    for key, value in mapping.items():
        symbol = _validate_symbol(key, field_name="activo")
        numeric = _coerce_positive_number(value, field_name=f"{field_name}:{symbol}", max_value=100.0)
        validated[symbol] = numeric
    return validated


def _coerce_target_return(value) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError("target_return debe ser numérico")

    if not math.isfinite(numeric):
        raise ValueError("target_return debe ser numérico")
    if numeric < MIN_TARGET_RETURN or numeric > MAX_TARGET_RETURN:
        raise ValueError("target_return fuera de rango permitido")
    return numeric


# Dashboard API
@api_view(['GET'])
def dashboard_kpis(request):
    """Obtiene KPIs principales del dashboard."""
    try:
        kpis = get_dashboard_kpis()
        kpis['metadata'] = {
            'bases': METRIC_BASES,
            'fields_basis': {
                'top_5_concentracion': 'invested_portfolio_market_value',
                'top_10_concentracion': 'invested_portfolio_market_value',
                'pct_fci_cash_management': 'total_portfolio',
                'pct_portafolio_invertido': 'total_portfolio',
                'rendimiento_total_porcentaje': 'invested_portfolio_estimated_cost',
            },
            'fields_methodology': {
                'top_5_concentracion': 'sum(top_5 valorizado del portafolio invertido) / portafolio invertido',
                'top_10_concentracion': 'sum(top_10 valorizado del portafolio invertido) / portafolio invertido',
                'rendimiento_total_porcentaje': 'ganancia acumulada / costo estimado del portafolio invertido',
            },
        }
        return Response(kpis, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_returns")

@api_view(['GET'])
def dashboard_concentracion_pais(request):
    """Obtiene concentración por país."""
    try:
        basis = request.query_params.get('basis', 'portafolio_invertido')
        if basis not in {'portafolio_invertido', 'total_iol'}:
            return Response(
                {'error': 'Par?metro basis inv?lido. Use portafolio_invertido o total_iol'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = get_concentracion_pais(base=basis)
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_volatility")

@api_view(['GET'])
def dashboard_concentracion_sector(request):
    """Obtiene concentración por sector."""
    try:
        data = get_concentracion_sector()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_performance")

@api_view(['GET'])
def dashboard_senales_rebalanceo(request):
    """Obtiene señales de rebalanceo."""
    try:
        data = get_senales_rebalanceo()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_historical_comparison")

# Alerts API
@api_view(['GET'])
def alerts_active(request):
    """Obtiene todas las alertas activas."""
    try:
        engine = AlertsEngine()
        alerts = engine.generate_alerts()
        return Response(alerts, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_var")

@api_view(['GET'])
def alerts_by_severity(request):
    """Obtiene alertas filtradas por severidad."""
    severity = request.query_params.get('severity', 'warning')
    try:
        engine = AlertsEngine()
        alerts = engine.get_alerts_by_severity(severity)
        return Response(alerts, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_cvar")

# Rebalance API
@api_view(['GET'])
def rebalance_suggestions(request):
    """Obtiene sugerencias de rebalanceo."""
    try:
        engine = RebalanceEngine()
        suggestions = engine.generate_rebalance_suggestions()
        return Response(suggestions, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_stress_test")

@api_view(['GET'])
def rebalance_critical_actions(request):
    """Obtiene acciones críticas de rebalanceo."""
    try:
        engine = RebalanceEngine()
        actions = engine.get_critical_actions()
        return Response(actions, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_attribution")

@api_view(['GET'])
def rebalance_opportunity_actions(request):
    """Obtiene acciones de oportunidad de rebalanceo."""
    try:
        engine = RebalanceEngine()
        actions = engine.get_opportunity_actions()
        return Response(actions, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_benchmarking")

# Temporal Metrics API
@api_view(['GET'])
def metrics_returns(request):
    """Obtiene retornos del portafolio."""
    try:
        days = int(request.query_params.get('days', 30))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service = TemporalMetricsService()
        returns = service.get_portfolio_returns(days)
        returns['metadata'] = build_metric_metadata(
            methodology='Time Weighted Return + returns by period over total portfolio value',
            data_basis='PortfolioSnapshot.total_iol',
            limitations='Requires at least two historical snapshots in selected period',
            extra={
                'bases': METRIC_BASES,
                'fields_basis': {
                    'total_period_return': 'total_portfolio',
                    'monthly_return': 'total_portfolio',
                    'weekly_return': 'total_portfolio',
                    'daily_return': 'total_portfolio',
                    'twr_total_return': 'total_portfolio',
                    'twr_annualized_return': 'total_portfolio',
                    'max_drawdown': 'total_portfolio',
                    'max_drawdown_real': 'total_portfolio',
                    'portfolio_return_ytd_nominal': 'total_portfolio',
                    'portfolio_return_ytd_real': 'total_portfolio',
                    'ipc_ytd': 'total_portfolio',
                    'badlar_privada': 'total_portfolio',
                    'badlar_ytd': 'total_portfolio',
                    'portfolio_excess_ytd_vs_badlar': 'total_portfolio',
                },
            },
        )
        return Response(returns, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "simulation_purchase")

@api_view(['GET'])
def metrics_volatility(request):
    """Obtiene volatilidad del portafolio."""
    try:
        days = int(request.query_params.get('days', 30))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service = TemporalMetricsService()
        volatility = service.get_portfolio_volatility(days)
        volatility['metadata'] = build_metric_metadata(
            methodology='Annualized standard deviation of daily returns: std(returns) * sqrt(252)',
            data_basis='PortfolioSnapshot.total_iol',
            limitations='Requires at least two snapshots; Sharpe/Sortino require non-zero volatility',
            extra={
                'bases': METRIC_BASES,
                'fields_basis': {
                    'daily_volatility': 'total_portfolio',
                    'annualized_volatility': 'total_portfolio',
                    'sharpe_ratio': 'total_portfolio',
                    'sharpe_ratio_badlar': 'total_portfolio',
                    'sortino_ratio': 'total_portfolio',
                },
            },
        )
        return Response(volatility, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "simulation_sale")

@api_view(['GET'])
def metrics_performance(request):
    """Obtiene métricas de performance completas."""
    try:
        days = int(request.query_params.get('days', 90))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service = TemporalMetricsService()
        metrics = service.get_performance_metrics(days)
        metrics['metadata'] = build_metric_metadata(
            methodology='Composite metrics package: returns, volatility, VaR/CVaR, attribution and benchmarking',
            data_basis='PortfolioSnapshot + PositionSnapshot + benchmark configuration',
            limitations='Sub-metrics may return warnings when historical depth is insufficient',
            extra={'bases': METRIC_BASES},
        )
        return Response(metrics, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "simulation_rebalance")

@api_view(['GET'])
def metrics_historical_comparison(request):
    """Obtiene comparación histórica de performance."""
    periods = request.query_params.get('periods', '7,30,90,180')
    try:
        periods = [int(p) for p in periods.split(',')]
    except ValueError:
        return Response(
            {'error': 'Parámetro periods debe contener números enteros válidos separados por comas'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service = TemporalMetricsService()
        comparison = service.get_historical_comparison(periods)
        comparison['metadata'] = build_metric_metadata(
            methodology='Comparative period returns and volatility over multiple lookback windows',
            data_basis='PortfolioSnapshot.total_iol',
            limitations='Each window requires at least two snapshots; sparse periods may be absent',
        )
        return Response(comparison, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "optimizer_risk_parity")


@api_view(['GET'])
def metrics_macro_comparison(request):
    """Obtiene comparacion historica normalizada entre portafolio nominal/real, dolar oficial e IPC."""
    try:
        days = int(request.query_params.get('days', 365))
    except ValueError:
        return Response(
            {'error': 'Parametro days debe ser un numero entero valido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = LocalMacroSeriesService().build_macro_comparison(days=days)
        result['metadata'] = build_metric_metadata(
            methodology='Normalized level comparison rebased to 100 for nominal portfolio, inflation-adjusted portfolio, USDARS official and IPC index',
            data_basis='PortfolioSnapshot.total_iol + BCRA + datos.gob.ar/INDEC snapshots',
            limitations='IPC is monthly and forward-filled across daily observations; real portfolio is deflated using that monthly series and sparse portfolio history may reduce overlap',
        )
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_macro_comparison")


@api_view(['GET'])
def metrics_var(request):
    """Obtiene VaR histórico y paramétrico."""
    try:
        confidence = float(request.query_params.get('confidence', 0.95))
    except ValueError:
        return Response(
            {'error': 'Parámetro confidence debe ser numérico'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        var_metrics = VaRService().calculate_var_set(confidence=confidence)
        var_metrics['metadata'] = build_metric_metadata(
            methodology='Historical VaR and Parametric VaR on daily portfolio returns',
            data_basis='PortfolioSnapshot.total_iol returns',
            limitations='Requires enough historical observations and assumes stable distribution for parametric VaR',
            extra={'confidence': confidence},
        )
        return Response(var_metrics, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "dashboard_kpis")


@api_view(['GET'])
def metrics_cvar(request):
    """Obtiene CVaR histórico."""
    try:
        confidence = float(request.query_params.get('confidence', 0.95))
    except ValueError:
        return Response(
            {'error': 'Parámetro confidence debe ser numérico'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        cvar_metrics = CVaRService().calculate_cvar_set(confidence=confidence)
        cvar_metrics['metadata'] = build_metric_metadata(
            methodology='Historical CVaR (Expected Shortfall) over left-tail portfolio returns',
            data_basis='PortfolioSnapshot.total_iol returns',
            limitations='Requires enough tail observations to be statistically stable',
            extra={'confidence': confidence},
        )
        return Response(cvar_metrics, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "dashboard_concentracion_pais")


@api_view(['GET'])
def metrics_stress_test(request):
    """Obtiene resultados de stress testing de portafolio."""
    try:
        result = StressTestService().run_all()
        return Response(
            {
                'scenarios': result,
                'metadata': build_metric_metadata(
                    methodology='Deterministic stress scenarios applied over current portfolio exposures',
                    data_basis='Current enriched portfolio positions and parameter metadata',
                    limitations='Scenario shocks are static and do not model second-order effects',
                ),
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return internal_error_response(e, "dashboard_concentracion_sector")


@api_view(['GET'])
def metrics_attribution(request):
    """Obtiene attribution de performance por activo/buckets/flujos."""
    try:
        days = int(request.query_params.get('days', 30))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        attribution = AttributionService().calculate_attribution(days=days)
        attribution['metadata'] = build_metric_metadata(
            methodology='Asset contribution based on weight * return and flow split',
            data_basis='Current portfolio + historical performance snapshots',
            limitations='Flow decomposition is an approximation when complete cashflow granularity is unavailable',
            extra={
                'details': {
                    'asset_contribution': 'weight * return',
                    'flow_split': 'total_return = market_return + flow_effect',
                },
                'bases': METRIC_BASES,
            },
        )
        return Response(attribution, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "dashboard_senales_rebalanceo")


@api_view(['GET'])
def metrics_benchmarking(request):
    """Obtiene métricas de benchmarking (tracking error + information ratio)."""
    try:
        days = int(request.query_params.get('days', 90))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = sanitize_json_payload(TrackingErrorService().calculate(days=days))
        result['metadata'] = build_metric_metadata(
            methodology='Tracking Error as annualized std(active return) and Information Ratio as active return / tracking error',
            data_basis='Portfolio returns from snapshots and benchmark configuration',
            limitations='Benchmark proxies may not fully match investable universe',
            extra={
                'details': {
                    'tracking_error': 'std(portfolio_return - benchmark_return) * sqrt(252)',
                    'information_ratio': '(portfolio_return - benchmark_return) / tracking_error',
                },
                'benchmark_config': 'ParametrosBenchmark',
            },
        )
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "alerts_active")


@api_view(['GET'])
def metrics_benchmark_curve(request):
    """Obtiene curva normalizada portafolio vs benchmark compuesto."""
    try:
        days = int(request.query_params.get('days', 365))
    except ValueError:
        return Response(
            {'error': 'Parametro days debe ser un numero entero valido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = sanitize_json_payload(TrackingErrorService().build_comparison_curve(days=days))
        result['metadata'] = build_metric_metadata(
            methodology='Normalized cumulative comparison between portfolio returns and composite benchmark returns',
            data_basis='PortfolioSnapshot.total_iol returns + benchmark configuration + local macro liquidity reference',
            limitations='Curve requires overlapping history and may downgrade to weekly frequency when daily benchmark depth is insufficient',
        )
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_benchmark_curve")


@api_view(['GET'])
def metrics_liquidity(request):
    """Obtiene métricas de liquidez operativa y días de liquidación estimados."""
    try:
        liquidity = LiquidityService().analyze_portfolio_liquidity()
        liquidity["metadata"] = build_metric_metadata(
            methodology='Liquidity score and liquidation horizon from instrument proxies',
            data_basis='Current portfolio positions and static liquidity assumptions',
            limitations='Uses estimated volume/spread proxies, not real-time market microstructure',
            extra={
                "details": {
                    "liquidity_score": "score 0-100 basado en tipo, volumen proxy y spread estimado",
                    "days_to_liquidate": "valor_portafolio / capacidad_diaria_estimada",
                }
            },
        )
        return Response(liquidity, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_liquidity")


@api_view(['GET'])
def metrics_data_quality(request):
    """Obtiene reporte de calidad de metadata para activos."""
    try:
        report = MetadataAuditService().run_audit()
        report["metadata"] = build_metric_metadata(
            methodology='Rule-based metadata completeness and consistency audit',
            data_basis='Activos + ParametroActivo',
            limitations='Detects structural metadata issues, not semantic classification quality',
            extra={
                "details": {
                    "unclassified": "Activos sin ParametroActivo",
                    "inconsistent": "Sector/pais vacios o tipo patrimonial invalido",
                }
            },
        )
        return Response(report, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_data_quality")

@api_view(['GET'])
@permission_classes([IsAdminUser])
def metrics_snapshot_integrity(request):
    """Reporte de integridad de snapshots patrimoniales."""
    try:
        days = int(request.query_params.get('days', 120))
    except ValueError:
        return Response(
            {'error': 'Parametro days debe ser un numero entero valido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        report = SnapshotIntegrityService().run_checks(days=days)
        report["metadata"] = build_metric_metadata(
            methodology='Integrity checks for duplicates, gaps, extreme jumps and valuation consistency',
            data_basis='PortfolioSnapshot daily series',
            limitations='Threshold rules are heuristic and may require tuning by portfolio regime',
        )
        return Response(report, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_snapshot_integrity")


@api_view(['GET'])
@permission_classes([IsAdminUser])
def metrics_sync_audit(request):
    """Reporte de auditoria de sincronizacion con IOL."""
    try:
        hours = int(request.query_params.get('hours', 24))
    except ValueError:
        return Response(
            {'error': 'Parametro hours debe ser un numero entero valido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        report = IOLSyncAuditService().run_audit(freshness_hours=hours)
        report["metadata"] = build_metric_metadata(
            methodology='Operational health checks over sync freshness, token status and operations continuity',
            data_basis='IOLToken + snapshots + operaciones',
            limitations='Detects synchronization symptoms, not root causes from external API outages',
        )
        return Response(report, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "metrics_sync_audit")


@api_view(['GET'])
@permission_classes([IsAdminUser])
def metrics_internal_observability(request):
    """Resumen de metricas internas de latencia en memoria."""
    metric_names = [
        "metrics.returns.calc_ms",
        "metrics.volatility.calc_ms",
        "metrics.performance.calc_ms",
        "optimizer.risk_parity.calc_ms",
        "optimizer.markowitz.calc_ms",
        "iol.api.estado_cuenta.latency_ms",
        "iol.api.portafolio.latency_ms",
        "iol.api.operaciones.latency_ms",
    ]
    state_metric_names = [
        "analytics_v2.risk_contribution.model_variant",
        "analytics_v2.local_macro.sync_status",
    ]
    data = [get_timing_summary(name) for name in metric_names]
    state_data = [get_state_summary(name) for name in state_metric_names]
    return Response(
        {
            "metrics": data,
            "states": state_data,
            "metadata": build_metric_metadata(
                methodology='In-memory rolling summaries of internal timing metrics and model state activations',
                data_basis='Django cache timing/state series',
                limitations='Non-persistent in default cache backend and reset after cache eviction',
            ),
        },
        status=status.HTTP_200_OK,
    )

# Historical Data API
@api_view(['GET'])
def historical_portfolio_evolution(request):
    """Obtiene evolución histórica del portafolio."""
    try:
        days = int(request.query_params.get('days', 90))
    except ValueError:
        return Response(
            {'error': 'Parámetro days debe ser un número entero válido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    try:
        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha').values(
            'fecha', 'total_iol', 'portafolio_invertido',
            'rendimiento_total', 'liquidez_operativa', 'cash_management',
            'total_patrimonio_modelado', 'cash_disponible_broker', 'caucion_colocada'
        )

        data = [_serialize_historical_snapshot(item) for item in snapshots]
        if len(data) >= 2:
            return Response(data, status=status.HTTP_200_OK)

        # Fallback: reconstruir desde snapshots operativos (Activo/Resumen)
        evolution = get_evolucion_historica(days=days, max_points=days)
        if not evolution.get('tiene_datos'):
            return Response(data, status=status.HTTP_200_OK)

        normalized = []
        fechas = evolution.get('fechas', [])
        total_iol = evolution.get('total_iol', [])
        portafolio_invertido = evolution.get('portafolio_invertido', [])
        liquidez_operativa = evolution.get('liquidez_operativa', [])
        cash_management = evolution.get('cash_management', [])
        for idx, fecha in enumerate(fechas):
            normalized.append(
                _serialize_historical_snapshot(
                    {
                        'fecha': fecha,
                        'total_iol': total_iol[idx] if idx < len(total_iol) else 0,
                        'portafolio_invertido': (
                            portafolio_invertido[idx] if idx < len(portafolio_invertido) else 0
                        ),
                        'rendimiento_total': 0,
                        'liquidez_operativa': (
                            liquidez_operativa[idx] if idx < len(liquidez_operativa) else 0
                        ),
                        'cash_management': cash_management[idx] if idx < len(cash_management) else 0,
                    },
                    fallback=True,
                )
            )
        return Response(normalized, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "alerts_by_severity")

@api_view(['GET'])
def historical_portfolio_summary(request):
    """Obtiene resumen histórico del portafolio."""
    try:
        # Último snapshot
        latest = PortfolioSnapshot.objects.order_by('-fecha').first()
        if not latest:
            return Response({}, status=status.HTTP_200_OK)

        # Estadísticas del último mes
        month_ago = timezone.now() - timedelta(days=30)
        monthly_snapshots = PortfolioSnapshot.objects.filter(
            fecha__gte=month_ago
        )

        summary = {
            'latest_snapshot': _serialize_historical_snapshot(latest),
            'monthly_stats': {
                'count': monthly_snapshots.count(),
                'avg_performance': monthly_snapshots.aggregate(
                    avg=Avg('rendimiento_total')
                )['avg'] or 0,
            }
        }

        return Response(summary, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "rebalance_suggestions")

# P4 - Strategy & Optimization API

# Simulation API
@api_view(['POST'])
def simulation_purchase(request):
    """Simula compra de un activo."""
    from apps.core.services.portfolio_simulator import PortfolioSimulator

    activo_symbol = request.data.get('activo')
    capital = request.data.get('capital')

    if not activo_symbol or capital in (None, ""):
        return Response(
            {'error': 'Se requieren activo y capital'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        activo_symbol = _validate_symbol(activo_symbol)
        capital = _coerce_positive_number(capital, field_name="capital", max_value=MAX_MONETARY_INPUT)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_purchase(activo_symbol, capital, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "rebalance_critical_actions")

@api_view(['POST'])
def simulation_sale(request):
    """Simula venta de un activo."""
    from apps.core.services.portfolio_simulator import PortfolioSimulator

    activo_symbol = request.data.get('activo')
    cantidad = request.data.get('cantidad')

    if not activo_symbol or cantidad in (None, ""):
        return Response(
            {'error': 'Se requieren activo y cantidad'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        activo_symbol = _validate_symbol(activo_symbol)
        cantidad = _coerce_positive_number(cantidad, field_name="cantidad", max_value=MAX_QUANTITY_INPUT)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_sale(activo_symbol, cantidad, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "rebalance_opportunity_actions")

@api_view(['POST'])
def simulation_rebalance(request):
    """Simula rebalanceo completo."""
    from apps.core.services.portfolio_simulator import PortfolioSimulator

    target_weights = request.data.get('target_weights', {})

    if not target_weights:
        return Response(
            {'error': 'Se requieren pesos objetivo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        target_weights = _validate_weight_mapping(target_weights, field_name="pesos objetivo")
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_rebalance(target_weights, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "historical_portfolio_evolution")

# Optimization API
@api_view(['POST'])
def optimizer_risk_parity(request):
    """Optimización Risk Parity."""
    from apps.core.services.portfolio_optimizer import PortfolioOptimizer

    activos = request.data.get('activos', [])
    target_return = request.data.get('target_return')

    if not activos:
        return Response(
            {'error': 'Se requieren activos'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        activos = _validate_symbol_list(activos)
        target_return = _coerce_target_return(target_return) if target_return is not None else None
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_risk_parity(activos, target_return)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "historical_portfolio_summary")

@api_view(['POST'])
def optimizer_markowitz(request):
    """Optimización Markowitz."""
    from apps.core.services.portfolio_optimizer import PortfolioOptimizer

    activos = request.data.get('activos', [])
    target_return = request.data.get('target_return')

    if not activos or target_return in (None, ""):
        return Response(
            {'error': 'Se requieren activos y retorno objetivo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        activos = _validate_symbol_list(activos)
        target_return = _coerce_target_return(target_return)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_markowitz(activos, target_return)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "optimizer_markowitz")

@api_view(['POST'])
def optimizer_target_allocation(request):
    """Optimización por asignación objetivo."""
    from apps.core.services.portfolio_optimizer import PortfolioOptimizer

    target_allocations = request.data.get('target_allocations', {})

    if not target_allocations:
        return Response(
            {'error': 'Se requieren asignaciones objetivo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        target_allocations = _validate_weight_mapping(
            target_allocations,
            field_name="asignaciones objetivo",
        )
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_target_allocation(target_allocations)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "optimizer_target_allocation")

# Recommendations API
@api_view(['GET'])
def recommendations_all(request):
    """Obtiene todas las recomendaciones."""
    from apps.core.services.recommendation_engine import RecommendationEngine

    try:
        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations()
        return Response(recommendations, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "recommendations_all")

@api_view(['GET'])
def recommendations_by_priority(request):
    """Obtiene recomendaciones filtradas por prioridad."""
    from apps.core.services.recommendation_engine import RecommendationEngine

    priority = request.query_params.get('priority', 'alta')

    try:
        engine = RecommendationEngine()
        all_recommendations = engine.generate_recommendations()
        filtered = [r for r in all_recommendations if r.get('prioridad') == priority]
        return Response(filtered, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "recommendations_by_priority")

# Monthly Investment Planner API
@api_view(['POST'])
def monthly_plan_basic(request):
    """Crea plan de inversión mensual básico."""
    from apps.core.services.monthly_investment_planner import MonthlyInvestmentPlanner

    monthly_amount = request.data.get('monthly_amount')

    if not monthly_amount:
        return Response(
            {'error': 'Se requiere monto mensual'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        planner = MonthlyInvestmentPlanner()
        current_portfolio = get_dashboard_kpis()
        result = planner.plan_monthly_investment(monthly_amount, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "monthly_plan_basic")

@api_view(['POST'])
def monthly_plan_custom(request):
    """Crea plan de inversión mensual personalizado."""
    from apps.core.services.monthly_investment_planner import MonthlyInvestmentPlanner

    monthly_amount = request.data.get('monthly_amount')
    risk_profile = request.data.get('risk_profile', 'moderado')
    investment_horizon = request.data.get('investment_horizon', 'medio')

    if not monthly_amount:
        return Response(
            {'error': 'Se requiere monto mensual'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        planner = MonthlyInvestmentPlanner()
        current_portfolio = get_dashboard_kpis()
        result = planner.create_custom_plan(
            monthly_amount, risk_profile, investment_horizon, current_portfolio
        )
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "monthly_plan_custom")

# Portfolio Parameters API
@api_view(['GET'])
def portfolio_parameters_get(request):
    """Obtiene parámetros actuales del portafolio."""
    from apps.core.models import PortfolioParameters

    try:
        params = PortfolioParameters.get_active_parameters()
        if not params:
            return Response(
                {'error': 'No hay parámetros activos'},
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            'id': params.id,
            'name': params.name,
            'liquidez_target': float(params.liquidez_target),
            'usa_target': float(params.usa_target),
            'argentina_target': float(params.argentina_target),
            'emerging_target': float(params.emerging_target),
            'max_single_position': float(params.max_single_position),
            'risk_free_rate': float(params.risk_free_rate),
            'rebalance_threshold': float(params.rebalance_threshold),
            'is_valid': params.is_valid_allocation(),
            'total_allocation': float(params.total_target_allocation)
        }
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return internal_error_response(e, "portfolio_parameters_get")

@api_view(['POST'])
def portfolio_parameters_update(request):
    """Actualiza parametros globales del portafolio."""
    from decimal import Decimal

    from apps.core.models import PortfolioParameters

    try:
        if not request.user or not request.user.is_staff:
            record_sensitive_action(
                request,
                action='portfolio_parameters_update',
                status='denied',
                details={'reason': 'non_staff_user'},
            )
            return Response(
                {'error': 'No autorizado para modificar parametros globales'},
                status=status.HTTP_403_FORBIDDEN,
            )

        params = PortfolioParameters.get_active_parameters()
        if not params:
            params = PortfolioParameters()

        params.name = request.data.get('name', params.name)
        params.liquidez_target = Decimal(
            str(request.data.get('liquidez_target', params.liquidez_target))
        )
        params.usa_target = Decimal(str(request.data.get('usa_target', params.usa_target)))
        params.argentina_target = Decimal(
            str(request.data.get('argentina_target', params.argentina_target))
        )
        params.emerging_target = Decimal(
            str(request.data.get('emerging_target', params.emerging_target))
        )
        params.max_single_position = Decimal(
            str(request.data.get('max_single_position', params.max_single_position))
        )
        params.risk_free_rate = Decimal(
            str(request.data.get('risk_free_rate', params.risk_free_rate))
        )
        params.rebalance_threshold = Decimal(
            str(request.data.get('rebalance_threshold', params.rebalance_threshold))
        )

        if not params.is_valid_allocation():
            record_sensitive_action(
                request,
                action='portfolio_parameters_update',
                status='failed',
                details={
                    'reason': 'invalid_allocation',
                    'total_allocation': float(params.total_target_allocation),
                },
            )
            return Response(
                {
                    'error': (
                        'La asignacion objetivo debe sumar 100%. '
                        f'Actualmente suma {params.total_target_allocation}%.'
                    ),
                    'total_allocation': float(params.total_target_allocation),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        params.save()
        record_sensitive_action(
            request,
            action='portfolio_parameters_update',
            status='success',
            details={
                'portfolio_parameters_id': params.id,
                'name': params.name,
                'total_allocation': float(params.total_target_allocation),
            },
        )
        return Response(
            {'message': 'Par?metros actualizados correctamente'},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        record_sensitive_action(
            request,
            action='portfolio_parameters_update',
            status='failed',
            details={'reason': 'exception'},
        )
        return internal_error_response(e, "portfolio_parameters_update")


