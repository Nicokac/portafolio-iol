import logging
from datetime import datetime

from celery import shared_task
from django.utils import timezone

from apps.core.models import Alert
from apps.core.services.alerts_engine import AlertsEngine
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.observability import record_state
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.core.services.rebalance_engine import RebalanceEngine
from apps.core.services.temporal_metrics_service import TemporalMetricsService

logger = logging.getLogger(__name__)

DEFAULT_ALERT_TYPE = 'concentracion_excesiva'
DEFAULT_ALERT_SEVERITY = 'warning'
SEVERITY_MAP = {
    'high': 'critical',
    'medium': 'warning',
    'low': 'info',
}


def _normalize_alert(alert_data: dict) -> dict:
    """Normaliza payload de alerta para prevenir fallos por claves ausentes."""
    data = dict(alert_data or {})
    data['tipo'] = data.get('tipo') or DEFAULT_ALERT_TYPE
    data['mensaje'] = data.get('mensaje') or 'Alerta sin detalle'

    raw_severity = str(data.get('severidad', DEFAULT_ALERT_SEVERITY)).lower()
    mapped = SEVERITY_MAP.get(raw_severity, raw_severity)
    data['severidad'] = mapped if mapped in {'info', 'warning', 'critical'} else DEFAULT_ALERT_SEVERITY
    return data


@shared_task
def sync_portfolio_data():
    """
    Tarea programada: Sincronizar datos del portafolio desde IOL API cada 30 minutos.
    """
    logger.info("Starting scheduled portfolio data sync")

    try:
        service = PortfolioSnapshotService()
        raw_result = service.sync_iol_data()
        if isinstance(raw_result, dict):
            result = raw_result
        else:
            result = {
                'success': bool(raw_result),
                'message': 'Sync OK' if raw_result else 'Sync failed',
            }

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
        raw_result = service.generate_daily_snapshot()
        if isinstance(raw_result, dict):
            result = raw_result
        else:
            snapshot_date = getattr(raw_result, 'fecha', None)
            result = {
                'success': raw_result is not None,
                'message': f'Snapshot generated for {snapshot_date}' if raw_result else 'Snapshot failed',
            }

        if result['success']:
            logger.info(f"Daily snapshot generated successfully: {result['message']}")
        else:
            logger.error(f"Daily snapshot generation failed: {result['message']}")

        return result

    except Exception as e:
        logger.error(f"Error in daily snapshot task: {str(e)}")
        return {'success': False, 'message': str(e)}


@shared_task
def sync_local_macro_series():
    """
    Tarea programada: Sincronizar referencias macro locales, incluido USDARS MEP si la fuente opcional existe.
    """
    logger.info("Starting local macro series sync")

    try:
        result = LocalMacroSeriesService().sync_all()
        summary = LocalMacroSeriesService.summarize_sync_result(result)
        record_state(summary["metric_name"], summary["state"], summary["extra"])
        has_hard_failures = any(
            payload.get("success") is False
            for payload in result.values()
            if isinstance(payload, dict)
        )
        synced = ", ".join(
            f"{series_key}: rows={payload.get('rows_received', 0)}"
            for series_key, payload in result.items()
        )

        if has_hard_failures:
            logger.error(f"Local macro sync completed with failures: {synced}")
        else:
            logger.info(f"Local macro sync completed: {synced}")

        return {
            "success": not has_hard_failures,
            "message": synced,
            "series": result,
        }

    except Exception as e:
        record_state(
            LocalMacroSeriesService.SYNC_STATE_METRIC,
            "failed",
            {"reason": str(e), "synced_series": [], "skipped_series": [], "failed_series": ["task_exception"]},
        )
        logger.error(f"Error in local macro sync task: {str(e)}")
        return {"success": False, "message": str(e)}


@shared_task
def sync_iol_historical_prices():
    """
    Tarea programada: sincronizar históricos IOL para los símbolos actuales del portfolio.
    """
    logger.info("Starting IOL historical prices sync")

    try:
        result = IOLHistoricalPriceService().sync_current_portfolio_symbols()
        if result.get("success", True):
            logger.info(
                "IOL historical prices sync completed: processed=%s symbols=%s",
                result.get("processed", 0),
                result.get("symbols_count", 0),
            )
        else:
            logger.error(
                "IOL historical prices sync completed with failures: processed=%s symbols=%s",
                result.get("processed", 0),
                result.get("symbols_count", 0),
            )

        return {
            "success": bool(result.get("success", True)),
            "message": (
                f"processed={result.get('processed', 0)} symbols={result.get('symbols_count', 0)}"
            ),
            "results": result.get("results", {}),
            "symbols_count": result.get("symbols_count", 0),
            "processed": result.get("processed", 0),
        }
    except Exception as e:
        logger.error(f"Error in IOL historical prices sync task: {str(e)}")
        return {"success": False, "message": str(e), "results": {}, "symbols_count": 0, "processed": 0}


@shared_task
def generate_alerts():
    """
    Tarea programada: Generar alertas del portafolio cada hora.
    """
    logger.info("Starting alerts generation")

    try:
        engine = AlertsEngine()
        raw_alerts_data = engine.generate_alerts()
        alerts_data = [_normalize_alert(alert) for alert in raw_alerts_data]

        # Guardar alertas en BD
        saved_alerts = []
        for alert_data in alerts_data:
            # Verificar si ya existe una alerta similar activa
            existing_alert = Alert.objects.filter(
                tipo=alert_data['tipo'],
                is_active=True,
                is_acknowledged=False
            ).first()

            if not existing_alert:
                # Crear nueva alerta
                alert = Alert.objects.create(
                    tipo=alert_data['tipo'],
                    mensaje=alert_data['mensaje'],
                    severidad=alert_data['severidad'],
                    valor=alert_data.get('valor'),
                    simbolo=alert_data.get('simbolo'),
                    sector=alert_data.get('sector'),
                    pais=alert_data.get('pais')
                )
                saved_alerts.append(alert)
                logger.warning(f"NEW ALERT [{alert.severidad.upper()}]: {alert.mensaje}")
            else:
                logger.info(f"Alert already exists: {alert_data['mensaje']}")

        # Desactivar alertas que ya no se cumplen
        active_alert_types = {alert.get('tipo', DEFAULT_ALERT_TYPE) for alert in alerts_data}
        expired_alerts = Alert.objects.filter(
            is_active=True,
            is_acknowledged=False
        ).exclude(tipo__in=active_alert_types)

        for expired_alert in expired_alerts:
            expired_alert.is_active = False
            expired_alert.save()
            logger.info(f"Deactivated expired alert: {expired_alert.mensaje}")

        result = {
            'success': True,
            'message': f'Generated {len(alerts_data)} alerts, saved {len(saved_alerts)} new alerts',
            'alerts_count': len(alerts_data),
            'new_alerts_count': len(saved_alerts)
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
