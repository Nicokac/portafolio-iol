from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def build_portafolio_list_context(activos: Iterable[ActivoPortafolioSnapshot]) -> dict:
    rows = [build_portafolio_row(activo) for activo in activos]
    total_count = len(rows)
    parking_count = sum(1 for row in rows if row["has_parking"])
    parking_value_total = sum((row["valorizado"] for row in rows if row["has_parking"]), Decimal("0"))
    immediate_available_total = sum((row["disponible_inmediato"] for row in rows), Decimal("0"))

    return {
        "rows": rows,
        "summary": {
            "total_count": total_count,
            "parking_count": parking_count,
            "parking_missing_count": total_count - parking_count,
            "parking_pct": _safe_percentage(parking_count, total_count),
            "parking_value_total": parking_value_total,
            "immediate_available_total": immediate_available_total,
        },
    }


def build_portafolio_row(activo: ActivoPortafolioSnapshot) -> dict:
    parking_payload = activo.parking
    has_parking = _has_parking_payload(parking_payload)

    return {
        "activo": activo,
        "has_parking": has_parking,
        "parking_label": "Con parking" if has_parking else "Sin parking",
        "parking_tone": "warning" if has_parking else "secondary",
        "parking_detail_label": _build_parking_detail_label(parking_payload),
        "valorizado": Decimal(str(activo.valorizado or 0)),
        "disponible_inmediato": Decimal(str(activo.disponible_inmediato or 0)),
    }


def _has_parking_payload(value) -> bool:
    if value in (None, "", [], {}):
        return False
    return True


def _build_parking_detail_label(value) -> str:
    if not _has_parking_payload(value):
        return "Sin restricciones visibles"

    if isinstance(value, list):
        return f"{len(value)} bloque(s) de parking"

    if isinstance(value, dict):
        quantity = value.get("cantidad") or value.get("quantity")
        date = value.get("fecha") or value.get("fechaHasta") or value.get("until")
        description = value.get("descripcion") or value.get("detalle") or value.get("motivo")

        parts = []
        if quantity not in (None, ""):
            parts.append(f"Cantidad {quantity}")
        if date:
            parts.append(f"Fecha {date}")
        if description:
            parts.append(str(description))
        return " · ".join(parts[:3]) if parts else "Detalle de parking disponible"

    return str(value)


def _safe_percentage(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"))
