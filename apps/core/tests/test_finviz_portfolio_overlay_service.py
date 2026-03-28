from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import FinvizFundamentalsSnapshot
from apps.core.services.finviz.finviz_portfolio_overlay_service import FinvizPortfolioOverlayService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_build_current_portfolio_overlay_summarizes_weighted_profiles():
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
        valorizado=700,
        pais_titulo="argentina",
        mercado="bcba",
        tipo="CEDEARS",
        plazo="t1",
        moneda="peso_Argentino",
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=portfolio_date,
        pais_consulta="argentina",
        simbolo="KO",
        descripcion="Cedear Coca-Cola",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=1,
        ppc=1,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=300,
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
        "volume": 2000000,
    }
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="MSFT",
        finviz_symbol="MSFT",
        beta=Decimal("1.20"),
        change_pct=Decimal("2"),
        **common,
    )
    ko_payload = {**common, "debt_eq": Decimal("0.3"), "quick_r": Decimal("0.9")}
    FinvizFundamentalsSnapshot.objects.create(
        internal_symbol="KO",
        finviz_symbol="KO",
        beta=Decimal("0.80"),
        change_pct=Decimal("0.5"),
        **ko_payload,
    )

    payload = FinvizPortfolioOverlayService().build_current_portfolio_overlay()

    assert payload["coverage"]["mapped_assets"] == 2
    assert payload["coverage"]["coverage_pct"] == 100.0
    assert payload["weighted_profiles"]["portfolio_beta"] == 1.08
    assert payload["leaders"]["highest_weight"][0]["symbol"] == "MSFT"
    assert payload["beta_profile"]["label"] == "Balanceado"


@pytest.mark.django_db
def test_build_current_portfolio_overlay_returns_empty_without_snapshots():
    payload = FinvizPortfolioOverlayService().build_current_portfolio_overlay()

    assert payload["coverage"]["mapped_assets"] == 0
    assert payload["items"] == []
    assert "sin base suficiente" in payload["summary"].lower() or "todavia no hay base" in payload["summary"].lower()
