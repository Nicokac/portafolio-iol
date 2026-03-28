from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import FinvizFundamentalsSnapshot
from apps.core.services.finviz.finviz_fundamentals_service import FinvizFundamentalsService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class DummyFinvizClient:
    def __init__(self, payload_by_symbol=None):
        self.payload_by_symbol = payload_by_symbol or {}
        self.last_error = {}

    def get_fundamentals(self, symbol):
        payload = self.payload_by_symbol.get(symbol)
        if payload is None:
            self.last_error = {"code": "empty_payload", "message": f"missing:{symbol}"}
            return None
        self.last_error = {}
        return payload


@pytest.mark.django_db
def test_sync_fundamentals_persists_normalized_metrics_from_metadata_scope():
    ParametroActivo.objects.create(
        simbolo="BRKB",
        sector="Finanzas",
        bloque_estrategico="Defensivo",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    client = DummyFinvizClient(
        {
            "BRK-B": {
                "Market Cap": "1.12T",
                "Price": "470.50",
                "Change": "1.25%",
                "Volume": "2.5M",
                "Beta": "0.87",
                "Fwd P/E": "21.4",
                "PEG": "1.85",
                "EPS Next Y": "10.2%",
                "EPS Next 5Y": "8.6%",
                "Sales Past 5Y": "7.1%",
                "ROIC": "14.4%",
                "Oper M": "22.5%",
                "Profit M": "18.0%",
                "Debt/Eq": "0.33",
                "Quick R": "1.40",
            }
        }
    )

    result = FinvizFundamentalsService(client=client).sync_fundamentals(scope="metadata")

    assert result["mapped_assets"] == 1
    assert result["ok"] == 1
    snapshot = FinvizFundamentalsSnapshot.objects.get(internal_symbol="BRKB")
    assert snapshot.finviz_symbol == "BRK-B"
    assert snapshot.market_cap == Decimal("1120000000000")
    assert snapshot.volume == 2500000
    assert snapshot.fwd_pe == Decimal("21.4")
    assert snapshot.quick_r == Decimal("1.40")
    assert snapshot.data_quality == "full"


@pytest.mark.django_db
def test_sync_fundamentals_persists_error_status_when_payload_missing():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    result = FinvizFundamentalsService(client=DummyFinvizClient()).sync_fundamentals(scope="metadata")

    assert result["mapped_assets"] == 1
    assert result["errors"] == 1
    snapshot = FinvizFundamentalsSnapshot.objects.get(internal_symbol="AAPL")
    assert snapshot.source_status == "error"
    assert snapshot.data_quality == "missing"
    assert snapshot.metadata["client_error"]["code"] == "empty_payload"


@pytest.mark.django_db
def test_sync_fundamentals_supports_portfolio_scope():
    now = timezone.now()
    ParametroActivo.objects.create(
        simbolo="MSFT",
        sector="Tecnologia",
        bloque_estrategico="Compounders",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=now,
        pais_consulta="argentina",
        simbolo="MSFT",
        descripcion="Cedear Microsoft",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=1,
        ppc=1,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=100,
        pais_titulo="argentina",
        mercado="bcba",
        tipo="CEDEARS",
        plazo="t1",
        moneda="peso_Argentino",
    )
    client = DummyFinvizClient({"MSFT": {"Price": "100", "Volume": "1M", "Beta": "0.9", "Fwd P/E": "25"}})

    result = FinvizFundamentalsService(client=client).sync_fundamentals(scope="portfolio")

    assert result["mapped_assets"] == 1
    assert FinvizFundamentalsSnapshot.objects.filter(internal_symbol="MSFT").exists()


@pytest.mark.django_db
def test_list_latest_snapshots_serializes_current_day_items():
    captured_at = timezone.now()
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="AAPL",
        finviz_symbol="AAPL",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="ok",
        data_quality="partial",
        price=Decimal("180.5"),
        beta=Decimal("1.20"),
    )

    payload = FinvizFundamentalsService().list_latest_snapshots(symbols=["AAPL"])

    assert payload["count"] == 1
    assert payload["items"][0]["internal_symbol"] == "AAPL"
    assert payload["items"][0]["price"] == 180.5
