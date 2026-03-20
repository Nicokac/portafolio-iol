from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_asset_snapshot(simbolo: str, mercado: str = "BCBA"):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.make_aware(pd.Timestamp("2026-03-20 10:00:00").to_pydatetime()),
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
        valorizado=1000,
        pais_titulo="Argentina",
        mercado=mercado,
        tipo="ACCIONES",
        moneda="ARS",
    )


@pytest.mark.django_db
def test_iol_historical_price_service_syncs_and_upserts_rows():
    client = Mock()
    client.get_titulo_historicos.return_value = [
        {
            "fechaHora": "2026-03-18T17:00:00",
            "apertura": 100.0,
            "maximo": 110.0,
            "minimo": 95.0,
            "ultimoPrecio": 108.0,
            "volumenNominal": 1500,
        },
        {
            "fechaHora": "2026-03-19T17:00:00",
            "apertura": 108.0,
            "maximo": 111.0,
            "minimo": 104.0,
            "ultimoPrecio": 109.0,
            "volumenNominal": 1600,
        },
    ]

    service = IOLHistoricalPriceService(client=client)
    first = service.sync_symbol_history("BCBA", "GGAL")
    second = service.sync_symbol_history("BCBA", "GGAL")

    assert first["created"] == 2
    assert second["updated"] == 2
    assert IOLHistoricalPriceSnapshot.objects.count() == 2


@pytest.mark.django_db
def test_iol_historical_price_service_ignores_rows_without_date_or_close():
    client = Mock()
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 108.0},
        {"fechaHora": None, "ultimoPrecio": 109.0},
        {"fechaHora": "2026-03-19T17:00:00", "ultimoPrecio": None},
    ]

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "GGAL")

    assert result["rows_received"] == 1
    assert IOLHistoricalPriceSnapshot.objects.count() == 1


@pytest.mark.django_db
def test_iol_historical_price_service_builds_close_series():
    IOLHistoricalPriceSnapshot.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source="iol",
        fecha=date(2026, 3, 18),
        close=100,
    )
    IOLHistoricalPriceSnapshot.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source="iol",
        fecha=date(2026, 3, 19),
        close=102,
    )

    dates = pd.to_datetime(["2026-03-18", "2026-03-19"])
    series = IOLHistoricalPriceService(client=Mock()).build_close_series("GGAL", "BCBA", dates)

    assert len(series) == 2
    assert float(series.iloc[0]) == 100.0
    assert float(series.iloc[1]) == 102.0


@pytest.mark.django_db
def test_iol_historical_price_service_syncs_current_portfolio_symbols():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("AAPL", "NASDAQ")

    client = Mock()
    client.get_titulo_historicos.side_effect = [
        [{"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 108.0}],
        [{"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 200.0}],
    ]

    result = IOLHistoricalPriceService(client=client).sync_current_portfolio_symbols()

    assert result["symbols_count"] == 2
    assert result["processed"] == 2
    assert result["success"] is True


@pytest.mark.django_db
def test_iol_historical_price_service_status_summary_reports_readiness():
    IOLHistoricalPriceSnapshot.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source="iol",
        fecha=date(2026, 3, 18),
        close=100,
    )
    IOLHistoricalPriceSnapshot.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source="iol",
        fecha=date(2026, 3, 19),
        close=102,
    )

    summary = IOLHistoricalPriceService(client=Mock()).get_status_summary()

    assert len(summary) == 1
    assert summary[0]["simbolo"] == "GGAL"
    assert summary[0]["rows_count"] == 2
    assert summary[0]["is_ready"] is True
