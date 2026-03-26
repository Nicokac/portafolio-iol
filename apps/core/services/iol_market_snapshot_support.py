from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import IOLMarketSnapshotObservation
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


DEFAULT_MARKET_SNAPSHOT_PLAZO = "t1"
TACTICAL_MARKET_SNAPSHOT_PLAZOS = ("t0", "t1")


def get_current_portfolio_market_snapshot_rows(service, *, limit: int = 10) -> list[dict]:
    return get_current_portfolio_market_snapshot_rows_by_plazo(
        service,
        plazo=DEFAULT_MARKET_SNAPSHOT_PLAZO,
        limit=limit,
    )


def get_current_portfolio_market_snapshot_rows_by_plazo(
    service,
    *,
    plazo: str = DEFAULT_MARKET_SNAPSHOT_PLAZO,
    limit: int = 10,
) -> list[dict]:
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

        snapshot = service._resolve_market_snapshot(
            mercado=row["mercado"],
            simbolo=row["simbolo"],
            params={"plazo": plazo},
        )
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
                    "plazo": str(plazo or "").strip().lower(),
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
                "plazo": str(snapshot.get("plazo") or plazo or "").strip().lower(),
            }
        )

    return rows[:limit]


def summarize_market_snapshot_rows(rows: list[dict]) -> dict:
    total = len(rows)
    available_count = sum(1 for row in rows if row.get("snapshot_status") == "available")
    missing_count = sum(1 for row in rows if row.get("snapshot_status") == "missing")
    unsupported_count = sum(1 for row in rows if row.get("snapshot_status") == "unsupported")
    detail_count = sum(
        1
        for row in rows
        if row.get("snapshot_source_key") in {"cotizacion_detalle", "cotizacion_detalle_mobile"}
    )
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
        "plazo": DEFAULT_MARKET_SNAPSHOT_PLAZO,
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
    t0_payload = {
        "rows": service.get_current_portfolio_market_snapshot_rows_by_plazo(plazo="t0", limit=limit),
        "summary": {},
        "refreshed_at": payload.get("refreshed_at") or timezone.now().isoformat(),
        "limit": limit,
        "plazo": "t0",
    }
    persistence_t1 = service.persist_market_snapshot_payload(payload)
    persistence_t0 = service.persist_market_snapshot_payload(t0_payload)
    payload["persistence"] = {
        "t1": persistence_t1,
        "t0": persistence_t0,
        "persisted_count": int(persistence_t1.get("persisted_count") or 0) + int(persistence_t0.get("persisted_count") or 0),
        "created": int(persistence_t1.get("created") or 0) + int(persistence_t0.get("created") or 0),
        "updated": int(persistence_t1.get("updated") or 0) + int(persistence_t0.get("updated") or 0),
        "skipped": int(persistence_t1.get("skipped") or 0) + int(persistence_t0.get("skipped") or 0),
    }
    payload["plazo_comparison"] = service.build_current_portfolio_market_plazo_comparison_payload(limit=limit)
    return payload


def build_current_portfolio_market_snapshot_payload_from_observations(
    service,
    *,
    limit: int = 25,
    lookback_days: int | None = None,
) -> dict | None:
    latest_positions = get_latest_position_rows()
    if not latest_positions:
        return None

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
            "descripcion",
            "tipo",
            "plazo",
            "ultimo_precio",
            "variacion",
            "cantidad_operaciones",
            "puntas_count",
            "spread_abs",
            "spread_pct",
        )
    )
    latest_observation_by_key: dict[tuple[str, str], dict] = {}
    for observation in observations:
        key = (
            str(observation.get("simbolo") or "").strip().upper(),
            str(observation.get("mercado") or "").strip().upper(),
        )
        latest_observation_by_key.setdefault(key, observation)

    if not latest_observation_by_key:
        return None

    rows = []
    latest_captured_at = None
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

        key = (
            str(row.get("simbolo") or "").strip().upper(),
            str(row.get("mercado") or "").strip().upper(),
        )
        observation = latest_observation_by_key.get(key)
        if not observation:
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

        captured_at = service._coerce_datetime(observation.get("captured_at"))
        if latest_captured_at is None or (captured_at and captured_at > latest_captured_at):
            latest_captured_at = captured_at
        rows.append(
            {
                "simbolo": row["simbolo"],
                "mercado": row["mercado"],
                "descripcion": observation.get("descripcion") or row.get("descripcion") or "",
                "tipo": observation.get("tipo") or row.get("tipo") or "",
                "snapshot_status": "available",
                "snapshot_source_key": str(observation.get("source_key") or "cotizacion_detalle"),
                "snapshot_source_label": service._build_snapshot_source_label(observation.get("source_key")),
                "snapshot_reason_key": "",
                "snapshot_reason": "",
                "fecha_hora": captured_at.isoformat() if captured_at else "",
                "fecha_hora_label": service._format_snapshot_datetime(captured_at),
                "ultimo_precio": service._coerce_decimal(observation.get("ultimo_precio")),
                "variacion": service._coerce_decimal(observation.get("variacion")),
                "cantidad_operaciones": service._coerce_int(observation.get("cantidad_operaciones")) or 0,
                "puntas_count": service._coerce_int(observation.get("puntas_count")) or 0,
                "best_bid": None,
                "best_ask": None,
                "spread_abs": service._coerce_decimal(observation.get("spread_abs")),
                "spread_pct": service._coerce_decimal(observation.get("spread_pct")),
                "plazo": str(observation.get("plazo") or "").strip().lower(),
            }
        )

    rows = rows[:limit]
    return {
        "rows": rows,
        "summary": summarize_market_snapshot_rows(rows),
        "refreshed_at": latest_captured_at.isoformat() if latest_captured_at else timezone.now().isoformat(),
        "limit": limit,
        "source": "persisted_observations",
        "plazo": DEFAULT_MARKET_SNAPSHOT_PLAZO,
        "plazo_comparison": build_current_portfolio_market_plazo_comparison_payload_from_observations(
            service,
            limit=limit,
            lookback_days=lookback_days,
        ),
    }


