from decimal import Decimal
from typing import Dict

from apps.portafolio_iol.selectors import build_portafolio_row


def build_market_snapshot_feature_context(*, payload: Dict, relevant_positions: list[dict], top_limit: int = 5) -> Dict:
    has_cached_snapshot = bool(payload.get("_has_cached_snapshot")) if "_has_cached_snapshot" in payload else bool(payload)
    cached_rows = payload.get("rows") or []
    summary = payload.get("summary") or {}
    refreshed_at_label = payload.get("refreshed_at_label") or ""

    snapshot_rows_by_key = {
        (
            str(row.get("simbolo") or "").strip().upper(),
            str(row.get("mercado") or "").strip().upper(),
        ): row
        for row in cached_rows
    }

    top_rows = []
    for item in relevant_positions[: max(int(top_limit or 0), 1)]:
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
        row
        for row in top_rows
        if row["snapshot_status"] == "available"
        and row.get("spread_pct") is not None
        and Decimal(str(row["spread_pct"])) >= Decimal("1.0")
    ]

    alerts = []
    if not has_cached_snapshot:
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
        "has_cached_snapshot": has_cached_snapshot,
        "refreshed_at_label": refreshed_at_label,
        "summary": summary,
        "top_rows": top_rows,
        "top_available_count": top_available_count,
        "top_missing_count": top_missing_count,
        "wide_spread_count": len(wide_spread_rows),
        "alerts": alerts[:3],
    }


def build_market_snapshot_history_feature_context(
    *,
    history_rows: list[dict],
    summary: Dict,
    current_portafolio: Dict,
    top_limit: int = 5,
    lookback_days: int = 7,
) -> Dict:
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


def build_portfolio_parking_feature_context(*, portafolio: Dict, top_limit: int = 5, safe_percentage) -> Dict:
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
            "parking_pct": safe_percentage(parking_count, total_positions),
            "parking_value_total": parking_value_total,
        },
        "parking_blocks": parking_block_summary,
        "top_rows": top_rows,
        "alerts": alerts,
    }
