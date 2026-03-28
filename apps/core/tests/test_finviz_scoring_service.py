from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import FinvizFundamentalsSnapshot, FinvizSignalSnapshot
from apps.core.services.finviz.finviz_scoring_service import FinvizScoringService


@pytest.mark.django_db
def test_build_latest_shortlist_orders_candidates_by_composite_buy_score():
    captured_at = timezone.now()
    common = {
        "captured_at": captured_at,
        "captured_date": captured_at.date(),
        "source_status": "ok",
        "data_quality": "full",
    }
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="AAPL",
        finviz_symbol="AAPL",
        fwd_pe=Decimal("24"),
        peg=Decimal("1.8"),
        eps_next_y=Decimal("10"),
        eps_next_5y=Decimal("9"),
        sales_past_5y=Decimal("8"),
        roic=Decimal("28"),
        oper_m=Decimal("30"),
        profit_m=Decimal("24"),
        debt_eq=Decimal("0.4"),
        quick_r=Decimal("1.3"),
        beta=Decimal("1.1"),
        change_pct=Decimal("1.2"),
        volume=5000000,
        **common,
    )
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="BABA",
        finviz_symbol="BABA",
        fwd_pe=Decimal("35"),
        peg=Decimal("2.7"),
        eps_next_y=Decimal("4"),
        eps_next_5y=Decimal("3"),
        sales_past_5y=Decimal("2"),
        roic=Decimal("8"),
        oper_m=Decimal("10"),
        profit_m=Decimal("9"),
        debt_eq=Decimal("1.8"),
        quick_r=Decimal("0.9"),
        beta=Decimal("1.7"),
        change_pct=Decimal("-5"),
        volume=400000,
        **common,
    )

    payload = FinvizScoringService().build_latest_shortlist(limit=5)

    assert payload["count"] == 2
    assert payload["items"][0]["internal_symbol"] == "AAPL"
    assert payload["items"][0]["composite_buy_score"] > payload["items"][1]["composite_buy_score"]
    assert payload["items"][0]["interpretation"]["level"] in {"high", "medium_high"}


@pytest.mark.django_db
def test_score_asset_generates_strengths_and_cautions():
    item = {
        "internal_symbol": "MSFT",
        "source_status": "ok",
        "data_quality": "full",
        "fwd_pe": 22.0,
        "peg": 1.2,
        "eps_next_y": 15.0,
        "eps_next_5y": 12.0,
        "sales_past_5y": 10.0,
        "roic": 22.0,
        "oper_m": 32.0,
        "profit_m": 28.0,
        "debt_eq": 0.5,
        "quick_r": 1.1,
        "beta": 1.0,
        "change_pct": -4.0,
        "volume": 8000000,
        "analyst_score": 82.0,
        "analyst_signal_label": "positive",
        "ratings_count": 6,
        "news_count": 4,
        "insider_buy_count": 2,
        "insider_sale_count": 1,
    }

    scored = FinvizScoringService().score_asset(item)

    assert scored["composite_buy_score"] is not None
    assert scored["strengths"]
    assert scored["main_reason"] == scored["strengths"][0]
    assert scored["data_quality_label"] == "Cobertura alta"
    assert scored["analyst_signal_label_text"] == "Consenso favorable"
    assert "rating(s)" in scored["secondary_overlay_summary"]
    assert "Catalizadores:" in scored["overlay_catalyst_summary"]
    assert "Sin fricciones" in scored["overlay_risk_summary"]


@pytest.mark.django_db
def test_score_asset_highlights_overlay_risks_when_consensus_and_insiders_are_weak():
    item = {
        "internal_symbol": "BABA",
        "source_status": "ok",
        "data_quality": "full",
        "fwd_pe": 30.0,
        "peg": 2.5,
        "eps_next_y": 4.0,
        "eps_next_5y": 3.0,
        "sales_past_5y": 2.0,
        "roic": 9.0,
        "oper_m": 11.0,
        "profit_m": 8.0,
        "debt_eq": 1.8,
        "quick_r": 0.8,
        "beta": 1.7,
        "change_pct": -5.0,
        "volume": 400000.0,
        "analyst_score": 30.0,
        "analyst_signal_label": "negative",
        "ratings_count": 4,
        "news_count": 1,
        "insider_buy_count": 0,
        "insider_sale_count": 3,
    }

    scored = FinvizScoringService().score_asset(item)

    assert "consenso adverso" in scored["overlay_risk_summary"].lower()
    assert "sesgo vendedor" in scored["overlay_risk_summary"].lower()


@pytest.mark.django_db
def test_compare_candidates_returns_gap_summary():
    captured_at = timezone.now()
    common = {
        "captured_at": captured_at,
        "captured_date": captured_at.date(),
        "source_status": "ok",
        "data_quality": "full",
        "fwd_pe": Decimal("20"),
        "peg": Decimal("1.1"),
        "eps_next_y": Decimal("12"),
        "eps_next_5y": Decimal("10"),
        "sales_past_5y": Decimal("8"),
        "roic": Decimal("18"),
        "oper_m": Decimal("25"),
        "profit_m": Decimal("20"),
        "debt_eq": Decimal("0.5"),
        "quick_r": Decimal("1.2"),
        "beta": Decimal("1.0"),
        "volume": 2000000,
    }
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="MSFT",
        finviz_symbol="MSFT",
        change_pct=Decimal("3"),
        **common,
    )
    ko_payload = {**common, "debt_eq": Decimal("0.3"), "quick_r": Decimal("0.9")}
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="KO",
        finviz_symbol="KO",
        change_pct=Decimal("0.5"),
        **ko_payload,
    )

    payload = FinvizScoringService().compare_candidates(["MSFT", "KO"])

    assert payload["count"] == 2
    assert payload["winner"]["internal_symbol"] in {"MSFT", "KO"}
    assert "queda arriba" in payload["summary"]


@pytest.mark.django_db
def test_build_latest_shortlist_keeps_fundamentals_ok_status_when_signal_snapshot_failed():
    captured_at = timezone.now()
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="AAPL",
        finviz_symbol="AAPL",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="ok",
        data_quality="full",
        fwd_pe=Decimal("20"),
        peg=Decimal("1.2"),
        eps_next_y=Decimal("12"),
        eps_next_5y=Decimal("10"),
        sales_past_5y=Decimal("8"),
        roic=Decimal("18"),
        oper_m=Decimal("25"),
        profit_m=Decimal("20"),
        debt_eq=Decimal("0.5"),
        quick_r=Decimal("1.2"),
        beta=Decimal("1.0"),
        change_pct=Decimal("2"),
        volume=2000000,
    )
    FinvizSignalSnapshot.objects.create(
        internal_symbol="AAPL",
        finviz_symbol="AAPL",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        source_status="error",
        metadata={"errors": {"news": {"code": "fetch_error"}}},
    )

    payload = FinvizScoringService().build_latest_shortlist(limit=5)

    assert payload["count"] == 1
    assert payload["items"][0]["internal_symbol"] == "AAPL"
