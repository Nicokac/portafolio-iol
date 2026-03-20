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
    client.get_titulo.return_value = {"simbolo": "GGAL", "mercado": "BCBA", "tipo": "ACCIONES"}
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
    client.get_titulo.return_value = {"simbolo": "GGAL", "mercado": "BCBA", "tipo": "ACCIONES"}
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
    client.get_titulo.side_effect = [
        {"simbolo": "GGAL", "mercado": "BCBA", "tipo": "ACCIONES"},
        {"simbolo": "AAPL", "mercado": "NASDAQ", "tipo": "ACCIONES"},
    ]
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


@pytest.mark.django_db
def test_iol_historical_price_service_builds_current_portfolio_coverage_rows():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("AAPL", "NASDAQ")
    for day, close in [(date(2026, 3, 18), 100), (date(2026, 3, 19), 102), (date(2026, 3, 20), 103)]:
        IOLHistoricalPriceSnapshot.objects.create(
            simbolo="GGAL",
            mercado="BCBA",
            source="iol",
            fecha=day,
            close=close,
        )

    rows = IOLHistoricalPriceService(client=Mock()).get_current_portfolio_coverage_rows(minimum_ready_rows=3)

    row_by_symbol = {row["simbolo"]: row for row in rows}
    assert row_by_symbol["GGAL"]["status"] == "ready"
    assert row_by_symbol["GGAL"]["rows_count"] == 3
    assert row_by_symbol["AAPL"]["status"] == "missing"
    assert row_by_symbol["AAPL"]["rows_count"] == 0


@pytest.mark.django_db
def test_iol_historical_price_service_syncs_only_missing_symbols_by_status():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("AAPL", "NASDAQ")
    for day, close in [(date(2026, 3, 18), 100), (date(2026, 3, 19), 102), (date(2026, 3, 20), 103)]:
        IOLHistoricalPriceSnapshot.objects.create(
            simbolo="GGAL",
            mercado="BCBA",
            source="iol",
            fecha=day,
            close=close,
        )

    client = Mock()
    client.get_titulo.return_value = {"simbolo": "AAPL", "mercado": "NASDAQ", "tipo": "ACCIONES"}
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 200.0},
    ]

    result = IOLHistoricalPriceService(client=client).sync_current_portfolio_symbols_by_status(
        statuses=("missing",),
        minimum_ready_rows=3,
    )

    assert result["selected_count"] == 1
    assert result["processed"] == 1
    assert result["success"] is True
    assert "NASDAQ:AAPL" in result["results"]
    assert "BCBA:GGAL" not in result["results"]


@pytest.mark.django_db
def test_iol_historical_price_service_syncs_only_partial_symbols_by_status():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("AAPL", "NASDAQ")
    for day, close in [(date(2026, 3, 18), 100), (date(2026, 3, 19), 102), (date(2026, 3, 20), 103)]:
        IOLHistoricalPriceSnapshot.objects.create(
            simbolo="GGAL",
            mercado="BCBA",
            source="iol",
            fecha=day,
            close=close,
        )

    client = Mock()
    client.get_titulo.return_value = {"simbolo": "GGAL", "mercado": "BCBA", "tipo": "ACCIONES"}
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 200.0},
    ]

    result = IOLHistoricalPriceService(client=client).sync_current_portfolio_symbols_by_status(
        statuses=("partial",),
        minimum_ready_rows=5,
    )

    assert result["selected_count"] == 1
    assert result["processed"] == 1
    assert result["success"] is True
    assert "BCBA:GGAL" in result["results"]
    assert "NASDAQ:AAPL" not in result["results"]


@pytest.mark.django_db
def test_iol_historical_price_service_skips_fci_symbols_in_title_history_pipeline():
    client = Mock()
    client.get_fci.return_value = {"simbolo": "ADBAICA", "tipoFondo": "money_market"}

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "ADBAICA")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported_fci"
    assert "confirmado por IOL como FCI" in result["error"]
    client.get_titulo_historicos.assert_not_called()


@pytest.mark.django_db
def test_iol_historical_price_service_marks_caucion_and_fci_as_unsupported_in_coverage_rows():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("ADBAICA", "BCBA")
    caucion = _make_asset_snapshot("CAUCIÓN COLOCADORA", "BCBA")
    caucion.tipo = "CAUCION"
    caucion.descripcion = "Caución colocadora"
    caucion.save(update_fields=["tipo", "descripcion"])
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
    IOLHistoricalPriceSnapshot.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source="iol",
        fecha=date(2026, 3, 20),
        close=103,
    )

    rows = IOLHistoricalPriceService(client=Mock()).get_current_portfolio_coverage_rows(minimum_ready_rows=3)

    row_by_symbol = {row["simbolo"]: row for row in rows}
    assert row_by_symbol["GGAL"]["status"] == "ready"
    assert row_by_symbol["ADBAICA"]["status"] == "unsupported"
    assert "pipeline distinto" in row_by_symbol["ADBAICA"]["eligibility_reason"]
    assert row_by_symbol["CAUCIÓN COLOCADORA"]["status"] == "unsupported"
    assert "caución" in row_by_symbol["CAUCIÓN COLOCADORA"]["eligibility_reason"].lower()


@pytest.mark.django_db
def test_iol_historical_price_service_skips_symbols_unresolved_by_iol_metadata():
    client = Mock()
    client.get_titulo.return_value = None
    client.get_fci.return_value = None

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "GGAL")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported"
    assert "metadata" in result["error"].lower()
    client.get_titulo_historicos.assert_not_called()


@pytest.mark.django_db
def test_iol_historical_price_service_resolves_market_using_known_aliases():
    client = Mock()
    client.get_titulo.side_effect = [
        None,
        {"simbolo": "GGAL", "mercado": "bCBA", "tipo": "ACCIONES"},
    ]
    client.get_fci.return_value = None
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 108.0},
    ]

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "GGAL")

    assert result["success"] is True
    assert result["mercado"] == "bCBA"
    assert client.get_titulo.call_args_list[0].args == ("BCBA", "GGAL")
    assert client.get_titulo.call_args_list[1].args == ("bCBA", "GGAL")
    client.get_titulo_historicos.assert_called_once_with("bCBA", "GGAL", params=None)


def test_iol_historical_price_service_candidate_markets_dedupes_and_keeps_primary_first():
    candidates = IOLHistoricalPriceService._candidate_markets("BCBA")

    assert candidates[0] == "BCBA"
    assert "bCBA" in candidates
    assert "bcba" in candidates
    assert len(candidates) == len(set(candidates))


@pytest.mark.django_db
def test_iol_historical_price_service_confirms_fci_when_title_metadata_is_missing():
    client = Mock()
    client.get_titulo.return_value = None
    client.get_fci.return_value = {"simbolo": "IOLPORA", "tipoFondo": "money_market"}

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "IOLPORA")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported_fci"
    assert "confirmado por IOL como FCI" in result["error"]
    client.get_titulo_historicos.assert_not_called()
