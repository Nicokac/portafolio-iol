from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.core.services.alerts_engine import AlertsEngine
from apps.core.services.rebalance_engine import RebalanceEngine
from apps.core.services.temporal_metrics_service import TemporalMetricsService
from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_sector,
    get_dashboard_kpis,
    get_senales_rebalanceo,
)
from apps.portafolio_iol.models import PortfolioSnapshot


# Dashboard API
@api_view(['GET'])
def dashboard_kpis(request):
    """Obtiene KPIs principales del dashboard."""
    try:
        kpis = get_dashboard_kpis()
        return Response(kpis, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def dashboard_concentracion_pais(request):
    """Obtiene concentración por país."""
    try:
        data = get_concentracion_pais()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def dashboard_concentracion_sector(request):
    """Obtiene concentración por sector."""
    try:
        data = get_concentracion_sector()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def dashboard_senales_rebalanceo(request):
    """Obtiene señales de rebalanceo."""
    try:
        data = get_senales_rebalanceo()
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Alerts API
@api_view(['GET'])
def alerts_active(request):
    """Obtiene todas las alertas activas."""
    try:
        engine = AlertsEngine()
        alerts = engine.generate_alerts()
        return Response(alerts, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def alerts_by_severity(request):
    """Obtiene alertas filtradas por severidad."""
    severity = request.query_params.get('severity', 'warning')
    try:
        engine = AlertsEngine()
        alerts = engine.get_alerts_by_severity(severity)
        return Response(alerts, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Rebalance API
@api_view(['GET'])
def rebalance_suggestions(request):
    """Obtiene sugerencias de rebalanceo."""
    try:
        engine = RebalanceEngine()
        suggestions = engine.generate_rebalance_suggestions()
        return Response(suggestions, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def rebalance_critical_actions(request):
    """Obtiene acciones críticas de rebalanceo."""
    try:
        engine = RebalanceEngine()
        actions = engine.get_critical_actions()
        return Response(actions, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def rebalance_opportunity_actions(request):
    """Obtiene acciones de oportunidad de rebalanceo."""
    try:
        engine = RebalanceEngine()
        actions = engine.get_opportunity_actions()
        return Response(actions, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Temporal Metrics API
@api_view(['GET'])
def metrics_returns(request):
    """Obtiene retornos del portafolio."""
    days = int(request.query_params.get('days', 30))
    try:
        service = TemporalMetricsService()
        returns = service.get_portfolio_returns(days)
        return Response(returns, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def metrics_volatility(request):
    """Obtiene volatilidad del portafolio."""
    days = int(request.query_params.get('days', 30))
    try:
        service = TemporalMetricsService()
        volatility = service.get_portfolio_volatility(days)
        return Response(volatility, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def metrics_performance(request):
    """Obtiene métricas de performance completas."""
    days = int(request.query_params.get('days', 90))
    try:
        service = TemporalMetricsService()
        metrics = service.get_performance_metrics(days)
        return Response(metrics, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def metrics_historical_comparison(request):
    """Obtiene comparación histórica de performance."""
    periods = request.query_params.get('periods', '7,30,90,180')
    periods = [int(p) for p in periods.split(',')]
    try:
        service = TemporalMetricsService()
        comparison = service.get_historical_comparison(periods)
        return Response(comparison, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Historical Data API
@api_view(['GET'])
def historical_portfolio_evolution(request):
    """Obtiene evolución histórica del portafolio."""
    days = int(request.query_params.get('days', 90))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    try:
        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by('fecha').values(
            'fecha', 'total_iol', 'total_portafolio',
            'rendimiento_diario', 'liquidez_operativa'
        )

        data = list(snapshots)
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
            'latest_snapshot': {
                'fecha': latest.fecha,
                'total_iol': latest.total_iol,
                'total_portafolio': latest.total_portafolio,
                'rendimiento_diario': latest.rendimiento_diario,
                'liquidez_operativa': latest.liquidez_operativa,
            },
            'monthly_stats': {
                'count': monthly_snapshots.count(),
                'avg_performance': monthly_snapshots.aggregate(
                    avg=Avg('rendimiento_diario')
                )['avg'] or 0,
            }
        }

        return Response(summary, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# P4 - Strategy & Optimization API

# Simulation API
@api_view(['POST'])
def simulation_purchase(request):
    """Simula compra de un activo."""
    from apps.core.services.portfolio_simulator import PortfolioSimulator

    activo_symbol = request.data.get('activo')
    capital = request.data.get('capital')

    if not activo_symbol or not capital:
        return Response(
            {'error': 'Se requieren activo y capital'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_purchase(activo_symbol, capital, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def simulation_sale(request):
    """Simula venta de un activo."""
    from apps.core.services.portfolio_simulator import PortfolioSimulator

    activo_symbol = request.data.get('activo')
    cantidad = request.data.get('cantidad')

    if not activo_symbol or not cantidad:
        return Response(
            {'error': 'Se requieren activo y cantidad'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_sale(activo_symbol, cantidad, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        simulator = PortfolioSimulator()
        current_portfolio = get_dashboard_kpis()
        result = simulator.simulate_rebalance(target_weights, current_portfolio)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_risk_parity(activos, target_return)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def optimizer_markowitz(request):
    """Optimización Markowitz."""
    from apps.core.services.portfolio_optimizer import PortfolioOptimizer

    activos = request.data.get('activos', [])
    target_return = request.data.get('target_return')

    if not activos or not target_return:
        return Response(
            {'error': 'Se requieren activos y retorno objetivo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_markowitz(activos, target_return)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_target_allocation(target_allocations)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def portfolio_parameters_update(request):
    """Actualiza parámetros del portafolio."""
    from apps.core.models import PortfolioParameters
    from decimal import Decimal

    try:
        # Obtener parámetros actuales o crear nuevos
        params = PortfolioParameters.get_active_parameters()
        if not params:
            params = PortfolioParameters()

        # Actualizar campos
        params.name = request.data.get('name', params.name)
        params.liquidez_target = Decimal(str(request.data.get('liquidez_target', params.liquidez_target)))
        params.usa_target = Decimal(str(request.data.get('usa_target', params.usa_target)))
        params.argentina_target = Decimal(str(request.data.get('argentina_target', params.argentina_target)))
        params.emerging_target = Decimal(str(request.data.get('emerging_target', params.emerging_target)))
        params.max_single_position = Decimal(str(request.data.get('max_single_position', params.max_single_position)))
        params.risk_free_rate = Decimal(str(request.data.get('risk_free_rate', params.risk_free_rate)))
        params.rebalance_threshold = Decimal(str(request.data.get('rebalance_threshold', params.rebalance_threshold)))

        params.save()

        return Response(
            {'message': 'Parámetros actualizados correctamente'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )