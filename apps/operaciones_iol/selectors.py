from __future__ import annotations

from decimal import Decimal
from typing import Iterable
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.core.models import SensitiveActionAudit
from apps.operaciones_iol.models import OperacionIOL


_STATUS_TONE_MAP = {
    'terminada': 'success',
    'ejecutada': 'success',
    'iniciada': 'secondary',
    'pendiente': 'warning',
    'cancelada': 'danger',
    'rechazada': 'danger',
}

_DEFAULT_FILTERS = {
    'numero': '',
    'estado': 'todas',
    'fecha_desde': '',
    'fecha_hasta': '',
    'pais': 'argentina',
}


def build_operation_list_context(operaciones: Iterable[OperacionIOL]) -> dict:
    rows = [build_operation_list_row(operacion) for operacion in operaciones]
    total_count = len(rows)
    enriched_count = sum(1 for row in rows if row['has_detail'])
    country_resolved_count = sum(1 for row in rows if row['has_country'])
    country_missing_count = total_count - country_resolved_count
    argentina_count = sum(1 for row in rows if row['country_value'] == 'argentina')
    us_count = sum(1 for row in rows if row['country_value'] == 'estados_Unidos')
    fills_count = sum(1 for row in rows if row['fills_count'] > 0)
    fragmented_count = sum(1 for row in rows if row['fills_count'] > 1)
    fees_visible_count = sum(1 for row in rows if row['fees_ars'] > 0 or row['fees_usd'] > 0)
    fees_ars_total = sum((row['fees_ars'] for row in rows), Decimal('0'))
    fees_usd_total = sum((row['fees_usd'] for row in rows), Decimal('0'))
    enriched_pct = _safe_percentage(enriched_count, total_count)
    country_resolved_pct = _safe_percentage(country_resolved_count, total_count)
    fragmented_pct = _safe_percentage(fragmented_count, fills_count)
    fees_visible_pct = _safe_percentage(fees_visible_count, total_count)
    type_breakdown = _build_type_breakdown(rows, total_count)

    return {
        'rows': rows,
        'summary': {
            'total_count': total_count,
            'enriched_count': enriched_count,
            'missing_detail_count': total_count - enriched_count,
            'enriched_pct': enriched_pct,
            'country_resolved_count': country_resolved_count,
            'country_missing_count': country_missing_count,
            'country_resolved_pct': country_resolved_pct,
            'country_argentina_count': argentina_count,
            'country_estados_unidos_count': us_count,
            'fills_count': fills_count,
            'fragmented_count': fragmented_count,
            'fragmented_pct': fragmented_pct,
            'fees_visible_count': fees_visible_count,
            'fees_visible_pct': fees_visible_pct,
            'fees_ars_total': fees_ars_total,
            'fees_usd_total': fees_usd_total,
            'type_breakdown': type_breakdown,
        },
    }


def build_operation_universe_coverage_context(queryset: QuerySet[OperacionIOL]) -> dict:
    operaciones = list(queryset)
    total_count = len(operaciones)
    detail_count = sum(1 for operacion in operaciones if has_operation_detail(operacion))
    country_count = sum(1 for operacion in operaciones if str(operacion.pais_consulta or '').strip())
    argentina_count = sum(1 for operacion in operaciones if str(operacion.pais_consulta or '').strip() == 'argentina')
    us_count = sum(1 for operacion in operaciones if str(operacion.pais_consulta or '').strip() == 'estados_Unidos')

    return {
        'total_count': total_count,
        'detail_count': detail_count,
        'detail_missing_count': max(total_count - detail_count, 0),
        'detail_pct': _safe_percentage(detail_count, total_count),
        'country_count': country_count,
        'country_missing_count': max(total_count - country_count, 0),
        'country_pct': _safe_percentage(country_count, total_count),
        'country_argentina_count': argentina_count,
        'country_estados_unidos_count': us_count,
    }


