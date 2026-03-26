from datetime import date
from datetime import timedelta
from unittest.mock import Mock
import warnings
from decimal import Decimal

import pandas as pd
import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.core.models import IOLHistoricalPriceSnapshot, IOLMarketSnapshotObservation
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
def test_iol_historical_price_service_syncs_only_metadata_unresolved_symbols():
    _make_asset_snapshot("GGAL", "BCBA")
    unresolved = _make_asset_snapshot("MSFT", "NASDAQ")
    unresolved.descripcion = "Acción exterior"
    unresolved.save(update_fields=["descripcion"])
    caucion = _make_asset_snapshot("CAUCION", "BCBA")
    caucion.tipo = "CAUCION"
    caucion.descripcion = "Caucion colocadora"
    caucion.save(update_fields=["tipo", "descripcion"])

    client = Mock()
    client.get_titulo.return_value = {"simbolo": "MSFT", "mercado": "NASDAQ", "tipo": "ACCIONES"}
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 200.0},
    ]

    service = IOLHistoricalPriceService(client=client)
    coverage_rows = [
        {"simbolo": "GGAL", "mercado": "BCBA", "status": "ready", "eligibility_reason_key": ""},
        {"simbolo": "MSFT", "mercado": "NASDAQ", "status": "unsupported", "eligibility_reason_key": "title_metadata_unresolved"},
        {"simbolo": "CAUCION", "mercado": "BCBA", "status": "unsupported", "eligibility_reason_key": "caucion_not_title_series"},
    ]
    service.get_current_portfolio_coverage_rows = Mock(return_value=coverage_rows)

    result = service.sync_current_portfolio_symbols_by_status(
        statuses=("unsupported",),
        eligibility_reason_keys=("title_metadata_unresolved",),
    )

    assert result["selected_count"] == 1
    assert result["processed"] == 1
    assert result["eligibility_reason_keys"] == ["title_metadata_unresolved"]
    assert "NASDAQ:MSFT" in result["results"]
    assert "BCBA:CAUCION" not in result["results"]


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
def test_iol_historical_price_service_treats_prpedob_as_cash_management_symbol():
    client = Mock()
    client.get_fci.return_value = None

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "PRPEDOB")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported_fci"
    assert "cash management" in result["error"].lower()
    client.get_titulo_historicos.assert_not_called()


@pytest.mark.django_db
def test_iol_historical_price_service_marks_caucion_and_fci_as_unsupported_in_coverage_rows():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("ADBAICA", "BCBA")
    _make_asset_snapshot("PRPEDOB", "BCBA")
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
    assert row_by_symbol["PRPEDOB"]["status"] == "unsupported"
    assert row_by_symbol["PRPEDOB"]["eligibility_status"] == "unsupported_fci"
    assert "confirmado por iol como fci" in row_by_symbol["ADBAICA"]["eligibility_reason"].lower()
    assert row_by_symbol["ADBAICA"]["eligibility_source_key"] == "fci_confirmation"
    assert row_by_symbol["CAUCIÓN COLOCADORA"]["status"] == "unsupported"
    assert "caución" in row_by_symbol["CAUCIÓN COLOCADORA"]["eligibility_reason"].lower()


@pytest.mark.django_db
def test_iol_historical_price_service_skips_symbols_unresolved_by_iol_metadata():
    client = Mock()
    client.get_titulo.return_value = None
    client.get_fci.return_value = None
    client.get_titulo_market_snapshot.return_value = None

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "GGAL")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported"
    assert "metadata" in result["error"].lower()
    client.get_titulo_historicos.assert_not_called()


@pytest.mark.django_db
def test_iol_historical_price_service_uses_market_snapshot_when_title_metadata_is_missing():
    client = Mock()
    client.get_titulo.return_value = None
    client.get_fci.return_value = None
    client.get_titulo_market_snapshot.return_value = {
        "simbolo": "GGAL",
        "mercado": "bCBA",
        "tipo": "acciones",
        "descripcionTitulo": "Grupo Financiero Galicia",
    }
    client.get_titulo_historicos.return_value = [
        {"fechaHora": "2026-03-18T17:00:00", "ultimoPrecio": 108.0},
    ]

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "GGAL")

    assert result["success"] is True
    assert result["mercado"] == "bCBA"
    client.get_titulo_market_snapshot.assert_called()
    client.get_titulo_historicos.assert_called_once_with("bCBA", "GGAL", params=None)


