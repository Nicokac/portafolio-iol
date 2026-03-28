from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import FinvizFundamentalsSnapshot, FinvizSignalSnapshot
from apps.core.services.finviz.finviz_opportunity_watchlist_service import FinvizOpportunityWatchlistService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_build_watchlist_separates_external_and_reinforce_candidates():
    captured_at = timezone.now()
    portfolio_date = timezone.now()
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=portfolio_date,
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
        valorizado=500,
        pais_titulo="argentina",
        mercado="bcba",
        tipo="CEDEARS",
        plazo="t1",
        moneda="peso_Argentino",
    )
    common = {
        "captured_at": captured_at,
        "captured_date": captured_at.date(),
        "source_status": "ok",
        "data_quality": "full",
        "eps_next_y": Decimal("12"),
        "eps_next_5y": Decimal("11"),
        "sales_past_5y": Decimal("10"),
        "roic": Decimal("20"),
        "oper_m": Decimal("25"),
        "profit_m": Decimal("18"),
        "debt_eq": Decimal("0.4"),
        "quick_r": Decimal("1.4"),
        "curr_r": Decimal("1.8"),
        "beta": Decimal("1.1"),
        "change_pct": Decimal("2"),
        "volume": 3000000,
    }
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="MSFT",
        finviz_symbol="MSFT",
        fwd_pe=Decimal("18"),
        peg=Decimal("1.2"),
        **common,
    )
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="NVDA",
        finviz_symbol="NVDA",
        fwd_pe=Decimal("24"),
        peg=Decimal("1.4"),
        **common,
    )
    FinvizSignalSnapshot.objects.create(
        internal_symbol="MSFT",
        finviz_symbol="MSFT",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="ok",
        ratings_count=12,
        ratings_positive_count=9,
        ratings_negative_count=1,
        ratings_neutral_count=2,
        analyst_score=Decimal("82"),
        analyst_signal_label="positive",
        news_count=4,
        insider_buy_count=1,
        insider_sale_count=0,
    )
    FinvizSignalSnapshot.objects.create(
        internal_symbol="NVDA",
        finviz_symbol="NVDA",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="ok",
        ratings_count=8,
        ratings_positive_count=6,
        ratings_negative_count=1,
        ratings_neutral_count=1,
        analyst_score=Decimal("76"),
        analyst_signal_label="positive",
        news_count=5,
        insider_buy_count=0,
        insider_sale_count=1,
    )

    payload = FinvizOpportunityWatchlistService().build_watchlist(shortlist_limit=10, external_limit=3, reinforce_limit=3)

    assert payload["coverage"]["current_holdings_considered"] == 1
    assert payload["external_candidates"][0]["internal_symbol"] == "NVDA"
    assert payload["reinforce_candidates"][0]["internal_symbol"] == "MSFT"
    assert payload["reinforce_candidates"][0]["is_current_holding"] is True
    assert payload["external_candidates"][0]["is_current_holding"] is False


@pytest.mark.django_db
def test_build_watchlist_returns_empty_summary_without_data():
    payload = FinvizOpportunityWatchlistService().build_watchlist()

    assert payload["external_candidates"] == []
    assert payload["reinforce_candidates"] == []
    assert "todavia no hay cobertura" in payload["summary"].lower()