def build_operation_audit_summary_context(limit: int = 3) -> dict:
    tracked_actions = [
        ('sync_operaciones_filtered', 'Sync remoto filtrado'),
        ('enrich_operaciones_filtered_details', 'Enriquecimiento de detalle'),
        ('backfill_operaciones_filtered_country', 'Backfill de pais'),
    ]
    action_map = dict(tracked_actions)
    audits = (
        SensitiveActionAudit.objects.filter(action__in=action_map.keys())
        .select_related('user')
        .order_by('-created_at', '-id')
    )

    latest_by_action: dict[str, SensitiveActionAudit] = {}
    for audit in audits:
        if audit.action not in latest_by_action:
            latest_by_action[audit.action] = audit
        if len(latest_by_action) == len(tracked_actions):
            break

    rows = []
    for action_key, label in tracked_actions[:limit]:
        audit = latest_by_action.get(action_key)
        rows.append(
            {
                'action': action_key,
                'label': label,
                'status': audit.status if audit else 'missing',
                'status_label': _build_audit_status_label(audit.status if audit else 'missing'),
                'status_tone': _build_audit_status_tone(audit.status if audit else 'missing'),
                'user_label': audit.user.username if audit and audit.user else 'system',
                'created_at_label': _format_audit_datetime(audit.created_at) if audit else 'Sin registros',
                'details': audit.details if audit else {},
            }
        )

    success_count = sum(1 for row in rows if row['status'] == 'success')
    failed_count = sum(1 for row in rows if row['status'] == 'failed')
    missing_count = sum(1 for row in rows if row['status'] == 'missing')
    return {
        'rows': rows,
        'summary': {
            'tracked_count': len(rows),
            'success_count': success_count,
            'failed_count': failed_count,
            'missing_count': missing_count,
        },
    }


def normalize_operation_filters(params) -> dict:
    params = params or {}

    def pick(*keys):
        getter = getattr(params, 'get', None)
        for key in keys:
            value = getter(key) if callable(getter) else params.get(key)
            if value not in (None, ''):
                return str(value).strip()
        return ''

    normalized = {
        'numero': pick('numero', 'filtro.numero'),
        'estado': pick('estado', 'filtro.estado') or 'todas',
        'fecha_desde': pick('fecha_desde', 'fechaDesde', 'filtro.fechaDesde'),
        'fecha_hasta': pick('fecha_hasta', 'fechaHasta', 'filtro.fechaHasta'),
        'pais': pick('pais', 'filtro.pais') or 'argentina',
    }
    if normalized['estado'] not in {'todas', 'terminada', 'iniciada', 'pendiente', 'cancelada', 'rechazada'}:
        normalized['estado'] = 'todas'
    if normalized['pais'] not in {'argentina', 'estados_Unidos'}:
        normalized['pais'] = 'argentina'
    return normalized


def apply_operation_filters(queryset: QuerySet[OperacionIOL], filters: dict) -> QuerySet[OperacionIOL]:
    numero = str(filters.get('numero') or '').strip()
    if numero:
        queryset = queryset.filter(numero__icontains=numero)

    estado = str(filters.get('estado') or 'todas').strip().lower()
    if estado and estado != 'todas':
        queryset = queryset.filter(Q(estado__iexact=estado) | Q(estado_actual__iexact=estado))

    fecha_desde = parse_date(str(filters.get('fecha_desde') or '').strip())
    if fecha_desde:
        queryset = queryset.filter(fecha_orden__date__gte=fecha_desde)

    fecha_hasta = parse_date(str(filters.get('fecha_hasta') or '').strip())
    if fecha_hasta:
        queryset = queryset.filter(fecha_orden__date__lte=fecha_hasta)

    pais = str(filters.get('pais') or '').strip()
    if pais and pais != 'argentina':
        queryset = queryset.filter(pais_consulta__iexact=pais)

    return queryset.distinct()


def build_operation_filter_context(filters: dict) -> dict:
    clean_filters = {**_DEFAULT_FILTERS, **(filters or {})}
    query_string = urlencode(
        {
            key: value
            for key, value in clean_filters.items()
            if (
                (key == 'estado' and value != 'todas')
                or (key == 'pais' and value != 'argentina')
                or (key not in {'estado', 'pais'} and value)
            )
        }
    )
    active_count = sum(
        1
        for key, value in clean_filters.items()
        if (
            (key == 'estado' and value != 'todas')
            or (key == 'pais' and value != 'argentina')
            or (key not in {'estado', 'pais'} and value)
        )
    )
    return {
        'values': clean_filters,
        'active_count': active_count,
        'has_active_filters': active_count > 0,
        'query_string': query_string,
        'estado_options': [
            ('todas', 'Todas'),
            ('terminada', 'Terminadas'),
            ('pendiente', 'Pendientes'),
            ('iniciada', 'Iniciadas'),
            ('cancelada', 'Canceladas'),
            ('rechazada', 'Rechazadas'),
        ],
        'pais_options': [
            ('argentina', 'Argentina'),
            ('estados_Unidos', 'Estados Unidos'),
        ],
    }


