from decimal import Decimal
from typing import Dict, List

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.dashboard.operation_execution import classify_operation_type, get_effective_operation_amount
from apps.operaciones_iol.models import OperacionIOL
from apps.parametros.models import ConfiguracionDashboard

_APORTE_MENSUAL_OBJETIVO_DEFAULT = Decimal('50000')
_ESTADOS_TERMINADA = ['terminada', 'Terminada', 'TERMINADA']
_MAX_RECENT_OPERATIONS = 5


def _process_operaciones(operaciones_list: list, aporte_mensual_objetivo: Decimal) -> Dict:
    """Procesa una lista de operaciones y calcula metricas mensuales. Funcion pura."""
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
    recent_operations: List[Dict] = []

    for op in operaciones_list:
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

        if len(recent_operations) < _MAX_RECENT_OPERATIONS:
            event_at = op.fecha_operada or op.fecha_orden
            recent_operations.append({
                'numero': op.numero,
                'simbolo': op.simbolo,
                'tipo': op.tipo,
                'tipo_key': operation_type_key,
                'estado': op.estado_actual or op.estado,
                'fecha_label': timezone.localtime(event_at).strftime('%Y-%m-%d %H:%M') if event_at else '',
                'monto': effective_amount,
                'plazo': op.plazo or '',
                'moneda': op.moneda or '',
            })

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
        'operaciones_ejecutadas_count': len(operaciones_list),
        'aporte_mensual_ejecutado': aporte_ejecutado,
        'aporte_pendiente': max(Decimal('0'), aporte_pendiente),
        'recent_operations': recent_operations,
    }


def build_analytics_mensual() -> Dict:
    """Calcula metricas operativas del mes actual a partir de operaciones ejecutadas."""
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin_mes = (inicio_mes + relativedelta(months=1)) - timezone.timedelta(seconds=1)

    operaciones_mes = OperacionIOL.objects.filter(
        fecha_operada__gte=inicio_mes,
        fecha_operada__lte=fin_mes,
        estado__in=_ESTADOS_TERMINADA,
    )

    if not operaciones_mes.exists():
        operaciones_mes = OperacionIOL.objects.filter(
            fecha_orden__gte=inicio_mes,
            fecha_orden__lte=fin_mes,
            estado__in=_ESTADOS_TERMINADA,
        )

    operaciones_list = list(operaciones_mes.order_by('-fecha_operada', '-fecha_orden'))

    try:
        config = ConfiguracionDashboard.objects.get(clave='contribucion_mensual')
        aporte_mensual_objetivo = Decimal(str(float(config.valor)))
    except (ConfiguracionDashboard.DoesNotExist, ValueError):
        aporte_mensual_objetivo = _APORTE_MENSUAL_OBJETIVO_DEFAULT

    return _process_operaciones(operaciones_list, aporte_mensual_objetivo)
