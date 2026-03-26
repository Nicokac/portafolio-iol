from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import IOLMarketSnapshotObservation
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def get_current_portfolio_market_snapshot_rows(service, *, limit: int = 10) -> list[dict]:
    latest_positions = get_latest_position_rows()
    if not latest_positions:
        return []

    rows = []
    for row in sorted(latest_positions, key=lambda item: (str(item["mercado"]), str(item["simbolo"]))):
        local_support = service.classify_position_for_history(row)
        if not local_support.get("supported"):
            rows.append(
                {
                    "simbolo": row["simbolo"],
                    "mercado": row["mercado"],
                    "descripcion": row.get("descripcion") or "",
                    "tipo": row.get("tipo") or "",
                    "snapshot_status": "unsupported",
                    "snapshot_source_key": local_support.get("support_source") or "local_classification",
                    "snapshot_source_label": service._build_snapshot_source_label(
                        local_support.get("support_source") or "local_classification"
                    ),
                    "snapshot_reason_key": local_support.get("reason_key") or "",
                    "snapshot_reason": local_support.get("reason") or "",
                    "fecha_hora": None,
                    "fecha_hora_label": "",
                    "ultimo_precio": None,
                    "variacion": None,
                    "cantidad_operaciones": 0,
                    "puntas_count": 0,
                    "best_bid": None,
                    "best_ask": None,
                    "spread_abs": None,
                    "spread_pct": None,
                    "plazo": "",
                }
            )
            continue

        snapshot = service._resolve_market_snapshot(mercado=row["mercado"], simbolo=row["simbolo"])
        if not snapshot:
            rows.append(
                {
                    "simbolo": row["simbolo"],
                    "mercado": row["mercado"],
                    "descripcion": row.get("descripcion") or "",
                    "tipo": row.get("tipo") or "",
                    "snapshot_status": "missing",
                    "snapshot_source_key": "",
                    "snapshot_source_label": "",
                    "snapshot_reason_key": "market_snapshot_unavailable",
                    "snapshot_reason": "IOL no devolvio cotizacion puntual para el instrumento.",
                    "fecha_hora": None,
                    "fecha_hora_label": "",
                    "ultimo_precio": None,
                    "variacion": None,
                    "cantidad_operaciones": 0,
                    "puntas_count": 0,
                    "best_bid": None,
                    "best_ask": None,
                    "spread_abs": None,
                    "spread_pct": None,
                    "plazo": "",
                }
            )
            continue

        first_punta = snapshot["puntas"][0] if isinstance(snapshot.get("puntas"), list) and snapshot.get("puntas") else {}
        best_bid = service._coerce_decimal(first_punta.get("precioCompra"))
        best_ask = service._coerce_decimal(first_punta.get("precioVenta"))
        spread_abs = None
        spread_pct = None
        if best_bid is not None and best_ask is not None and best_bid > 0 and best_ask >= best_bid:
            spread_abs = best_ask - best_bid
            spread_pct = (spread_abs / best_bid) * Decimal("100")

        fecha_hora = snapshot.get("fechaHora")
        source_key = service._infer_market_snapshot_source(snapshot)
        rows.append(
            {
                "simbolo": row["simbolo"],
                "mercado": str(snapshot.get("mercado") or row["mercado"]),
                "descripcion": snapshot.get("descripcionTitulo") or row.get("descripcion") or "",
                "tipo": snapshot.get("tipo") or row.get("tipo") or "",
                "snapshot_status": "available",
                "snapshot_source_key": source_key,
                "snapshot_source_label": service._build_snapshot_source_label(source_key),
                "snapshot_reason_key": "",
                "snapshot_reason": "",
                "fecha_hora": fecha_hora,
                "fecha_hora_label": service._format_snapshot_datetime(fecha_hora),
                "ultimo_precio": service._coerce_decimal(snapshot.get("ultimoPrecio")),
                "variacion": service._coerce_decimal(snapshot.get("variacion")),
                "cantidad_operaciones": service._coerce_int(snapshot.get("cantidadOperaciones")) or 0,
                "puntas_count": len(snapshot.get("puntas") or []),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_abs": spread_abs,
                "spread_pct": spread_pct,
                "plazo": str(snapshot.get("plazo") or ""),
            }
        )

    return rows[:limit]