def get_operation_subset_for_detail_enrichment(
    queryset: QuerySet[OperacionIOL],
    *,
    page_number: int | str = 1,
    page_size: int = 25,
) -> list[OperacionIOL]:
    page = Paginator(queryset, page_size).get_page(page_number)
    return [operacion for operacion in page.object_list if not has_operation_detail(operacion)]


def get_operation_subset_for_country_backfill(
    queryset: QuerySet[OperacionIOL],
    *,
    page_number: int | str = 1,
    page_size: int = 25,
) -> list[OperacionIOL]:
    page = Paginator(queryset, page_size).get_page(page_number)
    return [operacion for operacion in page.object_list if not str(operacion.pais_consulta or '').strip()]



def build_operation_list_row(operacion: OperacionIOL) -> dict:
    has_detail = has_operation_detail(operacion)
    country_value = str(operacion.pais_consulta or '').strip()
    fills = list(operacion.operaciones_detalle or [])
    fill_count = len(fills)
    fees_ars = Decimal(str(operacion.aranceles_ars or 0))
    fees_usd = Decimal(str(operacion.aranceles_usd or 0))
    execution_label = _build_execution_label(fill_count, has_detail)

    return {
        'operacion': operacion,
        'has_detail': has_detail,
        'has_country': bool(country_value),
        'country_value': country_value,
        'country_label': _build_country_label(country_value),
        'detail_status': 'enriched' if has_detail else 'local_only',
        'detail_status_label': 'Enriquecido' if has_detail else 'Solo local',
        'detail_tone': 'success' if has_detail else 'secondary',
        'fills_count': fill_count,
        'execution_label': execution_label,
        'execution_tone': 'warning' if fill_count > 1 else 'secondary',
        'fees_ars': fees_ars,
        'fees_usd': fees_usd,
        'status_tone': _build_status_tone(operacion.estado_actual or operacion.estado),
    }



def has_operation_detail(operacion: OperacionIOL) -> bool:
    return any(
        [
            bool(operacion.moneda),
            bool(operacion.estado_actual),
            bool(operacion.fecha_alta),
            bool(operacion.validez),
            bool(operacion.estados_detalle),
            bool(operacion.aranceles_detalle),
            bool(operacion.operaciones_detalle),
            operacion.monto_operacion is not None,
            operacion.aranceles_ars is not None,
            operacion.aranceles_usd is not None,
        ]
    )



def _build_execution_label(fill_count: int, has_detail: bool) -> str:
    if fill_count > 1:
        return 'Multiples fills'
    if fill_count == 1:
        return 'Fill unico'
    if has_detail:
        return 'Sin fills'
    return 'Sin detalle'



def _build_status_tone(status: str | None) -> str:
    normalized = str(status or '').strip().lower()
    return _STATUS_TONE_MAP.get(normalized, 'secondary')


def _build_country_label(country_value: str) -> str:
    if country_value == 'argentina':
        return 'Argentina'
    if country_value == 'estados_Unidos':
        return 'Estados Unidos'
    return 'Pendiente'


def _safe_percentage(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal('0')
    return (Decimal(numerator) / Decimal(denominator) * Decimal('100')).quantize(Decimal('0.01'))


def _build_type_breakdown(rows: list[dict], total_count: int) -> list[dict]:
    counts: dict[str, int] = {}
    for row in rows:
        tipo = str(row['operacion'].tipo or 'Sin tipo').strip() or 'Sin tipo'
        counts[tipo] = counts.get(tipo, 0) + 1

    breakdown = [
        {
            'tipo': tipo,
            'count': count,
            'pct': _safe_percentage(count, total_count),
        }
        for tipo, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return breakdown[:4]


def _build_audit_status_label(status: str) -> str:
    if status == 'success':
        return 'OK'
    if status == 'failed':
        return 'Fallo'
    return 'Sin registro'


def _build_audit_status_tone(status: str) -> str:
    if status == 'success':
        return 'success'
    if status == 'failed':
        return 'danger'
    return 'secondary'


def _format_audit_datetime(value) -> str:
    if value is None:
        return 'Sin registros'
    localized = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized.strftime('%Y-%m-%d %H:%M')