@pytest.mark.django_db
def test_iol_historical_price_service_market_snapshot_can_confirm_unsupported_symbol():
    client = Mock()
    client.get_titulo.return_value = None
    client.get_fci.return_value = None
    client.get_titulo_market_snapshot.return_value = {
        "simbolo": "CAUCIÓN COLOCADORA",
        "mercado": "bcba",
        "tipo": "caucionespesos",
        "descripcionTitulo": "Caución En Pesos",
    }

    result = IOLHistoricalPriceService(client=client).sync_symbol_history("BCBA", "CAUCIÓN COLOCADORA")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["eligibility_status"] == "unsupported"
    assert "caución" in result["error"].lower()
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


@pytest.mark.django_db
def test_iol_historical_price_service_builds_current_portfolio_market_snapshot_rows():
    _make_asset_snapshot("GGAL", "BCBA")
    _make_asset_snapshot("AAPL", "NASDAQ")
    fci = _make_asset_snapshot("ADBAICA", "BCBA")
    fci.tipo = "FondoComundeInversion"
    fci.descripcion = "Adcap Cobertura"
    fci.save(update_fields=["tipo", "descripcion"])

    client = Mock()
    def _snapshot_side_effect(mercado, simbolo):
        if simbolo == "GGAL":
            return {
                "simbolo": "GGAL",
                "mercado": "bcba",
                "tipo": "acciones",
                "descripcionTitulo": "Grupo Financiero Galicia",
                "ultimoPrecio": 1000,
                "variacion": 1.5,
                "fechaHora": "2026-03-20T16:59:46.4181717-03:00",
                "cantidadOperaciones": 321,
                "puntas": [
                    {
                        "precioCompra": 995,
                        "precioVenta": 1000,
                        "cantidadCompra": 10,
                        "cantidadVenta": 12,
                    }
                ],
                "plazo": "t1",
                "cantidadMinima": 1,
            }
        return None

    client.get_titulo_market_snapshot.side_effect = _snapshot_side_effect

    rows = IOLHistoricalPriceService(client=client).get_current_portfolio_market_snapshot_rows(limit=10)

    row_by_symbol = {row["simbolo"]: row for row in rows}
    assert row_by_symbol["GGAL"]["snapshot_status"] == "available"
    assert row_by_symbol["GGAL"]["snapshot_source_key"] == "cotizacion_detalle"
    assert row_by_symbol["GGAL"]["puntas_count"] == 1
    assert row_by_symbol["GGAL"]["spread_abs"] == 5
    assert row_by_symbol["GGAL"]["cantidad_operaciones"] == 321
    assert row_by_symbol["AAPL"]["snapshot_status"] == "missing"
    assert row_by_symbol["AAPL"]["snapshot_reason_key"] == "market_snapshot_unavailable"
    assert row_by_symbol["ADBAICA"]["snapshot_status"] == "unsupported"
    assert row_by_symbol["ADBAICA"]["snapshot_source_key"] == "local_classification"
    called_pairs = {call.args for call in client.get_titulo_market_snapshot.call_args_list}
    assert ("BCBA", "GGAL") in called_pairs
    assert any(args[1] == "AAPL" for args in called_pairs)


@pytest.mark.django_db
def test_iol_historical_price_service_marks_snapshot_fallback_source_when_detail_keys_are_absent():
    _make_asset_snapshot("GGAL", "BCBA")

    client = Mock()
    client.get_titulo_market_snapshot.return_value = {
        "ultimoPrecio": 1000,
        "variacion": 1.5,
        "fechaHora": "2026-03-20T16:59:46.4181717-03:00",
        "descripcionTitulo": "Grupo Financiero Galicia",
        "puntas": [],
        "cantidadOperaciones": 0,
    }

    rows = IOLHistoricalPriceService(client=client).get_current_portfolio_market_snapshot_rows(limit=10)

    assert rows[0]["snapshot_status"] == "available"
    assert rows[0]["snapshot_source_key"] == "cotizacion"
    assert rows[0]["snapshot_source_label"] == "Cotizacion fallback"