def summarize_market_snapshot_rows(rows: list[dict]) -> dict:
    total = len(rows)
    available_count = sum(1 for row in rows if row.get("snapshot_status") == "available")
    missing_count = sum(1 for row in rows if row.get("snapshot_status") == "missing")
    unsupported_count = sum(1 for row in rows if row.get("snapshot_status") == "unsupported")
    detail_count = sum(1 for row in rows if row.get("snapshot_source_key") == "cotizacion_detalle")
    fallback_count = sum(1 for row in rows if row.get("snapshot_source_key") == "cotizacion")
    order_book_count = sum(1 for row in rows if int(row.get("puntas_count") or 0) > 0)

    if total == 0:
        overall_status = "missing"
    elif missing_count == 0 and unsupported_count == 0:
        overall_status = "ready"
    elif available_count > 0:
        overall_status = "partial"
    else:
        overall_status = "warning"

    return {
        "total_symbols": total,
        "available_count": available_count,
        "missing_count": missing_count,
        "unsupported_count": unsupported_count,
        "detail_count": detail_count,
        "fallback_count": fallback_count,
        "order_book_count": order_book_count,
        "overall_status": overall_status,
    }


def build_current_portfolio_market_snapshot_payload(service, *, limit: int = 25) -> dict:
    rows = service.get_current_portfolio_market_snapshot_rows(limit=limit)
    return {
        "rows": rows,
        "summary": summarize_market_snapshot_rows(rows),
        "refreshed_at": timezone.now().isoformat(),
        "limit": limit,
    }


def refresh_cached_current_portfolio_market_snapshot(service, *, limit: int = 25) -> dict:
    payload = service.build_current_portfolio_market_snapshot_payload(limit=limit)
    cache.set(
        service.MARKET_SNAPSHOT_CACHE_KEY,
        payload,
        timeout=service.MARKET_SNAPSHOT_CACHE_TTL_SECONDS,
    )
    return payload


def refresh_and_persist_current_portfolio_market_snapshot(service, *, limit: int = 25) -> dict:
    payload = service.refresh_cached_current_portfolio_market_snapshot(limit=limit)
    payload["persistence"] = service.persist_market_snapshot_payload(payload)
    return payload


def get_cached_current_portfolio_market_snapshot(cache_key: str) -> dict | None:
    cached = cache.get(cache_key)
    return cached if isinstance(cached, dict) else None


