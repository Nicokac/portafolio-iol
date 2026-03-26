from types import SimpleNamespace

import pandas as pd
import pytest
from django.utils import timezone
from decimal import Decimal

from apps.portafolio_iol.models import ActivoPortafolioSnapshot

from apps.core.services.iol_market_snapshot_support import (
    build_current_portfolio_market_plazo_comparison_payload_from_observations,
    get_current_portfolio_market_snapshot_rows,
    persist_market_snapshot_payload,
    summarize_recent_market_history_rows,
)
from apps.core.models import IOLMarketSnapshotObservation


@pytest.mark.django_db
def test_get_current_portfolio_market_snapshot_rows_marks_missing_snapshot():
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.make_aware(pd.Timestamp("2026-03-20 10:00:00").to_pydatetime()),
        pais_consulta="argentina",
        simbolo="GGAL",
        descripcion="Grupo Galicia",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        moneda="ARS",
    )
    service = SimpleNamespace(
        classify_position_for_history=lambda row: {"supported": True},
        _resolve_market_snapshot=lambda **kwargs: None,
        _build_snapshot_source_label=lambda source_key: source_key or "",
    )

    rows = get_current_portfolio_market_snapshot_rows(service, limit=5)

    assert rows[0]["simbolo"] == "GGAL"
    assert rows[0]["snapshot_status"] == "missing"


def test_summarize_recent_market_history_rows_prioritizes_weak_status():
    summary = summarize_recent_market_history_rows(
        [
            {"quality_status": "strong"},
            {"quality_status": "watch"},
            {"quality_status": "weak"},
        ]
    )

    assert summary["overall_status"] == "weak"
    assert summary["weak_count"] == 1


@pytest.mark.django_db
def test_persist_market_snapshot_payload_keeps_t0_and_t1_observations_separate():
    now = timezone.now()
    service = SimpleNamespace(
        _coerce_datetime=lambda value: value if hasattr(value, "tzinfo") else now,
        _coerce_decimal=lambda value: Decimal(str(value)) if value is not None else None,
        _coerce_int=lambda value: int(value) if value is not None else None,
        MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS=7,
    )

    t0_payload = {
        "plazo": "t0",
        "refreshed_at": now,
        "rows": [
            {
                "simbolo": "MELI",
                "mercado": "BCBA",
                "snapshot_status": "available",
                "snapshot_source_key": "cotizacion_detalle_mobile",
                "descripcion": "Cedear MELI",
                "tipo": "CEDEARS",
                "plazo": "t0",
                "ultimo_precio": 20000,
                "variacion": 0.5,
                "cantidad_operaciones": 10,
                "puntas_count": 5,
                "spread_abs": 10,
                "spread_pct": 0.05,
                "fecha_hora": now,
            }
        ],
    }
    t1_payload = {
        "plazo": "t1",
        "refreshed_at": now,
        "rows": [
            {
                "simbolo": "MELI",
                "mercado": "BCBA",
                "snapshot_status": "available",
                "snapshot_source_key": "cotizacion_detalle_mobile",
                "descripcion": "Cedear MELI",
                "tipo": "CEDEARS",
                "plazo": "t1",
                "ultimo_precio": 20050,
                "variacion": 1.0,
                "cantidad_operaciones": 20,
                "puntas_count": 5,
                "spread_abs": 20,
                "spread_pct": 0.10,
                "fecha_hora": now,
            }
        ],
    }

    persist_market_snapshot_payload(service, t0_payload)
    persist_market_snapshot_payload(service, t1_payload)

    assert IOLMarketSnapshotObservation.objects.filter(simbolo="MELI", mercado="BCBA").count() == 2
    assert IOLMarketSnapshotObservation.objects.filter(simbolo="MELI", mercado="BCBA", plazo="t0").exists()
    assert IOLMarketSnapshotObservation.objects.filter(simbolo="MELI", mercado="BCBA", plazo="t1").exists()


@pytest.mark.django_db
def test_build_current_portfolio_market_plazo_comparison_payload_prefers_lower_spread():
    extraction_time = timezone.make_aware(pd.Timestamp("2026-03-20 10:00:00").to_pydatetime())
    captured_at = timezone.make_aware(pd.Timestamp("2026-03-20 11:00:00").to_pydatetime())
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=extraction_time,
        pais_consulta="argentina",
        simbolo="MELI",
        descripcion="Mercado Libre",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="CEDEARS",
        moneda="ARS",
    )
    IOLMarketSnapshotObservation.objects.create(
        simbolo="MELI",
        mercado="BCBA",
        source_key="cotizacion_detalle_mobile",
        snapshot_status="available",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        descripcion="Mercado Libre",
        tipo="CEDEARS",
        plazo="t0",
        ultimo_precio=20000,
        variacion=0.5,
        cantidad_operaciones=50,
        puntas_count=5,
        spread_abs=5,
        spread_pct=Decimal("0.05"),
    )
    IOLMarketSnapshotObservation.objects.create(
        simbolo="MELI",
        mercado="BCBA",
        source_key="cotizacion_detalle_mobile",
        snapshot_status="available",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        descripcion="Mercado Libre",
        tipo="CEDEARS",
        plazo="t1",
        ultimo_precio=20050,
        variacion=1.0,
        cantidad_operaciones=80,
        puntas_count=5,
        spread_abs=20,
        spread_pct=Decimal("0.10"),
    )

    service = SimpleNamespace(
        MARKET_SNAPSHOT_HISTORY_LOOKBACK_DAYS=7,
        _coerce_decimal=lambda value: Decimal(str(value)) if value is not None else None,
        _coerce_int=lambda value: int(value) if value is not None else None,
        _build_snapshot_source_label=lambda source_key: source_key or "",
        _format_snapshot_datetime=lambda value: timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if value else "",
    )

    payload = build_current_portfolio_market_plazo_comparison_payload_from_observations(service, limit=5)

    assert payload["summary"]["both_available_count"] == 1
    assert payload["summary"]["t0_preferred_count"] == 1
    assert payload["rows"][0]["recommended_plazo"] == "t0"
    assert "menor spread" in payload["rows"][0]["recommendation_reason"].lower()