def test_iol_historical_price_service_summarizes_market_snapshot_rows():
    summary = IOLHistoricalPriceService.summarize_market_snapshot_rows(
        [
            {"snapshot_status": "available", "snapshot_source_key": "cotizacion_detalle", "puntas_count": 2},
            {"snapshot_status": "available", "snapshot_source_key": "cotizacion", "puntas_count": 0},
            {"snapshot_status": "missing", "snapshot_source_key": "", "puntas_count": 0},
            {"snapshot_status": "unsupported", "snapshot_source_key": "local_classification", "puntas_count": 0},
        ]
    )

    assert summary == {
        "total_symbols": 4,
        "available_count": 2,
        "missing_count": 1,
        "unsupported_count": 1,
        "detail_count": 1,
        "fallback_count": 1,
        "order_book_count": 1,
        "overall_status": "partial",
    }


@pytest.mark.django_db
def test_iol_historical_price_service_refreshes_and_reads_cached_market_snapshot_payload():
    cache.delete(IOLHistoricalPriceService.MARKET_SNAPSHOT_CACHE_KEY)

    service = IOLHistoricalPriceService(client=Mock())
    service.get_current_portfolio_market_snapshot_rows = Mock(
        return_value=[
            {
                "simbolo": "GGAL",
                "snapshot_status": "available",
                "snapshot_source_key": "cotizacion_detalle",
                "puntas_count": 1,
            }
        ]
    )

    payload = service.refresh_cached_current_portfolio_market_snapshot(limit=12)

    assert payload["summary"]["available_count"] == 1
    assert payload["limit"] == 12
    assert payload["rows"][0]["simbolo"] == "GGAL"
    assert IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot() == payload


@pytest.mark.django_db
def test_iol_historical_price_service_rebuilds_market_snapshot_payload_from_persisted_observations():
    cache.delete(IOLHistoricalPriceService.MARKET_SNAPSHOT_CACHE_KEY)
    _make_asset_snapshot("GGAL", "BCBA")
    now = timezone.now()
    IOLMarketSnapshotObservation.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source_key="cotizacion_detalle",
        snapshot_status="available",
        captured_at=now - timedelta(minutes=5),
        captured_date=now.date(),
        descripcion="Grupo Galicia",
        tipo="ACCIONES",
        plazo="T1",
        ultimo_precio=Decimal("1234.50"),
        variacion=Decimal("1.75"),
        cantidad_operaciones=320,
        puntas_count=2,
        spread_abs=Decimal("5.00"),
        spread_pct=Decimal("0.40"),
    )

    payload = IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot()

    assert payload is not None
    assert payload["source"] == "persisted_observations"
    assert payload["summary"]["available_count"] == 1
    assert payload["summary"]["missing_count"] == 0
    assert payload["rows"][0]["simbolo"] == "GGAL"
    assert payload["rows"][0]["snapshot_status"] == "available"
    assert payload["rows"][0]["ultimo_precio"] == Decimal("1234.50")
    assert cache.get(IOLHistoricalPriceService.MARKET_SNAPSHOT_CACHE_KEY) == payload


@pytest.mark.django_db
def test_iol_historical_price_service_refresh_and_persist_includes_persistence_summary():
    cache.delete(IOLHistoricalPriceService.MARKET_SNAPSHOT_CACHE_KEY)

    service = IOLHistoricalPriceService(client=Mock())
    service.refresh_cached_current_portfolio_market_snapshot = Mock(
        return_value={
            "rows": [
                {
                    "simbolo": "GGAL",
                    "mercado": "BCBA",
                    "snapshot_status": "available",
                    "snapshot_source_key": "cotizacion_detalle",
                    "fecha_hora": "2026-03-21T10:00:00-03:00",
                    "cantidad_operaciones": 100,
                    "puntas_count": 1,
                }
            ],
            "summary": {"available_count": 1},
            "refreshed_at": "2026-03-21T10:00:00-03:00",
        }
    )

    payload = service.refresh_and_persist_current_portfolio_market_snapshot(limit=25)

    assert payload["persistence"]["persisted_count"] == 1
    assert IOLMarketSnapshotObservation.objects.count() == 1