def get_cached_current_portfolio_market_snapshot(cache_key: str, service=None) -> dict | None:
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    if service is None:
        return None

    rebuilt_payload = build_current_portfolio_market_snapshot_payload_from_observations(service)
    if isinstance(rebuilt_payload, dict):
        cache.set(
            cache_key,
            rebuilt_payload,
            timeout=service.MARKET_SNAPSHOT_CACHE_TTL_SECONDS,
        )
        return rebuilt_payload
    return None


def persist_market_snapshot_payload(service, payload: dict | None) -> dict:
    payload = payload or {}
    rows = payload.get("rows") or []
    refreshed_at = service._coerce_datetime(payload.get("refreshed_at")) or timezone.now()
    created = 0
    updated = 0
    skipped = 0
    payload_plazo = str(payload.get("plazo") or "").strip()

    with transaction.atomic():
        for row in rows:
            if str(row.get("snapshot_status") or "") != "available":
                skipped += 1
                continue

            captured_at = service._coerce_datetime(row.get("fecha_hora")) or refreshed_at
            effective_plazo = str(row.get("plazo") or payload_plazo or "").strip().lower()
            _, was_created = IOLMarketSnapshotObservation.objects.update_or_create(
                simbolo=str(row.get("simbolo") or "").strip().upper(),
                mercado=str(row.get("mercado") or "").strip(),
                captured_at=captured_at,
                plazo=effective_plazo,
                defaults={
                    "captured_date": captured_at.date(),
                    "source_key": str(row.get("snapshot_source_key") or "cotizacion_detalle"),
                    "snapshot_status": "available",
                    "descripcion": str(row.get("descripcion") or ""),
                    "tipo": str(row.get("tipo") or ""),
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


def build_current_portfolio_market_plazo_comparison_payload_from_observations(
    service,
    *,
    limit: int = 25,
    lookback_days: int | None = None,
) -> dict:
    latest_positions = get_latest_position_rows()
    if not latest_positions:
        return {
            "rows": [],
            "summary": {
                "total_symbols": 0,
                "both_available_count": 0,
                "t0_only_count": 0,
                "t1_only_count": 0,
                "t0_preferred_count": 0,
                "t1_preferred_count": 0,
                "neutral_count": 0,
            },
        }

    days = int(lookback_days or service.MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS)
    cutoff = timezone.now() - pd.Timedelta(days=days)
    observations = list(
        IOLMarketSnapshotObservation.objects.filter(
            captured_at__gte=cutoff,
            plazo__in=TACTICAL_MARKET_SNAPSHOT_PLAZOS + tuple(item.upper() for item in TACTICAL_MARKET_SNAPSHOT_PLAZOS),
        )
        .order_by("simbolo", "mercado", "plazo", "-captured_at")
        .values(
            "simbolo",
            "mercado",
            "captured_at",
            "descripcion",
            "tipo",
            "plazo",
            "source_key",
            "ultimo_precio",
            "variacion",
            "cantidad_operaciones",
            "puntas_count",
            "spread_abs",
            "spread_pct",
        )
    )

    latest_by_key: dict[tuple[str, str, str], dict] = {}
    for observation in observations:
        key = (
            str(observation.get("simbolo") or "").strip().upper(),
            str(observation.get("mercado") or "").strip().upper(),
            str(observation.get("plazo") or "").strip().lower(),
        )
        latest_by_key.setdefault(key, observation)

    rows = []
    summary = {
        "total_symbols": 0,
        "both_available_count": 0,
        "t0_only_count": 0,
        "t1_only_count": 0,
        "t0_preferred_count": 0,
        "t1_preferred_count": 0,
        "neutral_count": 0,
    }

    for position in latest_positions:
        simbolo_key = str(position.get("simbolo") or "").strip().upper()
        mercado_key = str(position.get("mercado") or "").strip().upper()
        t0_observation = latest_by_key.get((simbolo_key, mercado_key, "t0"))
        t1_observation = latest_by_key.get((simbolo_key, mercado_key, "t1"))
        if not t0_observation and not t1_observation:
            continue

        comparison = _build_market_plazo_comparison_row(
            service,
            position=position,
            t0_observation=t0_observation,
            t1_observation=t1_observation,
        )
        rows.append(comparison)
        summary["total_symbols"] += 1
        if comparison["t0_available"] and comparison["t1_available"]:
            summary["both_available_count"] += 1
        elif comparison["t0_available"]:
            summary["t0_only_count"] += 1
        elif comparison["t1_available"]:
            summary["t1_only_count"] += 1

        recommended = comparison["recommended_plazo"]
        if recommended == "t0":
            summary["t0_preferred_count"] += 1
        elif recommended == "t1":
            summary["t1_preferred_count"] += 1
        else:
            summary["neutral_count"] += 1

    return {
        "rows": rows[:limit],
        "summary": summary,
        "lookback_days": days,
    }


def _build_market_plazo_comparison_row(service, *, position: dict, t0_observation: dict | None, t1_observation: dict | None) -> dict:
    t0_spread_pct = service._coerce_decimal((t0_observation or {}).get("spread_pct"))
    t1_spread_pct = service._coerce_decimal((t1_observation or {}).get("spread_pct"))
    t0_ops = service._coerce_int((t0_observation or {}).get("cantidad_operaciones")) or 0
    t1_ops = service._coerce_int((t1_observation or {}).get("cantidad_operaciones")) or 0
    t0_available = t0_observation is not None
    t1_available = t1_observation is not None

    recommended_plazo = "neutral"
    recommendation_reason = "Sin diferencia tactica concluyente entre plazos."
    if t0_available and not t1_available:
        recommended_plazo = "t0"
        recommendation_reason = "Solo hay snapshot disponible para t0."
    elif t1_available and not t0_available:
        recommended_plazo = "t1"
        recommendation_reason = "Solo hay snapshot disponible para t1."
    elif t0_available and t1_available:
        if t0_spread_pct is not None and t1_spread_pct is not None and t0_spread_pct != t1_spread_pct:
            if t0_spread_pct < t1_spread_pct:
                recommended_plazo = "t0"
                recommendation_reason = "t0 muestra menor spread visible."
            else:
                recommended_plazo = "t1"
                recommendation_reason = "t1 muestra menor spread visible."
        elif t0_ops != t1_ops:
            if t0_ops > t1_ops:
                recommended_plazo = "t0"
                recommendation_reason = "t0 muestra mayor actividad observada."
            else:
                recommended_plazo = "t1"
                recommendation_reason = "t1 muestra mayor actividad observada."
        elif int((t0_observation or {}).get("puntas_count") or 0) != int((t1_observation or {}).get("puntas_count") or 0):
            if int((t0_observation or {}).get("puntas_count") or 0) > int((t1_observation or {}).get("puntas_count") or 0):
                recommended_plazo = "t0"
                recommendation_reason = "t0 muestra mejor libro visible."
            else:
                recommended_plazo = "t1"
                recommendation_reason = "t1 muestra mejor libro visible."

    return {
        "simbolo": position.get("simbolo") or "",
        "mercado": position.get("mercado") or "",
        "descripcion": (t1_observation or t0_observation or {}).get("descripcion") or position.get("descripcion") or "",
        "tipo": (t1_observation or t0_observation or {}).get("tipo") or position.get("tipo") or "",
        "t0_available": t0_available,
        "t1_available": t1_available,
        "t0_spread_pct": t0_spread_pct,
        "t1_spread_pct": t1_spread_pct,
        "t0_operations": t0_ops,
        "t1_operations": t1_ops,
        "t0_source_label": service._build_snapshot_source_label((t0_observation or {}).get("source_key")),
        "t1_source_label": service._build_snapshot_source_label((t1_observation or {}).get("source_key")),
        "t0_captured_at_label": service._format_snapshot_datetime((t0_observation or {}).get("captured_at")),
        "t1_captured_at_label": service._format_snapshot_datetime((t1_observation or {}).get("captured_at")),
        "recommended_plazo": recommended_plazo,
        "recommended_label": {
            "t0": "Preferir t0",
            "t1": "Preferir t1",
            "neutral": "Sin ventaja clara",
        }.get(recommended_plazo, "Sin ventaja clara"),
        "recommendation_reason": recommendation_reason,
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