def persist_market_snapshot_payload(service, payload: dict | None) -> dict:
    payload = payload or {}
    rows = payload.get("rows") or []
    refreshed_at = service._coerce_datetime(payload.get("refreshed_at")) or timezone.now()
    created = 0
    updated = 0
    skipped = 0

    with transaction.atomic():
        for row in rows:
            if str(row.get("snapshot_status") or "") != "available":
                skipped += 1
                continue

            captured_at = service._coerce_datetime(row.get("fecha_hora")) or refreshed_at
            _, was_created = IOLMarketSnapshotObservation.objects.update_or_create(
                simbolo=str(row.get("simbolo") or "").strip().upper(),
                mercado=str(row.get("mercado") or "").strip(),
                captured_at=captured_at,
                defaults={
                    "captured_date": captured_at.date(),
                    "source_key": str(row.get("snapshot_source_key") or "cotizacion_detalle"),
                    "snapshot_status": "available",
                    "descripcion": str(row.get("descripcion") or ""),
                    "tipo": str(row.get("tipo") or ""),
                    "plazo": str(row.get("plazo") or ""),
                    "ultimo_precio": service._coerce_decimal(row.get("ultimo_precio")),
                    "variacion": service._coerce_decimal(row.get("variacion")),
                    "cantidad_operaciones": service._coerce_int(row.get("cantidad_operaciones")) or 0,
                    "puntas_count": service._coerce_int(row.get("puntas_count")) or 0,
                    "spread_abs": service._coerce_decimal(row.get("spread_abs")),
                    "spread_pct": service._coerce_decimal(row.get("spread_pct")),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

    return {
        "persisted_count": created + updated,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "lookback_days": service.MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS,
    }


def get_recent_market_history_rows(service, *, lookback_days: int | None = None) -> list[dict]:
    latest_positions = get_latest_position_rows()
    if not latest_positions:
        return []

    days = int(lookback_days or service.MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS)
    cutoff = timezone.now() - pd.Timedelta(days=days)
    observations = list(
        IOLMarketSnapshotObservation.objects.filter(captured_at__gte=cutoff)
        .order_by("simbolo", "mercado", "-captured_at")
        .values(
            "simbolo",
            "mercado",
            "captured_at",
            "source_key",
            "spread_pct",
            "cantidad_operaciones",
            "puntas_count",
        )
    )
    observations_by_key: dict[tuple[str, str], list[dict]] = {}
    for observation in observations:
        key = (
            str(observation.get("simbolo") or "").strip().upper(),
            str(observation.get("mercado") or "").strip().upper(),
        )
        observations_by_key.setdefault(key, []).append(observation)

    rows = []
    for position in latest_positions:
        key = (
            str(position.get("simbolo") or "").strip().upper(),
            str(position.get("mercado") or "").strip().upper(),
        )
        symbol_observations = observations_by_key.get(key, [])
        latest_observation = symbol_observations[0] if symbol_observations else None
        spreads = [
            service._coerce_decimal(item.get("spread_pct"))
            for item in symbol_observations
            if service._coerce_decimal(item.get("spread_pct")) is not None
        ]
        operation_counts = [
            service._coerce_int(item.get("cantidad_operaciones")) or 0
            for item in symbol_observations
        ]
        order_book_count = sum(1 for item in symbol_observations if int(item.get("puntas_count") or 0) > 0)
        observations_count = len(symbol_observations)
        avg_spread_pct = service._average_decimal(spreads)
        avg_operations = service._average_int(operation_counts)
        order_book_coverage_pct = service._coverage_percentage(order_book_count, observations_count)
        quality_status = service._classify_recent_market_quality(
            observations_count=observations_count,
            avg_spread_pct=avg_spread_pct,
            avg_operations=avg_operations,
            order_book_coverage_pct=order_book_coverage_pct,
        )
        rows.append(
            {
                "simbolo": position["simbolo"],
                "mercado": position["mercado"],
                "descripcion": position.get("descripcion") or "",
                "tipo": position.get("tipo") or "",
                "observations_count": observations_count,
                "last_captured_at": latest_observation.get("captured_at") if latest_observation else None,
                "last_captured_at_label": service._format_snapshot_datetime(
                    latest_observation.get("captured_at") if latest_observation else None
                ),
                "latest_source_key": str((latest_observation or {}).get("source_key") or ""),
                "avg_spread_pct": avg_spread_pct,
                "avg_operations": avg_operations,
                "order_book_coverage_pct": order_book_coverage_pct,
                "quality_status": quality_status,
                "quality_status_label": service._build_recent_market_quality_label(quality_status),
                "quality_summary": service._build_recent_market_quality_summary(
                    quality_status=quality_status,
                    avg_spread_pct=avg_spread_pct,
                    avg_operations=avg_operations,
                    order_book_coverage_pct=order_book_coverage_pct,
                ),
            }
        )
    return rows


def summarize_recent_market_history_rows(rows: list[dict]) -> dict:
    total = len(rows)
    strong_count = sum(1 for row in rows if row.get("quality_status") == "strong")
    watch_count = sum(1 for row in rows if row.get("quality_status") == "watch")
    weak_count = sum(1 for row in rows if row.get("quality_status") == "weak")
    insufficient_count = sum(1 for row in rows if row.get("quality_status") == "insufficient")
    return {
        "total_symbols": total,
        "strong_count": strong_count,
        "watch_count": watch_count,
        "weak_count": weak_count,
        "insufficient_count": insufficient_count,
        "overall_status": "weak" if weak_count else "watch" if watch_count else "ready" if strong_count else "missing",
    }


def get_latest_position_rows() -> list[dict]:
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    if not latest_date:
        return []
    return list(
        ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date)
        .exclude(simbolo__isnull=True)
        .exclude(simbolo="")
        .exclude(mercado__isnull=True)
        .exclude(mercado="")
        .values("simbolo", "mercado", "descripcion", "tipo")
        .distinct()
    )