@pytest.mark.django_db
def test_iol_historical_price_service_persists_available_market_snapshot_rows():
    service = IOLHistoricalPriceService(client=Mock())
    payload = {
        "refreshed_at": "2026-03-21T10:00:00-03:00",
        "rows": [
            {
                "simbolo": "GGAL",
                "mercado": "BCBA",
                "descripcion": "Grupo Galicia",
                "tipo": "ACCIONES",
                "snapshot_status": "available",
                "snapshot_source_key": "cotizacion_detalle",
                "fecha_hora": "2026-03-21T09:58:00-03:00",
                "ultimo_precio": Decimal("100"),
                "variacion": Decimal("1.25"),
                "cantidad_operaciones": 240,
                "puntas_count": 3,
                "spread_abs": Decimal("0.50"),
                "spread_pct": Decimal("0.50"),
                "plazo": "T0",
            },
            {
                "simbolo": "AAPL",
                "mercado": "NASDAQ",
                "snapshot_status": "missing",
            },
        ],
    }

    summary = service.persist_market_snapshot_payload(payload)

    assert summary["persisted_count"] == 1
    assert summary["skipped"] == 1
    observation = IOLMarketSnapshotObservation.objects.get(simbolo="GGAL")
    assert observation.source_key == "cotizacion_detalle"
    assert observation.cantidad_operaciones == 240
    assert observation.puntas_count == 3


@pytest.mark.django_db
def test_iol_historical_price_service_builds_recent_market_history_rows():
    _make_asset_snapshot("GGAL", "BCBA")
    now = timezone.now()
    IOLMarketSnapshotObservation.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source_key="cotizacion_detalle",
        snapshot_status="available",
        captured_at=now - timedelta(days=1),
        captured_date=(now - timedelta(days=1)).date(),
        cantidad_operaciones=420,
        puntas_count=1,
        spread_pct=Decimal("0.40"),
    )
    IOLMarketSnapshotObservation.objects.create(
        simbolo="GGAL",
        mercado="BCBA",
        source_key="cotizacion_detalle",
        snapshot_status="available",
        captured_at=now - timedelta(days=2),
        captured_date=(now - timedelta(days=2)).date(),
        cantidad_operaciones=380,
        puntas_count=1,
        spread_pct=Decimal("0.60"),
    )

    rows = IOLHistoricalPriceService(client=Mock()).get_recent_market_history_rows(lookback_days=7)

    assert len(rows) == 1
    assert rows[0]["simbolo"] == "GGAL"
    assert rows[0]["observations_count"] == 2
    assert rows[0]["quality_status"] == "strong"
    assert rows[0]["avg_operations"] == 400


def test_iol_historical_price_service_summarizes_recent_market_history_rows():
    summary = IOLHistoricalPriceService.summarize_recent_market_history_rows(
        [
            {"quality_status": "strong"},
            {"quality_status": "watch"},
            {"quality_status": "weak"},
            {"quality_status": "insufficient"},
        ]
    )

    assert summary == {
        "total_symbols": 4,
        "strong_count": 1,
        "watch_count": 1,
        "weak_count": 1,
        "insufficient_count": 1,
        "overall_status": "weak",
    }


def test_iol_historical_price_service_formats_snapshot_datetime_without_nanosecond_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        formatted = IOLHistoricalPriceService._format_snapshot_datetime(
            "2026-03-20T16:59:46.4181717-03:00"
        )

    assert formatted == "2026-03-20 16:59"
    assert not any("Discarding nonzero nanoseconds" in str(item.message) for item in caught)


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
