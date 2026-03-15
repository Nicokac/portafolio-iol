from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.data_quality.snapshot_history_audit import SnapshotHistoryAuditService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_asset_snapshot(fecha, simbolo, valorizado, *, tipo="ACCIONES", moneda="dolar_Estadounidense"):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo=simbolo,
        descripcion=f"Activo {simbolo}",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo=tipo,
        moneda=moneda,
    )


def _seed_parametro(simbolo, *, sector="Tecnologia", country="USA", patrimonial="Equity", strategic_bucket="Growth"):
    ParametroActivo.objects.create(
        simbolo=simbolo,
        sector=sector,
        bloque_estrategico=strategic_bucket,
        pais_exposicion=country,
        tipo_patrimonial=patrimonial,
    )


@pytest.mark.django_db
def test_snapshot_history_audit_returns_empty_payload_for_empty_portfolio():
    result = SnapshotHistoryAuditService().audit_current_invested_history(lookback_days=7)

    assert result["warning"] == "empty_portfolio"
    assert result["expected_symbols_count"] == 0
    assert result["usable_observations_count"] == 0
    assert result["rows"] == []


@pytest.mark.django_db
def test_snapshot_history_audit_detects_missing_calendar_days_and_usable_observations():
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    _seed_parametro("AAPL")
    _seed_parametro("MSFT")

    for offset, aapl, msft in [
        (4, 1000, 900),
        (2, 1020, 915),
        (0, 1035, 930),
    ]:
        fecha = now - timedelta(days=offset)
        _make_asset_snapshot(fecha, "AAPL", aapl)
        _make_asset_snapshot(fecha, "MSFT", msft)

    result = SnapshotHistoryAuditService().audit_current_invested_history(lookback_days=4)

    assert result["expected_symbols_count"] == 2
    assert result["available_price_dates_count"] == 2
    assert result["usable_observations_count"] == 1
    assert len(result["missing_calendar_dates"]) == 3

    row_by_date = {row["date"]: row for row in result["rows"]}
    missing_date = (now.date() - timedelta(days=3)).isoformat()
    assert row_by_date[missing_date]["assets_present"] == 0
    assert row_by_date[missing_date]["usable"] is False

    latest_date = now.date().isoformat()
    assert row_by_date[latest_date]["assets_present"] == 2
    assert row_by_date[latest_date]["coverage_pct"] == 100.0
    assert row_by_date[latest_date]["usable"] is True


@pytest.mark.django_db
def test_snapshot_history_audit_distinguishes_complete_dates_from_usable_return_dates():
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    _seed_parametro("AAPL")
    _seed_parametro("MSFT")

    day_2 = now - timedelta(days=2)
    day_1 = now - timedelta(days=1)
    day_0 = now

    _make_asset_snapshot(day_2, "AAPL", 1000)
    _make_asset_snapshot(day_1, "AAPL", 1010)
    _make_asset_snapshot(day_1, "MSFT", 900)
    _make_asset_snapshot(day_0, "AAPL", 1020)
    _make_asset_snapshot(day_0, "MSFT", 910)

    result = SnapshotHistoryAuditService().audit_current_invested_history(lookback_days=2)
    row_by_date = {row["date"]: row for row in result["rows"]}

    assert row_by_date[day_1.date().isoformat()]["complete_after_ffill"] is True
    assert row_by_date[day_1.date().isoformat()]["usable"] is False
    assert row_by_date[day_0.date().isoformat()]["usable"] is True
    assert result["usable_observations_count"] == 1
