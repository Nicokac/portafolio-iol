from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from apps.operaciones_iol.models import OperacionIOL


_STATUS_TONE_MAP = {
    'terminada': 'success',
    'ejecutada': 'success',
    'iniciada': 'secondary',
    'pendiente': 'warning',
    'cancelada': 'danger',
    'rechazada': 'danger',
}


def build_operation_list_context(operaciones: Iterable[OperacionIOL]) -> dict:
    rows = [build_operation_list_row(operacion) for operacion in operaciones]
    total_count = len(rows)
    enriched_count = sum(1 for row in rows if row['has_detail'])
    fills_count = sum(1 for row in rows if row['fills_count'] > 0)
    fragmented_count = sum(1 for row in rows if row['fills_count'] > 1)
    fees_visible_count = sum(1 for row in rows if row['fees_ars'] > 0 or row['fees_usd'] > 0)
    fees_ars_total = sum((row['fees_ars'] for row in rows), Decimal('0'))
    fees_usd_total = sum((row['fees_usd'] for row in rows), Decimal('0'))
    enriched_pct = _safe_percentage(enriched_count, total_count)
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



def build_operation_list_row(operacion: OperacionIOL) -> dict:
    has_detail = has_operation_detail(operacion)
    fills = list(operacion.operaciones_detalle or [])
    fill_count = len(fills)
    fees_ars = Decimal(str(operacion.aranceles_ars or 0))
    fees_usd = Decimal(str(operacion.aranceles_usd or 0))
    execution_label = _build_execution_label(fill_count, has_detail)

    return {
        'operacion': operacion,
        'has_detail': has_detail,
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
