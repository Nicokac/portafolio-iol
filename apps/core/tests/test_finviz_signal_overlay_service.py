from decimal import Decimal

import pytest
import pandas as pd
from django.utils import timezone

from apps.core.models import FinvizSignalSnapshot
from apps.core.services.finviz.finviz_signal_overlay_service import FinvizSignalOverlayService
from apps.parametros.models import ParametroActivo


class DummyFinvizSignalClient:
    def __init__(self, ratings=None, news=None, insiders=None):
        self.ratings_payload = ratings or {}
        self.news_payload = news or {}
        self.insiders_payload = insiders or {}
        self.last_error = {}

    def get_ratings(self, symbol):
        self.last_error = {}
        return self.ratings_payload.get(symbol, [])

    def get_news(self, symbol):
        self.last_error = {}
        return self.news_payload.get(symbol, [])

    def get_insiders(self, symbol):
        self.last_error = {}
        return self.insiders_payload.get(symbol, [])


@pytest.mark.django_db
def test_sync_signals_persists_secondary_overlay_summary():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    client = DummyFinvizSignalClient(
        ratings={
            "AAPL": [
                {"Action": "Upgrade", "Rating": "Buy"},
                {"Action": "Hold", "Rating": "Neutral"},
                {"Action": "Downgrade", "Rating": "Sell"},
            ]
        },
        news={"AAPL": [{"Title": "Headline 1"}, {"Title": "Headline 2"}]},
        insiders={"AAPL": [{"Transaction": "Buy"}, {"Transaction": "Sale"}]},
    )

    result = FinvizSignalOverlayService(client=client).sync_signals(scope="metadata")

    assert result["mapped_assets"] == 1
    snapshot = FinvizSignalSnapshot.objects.get(internal_symbol="AAPL")
    assert snapshot.ratings_count == 3
    assert snapshot.news_count == 2
    assert snapshot.insider_buy_count == 1
    assert snapshot.insider_sale_count == 1
    assert snapshot.analyst_score == Decimal("50.0")


@pytest.mark.django_db
def test_list_latest_snapshots_serializes_signal_fields():
    captured_at = timezone.now()
    FinvizSignalSnapshot.objects.create(
        internal_symbol="MSFT",
        finviz_symbol="MSFT",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        ratings_count=4,
        ratings_positive_count=3,
        ratings_negative_count=0,
        ratings_neutral_count=1,
        analyst_score=Decimal("80.0"),
        analyst_signal_label="positive",
        news_count=5,
        insider_buy_count=2,
        insider_sale_count=0,
    )

    payload = FinvizSignalOverlayService().list_latest_snapshots(symbols=["MSFT"])

    assert payload["count"] == 1
    assert payload["items"][0]["analyst_score"] == 80.0
    assert payload["items"][0]["news_count"] == 5
    assert payload["items"][0]["news_headlines"] == []


@pytest.mark.django_db
def test_list_latest_snapshots_exposes_top_news_headlines():
    captured_at = timezone.now()
    FinvizSignalSnapshot.objects.create(
        internal_symbol="NVDA",
        finviz_symbol="NVDA",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="ok",
        raw_payload={
            "news": [
                {"Title": "Nvidia beats earnings expectations"},
                {"Title": "Nvidia signs AI partnership"},
            ]
        },
    )

    payload = FinvizSignalOverlayService().list_latest_snapshots(symbols=["NVDA"])

    assert payload["count"] == 1
    assert payload["items"][0]["news_headlines"] == [
        "Nvidia beats earnings expectations",
        "Nvidia signs AI partnership",
    ]


@pytest.mark.django_db
def test_sync_signals_makes_timestamp_payload_json_safe():
    ParametroActivo.objects.create(
        simbolo="NVDA",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    client = DummyFinvizSignalClient(
        news={"NVDA": [{"Date": pd.Timestamp("2026-03-28 10:00:00"), "Title": "Headline"}]},
    )

    FinvizSignalOverlayService(client=client).sync_signals(scope="metadata")

    snapshot = FinvizSignalSnapshot.objects.get(internal_symbol="NVDA")
    assert snapshot.news_count == 1
    assert snapshot.raw_payload["news"][0]["Date"] == "2026-03-28T10:00:00"


@pytest.mark.django_db
def test_sync_signals_converts_nan_payload_values_to_null():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    client = DummyFinvizSignalClient(
        insiders={
            "AAPL": [
                {
                    "Transaction": "Buy",
                    "#Shares Total": float("nan"),
                }
            ]
        },
    )

    FinvizSignalOverlayService(client=client).sync_signals(scope="metadata")

    snapshot = FinvizSignalSnapshot.objects.get(internal_symbol="AAPL")
    assert snapshot.raw_payload["insiders"][0]["#Shares Total"] is None
