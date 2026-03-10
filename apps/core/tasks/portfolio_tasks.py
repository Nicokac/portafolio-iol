import logging
from datetime import datetime

from celery import shared_task
from django.utils import timezone

from apps.core.services.alerts_engine import AlertsEngine
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.core.services.rebalance_engine import RebalanceEngine
from apps.core.services.temporal_metrics_service import TemporalMetricsService

logger = logging.getLogger(__name__)


@shared_task
def sync_portfolio_data():
    """
    Tarea programada: Sincronizar datos del portafolio desde IOL API cada 30 minutos.
    """
    logger.info("Starting scheduled portfolio data sync")

    try:
        service = PortfolioSnapshotService()
        result = service.sync_iol_data()

        if result['success']:
            logger.info(f"Portfolio sync completed successfully: {result['message']}")
        else:
            logger.error(f"Portfolio sync failed: {result['message']}")

        return result

    except Exception as e:
        logger.error(f"Error in portfolio sync task: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def generate_daily_snapshot():
    """
    Tarea programada: Generar snapshot diario del portafolio a las 6:00 AM.
    """
    logger.info("Starting daily snapshot generation")

    try:
        service = PortfolioSnapshotService()
        result = service.generate_daily_snapshot()

        if result['success']:
            logger.info(f"Daily snapshot generated successfully: {result['message']}")
        else:
            logger.error(f"Daily snapshot generation failed: {result['message']}")

        return result

    except Exception as e:
        logger.error(f"Error in daily snapshot task: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def generate_alerts():
    """
    Tarea programada: Generar alertas del portafolio cada hora.
    """
    logger.info("Starting alerts generation")

    try:
        engine = AlertsEngine()
        alerts = engine.generate_alerts()

        # Aquí se podrían guardar las alertas en BD o enviar notificaciones
        # Por ahora solo logueamos
        for alert in alerts:
            logger.warning(f"ALERT [{alert['severidad'].upper()}]: {alert['mensaje']}")

        result = {
            'success': True,
            'message': f'Generated {len(alerts)} alerts',
            'alerts_count': len(alerts)
        }

        logger.info(f"Alerts generation completed: {result['message']}")
        return result

    except Exception as e:
        logger.error(f"Error in alerts generation task: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def calculate_temporal_metrics():
    """
    Tarea programada: Calcular métricas temporales cada 4 horas.
    """
    logger.info("Starting temporal metrics calculation")

    try:
        service = TemporalMetricsService()

        # Calcular métricas para diferentes períodos
        periods = [7, 30, 90, 180]
        results = {}

        for period in periods:
            returns = service.get_portfolio_returns(period)
            volatility = service.get_portfolio_volatility(period)

            results[f'{period}d'] = {
                'returns': returns,
                'volatility': volatility
            }

        # Aquí se podrían cachear o guardar las métricas
        logger.info(f"Temporal metrics calculated for periods: {list(results.keys())}")

        result = {
            'success': True,
            'message': f'Calculated metrics for {len(periods)} periods',
            'periods_calculated': periods
        }

        return result

    except Exception as e:
        logger.error(f"Error in temporal metrics calculation: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def generate_rebalance_suggestions():
    """
    Tarea programada: Generar sugerencias de rebalanceo (ejecutar manualmente o programar).
    """
    logger.info("Starting rebalance suggestions generation")

    try:
        engine = RebalanceEngine()
        suggestions = engine.generate_rebalance_suggestions()

        # Log sugerencias críticas
        critical_actions = engine.get_critical_actions()
        for action in critical_actions:
            logger.warning(f"CRITICAL REBALANCE ACTION: {action}")

        result = {
            'success': True,
            'message': f'Generated {len(suggestions)} rebalance suggestions',
            'suggestions_count': len(suggestions),
            'critical_actions_count': len(critical_actions)
        }

        logger.info(f"Rebalance suggestions completed: {result['message']}")
        return result

    except Exception as e:
        logger.error(f"Error in rebalance suggestions task: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def comprehensive_portfolio_update():
    """
    Tarea compuesta: Ejecutar actualización completa del portafolio.
    Incluye sync, snapshot, alertas, métricas y rebalanceo.
    Llama a las subtareas de forma asíncrona para no bloquear workers.
    """
    logger.info("Starting comprehensive portfolio update")

    # 1. Sincronizar datos
    sync_result = sync_portfolio_data.delay()

    # 2. Generar snapshot si es hora (6 AM)
    now = timezone.now()
    snapshot_result = None
    if now.hour == 6:
        snapshot_result = generate_daily_snapshot.delay()

    # 3. Generar alertas
    alerts_result = generate_alerts.delay()

    # 4. Calcular métricas
    metrics_result = calculate_temporal_metrics.delay()

    # 5. Generar sugerencias de rebalanceo
    rebalance_result = generate_rebalance_suggestions.delay()

    # Devolver IDs de las tareas lanzadas para seguimiento
    task_ids = {
        'sync': sync_result.id,
        'alerts': alerts_result.id,
        'metrics': metrics_result.id,
        'rebalance': rebalance_result.id
    }

    if snapshot_result:
        task_ids['snapshot'] = snapshot_result.id

    result = {
        'success': True,
        'message': f'Launched {len(task_ids)} asynchronous tasks',
        'task_ids': task_ids,
        'snapshot_launched': snapshot_result is not None
    }

    logger.info(f"Comprehensive portfolio update launched: {result['message']}")
    return result