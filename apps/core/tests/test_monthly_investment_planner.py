from decimal import Decimal

import pytest

from apps.core.services.monthly_investment_planner import MonthlyInvestmentPlanner
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.fixture
def planner():
    return MonthlyInvestmentPlanner()


@pytest.fixture
def activo_snapshot(db):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion="2026-03-13T10:00:00Z",
        pais_consulta="argentina",
        simbolo="SPY",
        descripcion="SPY",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=200,
        ppc=180,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=2000,
        pais_titulo="USA",
        mercado="BCBA",
        tipo="CEDEAR",
        moneda="ARS",
    )


def test_plan_monthly_investment_rejects_invalid_allocation(planner):
    result = planner.plan_monthly_investment(
        Decimal("100000"),
        current_portfolio={"total_iol": 1000000},
        custom_allocation={"SPY": 70, "EEM": 20},
    )

    assert result == {"error": "La asignación debe sumar 100%. Suma actual: 90"}


def test_plan_monthly_investment_uses_dashboard_when_portfolio_missing(planner, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.get_dashboard_kpis",
        lambda: {"total_iol": 1000000, "liquidez_operativa": 100000},
    )
    monkeypatch.setattr(planner, "_estimate_quantity", lambda asset, amount: None)
    monkeypatch.setattr(planner, "_calculate_portfolio_impact", lambda distribution, current, nuevo: {"ok": True})
    monkeypatch.setattr(planner, "_generate_additional_recommendations", lambda distribution, current: ["ok"])

    result = planner.plan_monthly_investment(Decimal("100000"))

    assert result["aporte_mensual"] == 100000.0
    assert result["total_portafolio_actual"] == 1000000.0
    assert result["total_portafolio_nuevo"] == 1100000.0
    assert result["incremento_porcentual"] == 10.0
    assert result["impacto_portafolio"] == {"ok": True}
    assert result["recomendaciones_adicionales"] == ["ok"]


def test_plan_monthly_investment_returns_error_on_zero_total(planner):
    planner._estimate_quantity = lambda asset, amount: None

    result = planner.plan_monthly_investment(
        Decimal("100000"),
        current_portfolio={"total_iol": 0},
    )

    assert "error" in result
    assert "divisionbyzero" in result["error"].lower()


def test_create_custom_plan_applies_short_horizon_adjustments(planner, monkeypatch):
    monkeypatch.setattr(
        planner,
        "_build_state_based_allocation",
        lambda base_allocation, current_portfolio, risk_profile: (
            base_allocation,
            {"mode": "state_based", "targets": {}, "gaps": {}},
        ),
    )
    monkeypatch.setattr(
        planner,
        "plan_monthly_investment",
        lambda monthly_amount, current_portfolio, allocation: {
            "distribucion": allocation,
            "aporte_mensual": float(monthly_amount),
        },
    )

    result = planner.create_custom_plan(
        Decimal("100000"),
        risk_profile="moderado",
        investment_horizon="corto",
        current_portfolio={"total_iol": 1000000},
    )

    assert result["distribucion"]["LIQUIDEZ"] == 25.0
    assert result["distribucion"]["BONOS"] == 30.0
    assert result["distribucion"]["SPY"] == 20.0
    assert result["allocation_basis"]["mode"] == "state_based"


def test_create_custom_plan_applies_long_horizon_adjustments(planner, monkeypatch):
    monkeypatch.setattr(
        planner,
        "_build_state_based_allocation",
        lambda base_allocation, current_portfolio, risk_profile: (
            base_allocation,
            {"mode": "state_based", "targets": {}, "gaps": {}},
        ),
    )
    monkeypatch.setattr(
        planner,
        "plan_monthly_investment",
        lambda monthly_amount, current_portfolio, allocation: {
            "distribucion": allocation,
        },
    )

    result = planner.create_custom_plan(
        Decimal("100000"),
        risk_profile="conservador",
        investment_horizon="largo",
        current_portfolio={"total_iol": 1000000},
    )

    assert result["distribucion"]["LIQUIDEZ"] == 25.0
    assert result["distribucion"]["SPY"] == 25.0


def test_build_state_based_allocation_uses_defaults_when_no_active_parameters(planner, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.PortfolioParameters.get_active_parameters",
        lambda: None,
    )
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.get_concentracion_pais",
        lambda: {"USA": 10.0, "Argentina": 20.0, "EM": 5.0},
    )

    allocation, rationale = planner._build_state_based_allocation(
        base_allocation={"SPY": 40, "EEM": 20, "BONOS": 20, "LIQUIDEZ": 20},
        current_portfolio={"total_iol": 1000, "liquidez_operativa": 50, "fci_cash_management": 50},
        risk_profile="moderado",
    )

    assert rationale["mode"] == "state_based"
    assert rationale["targets"] == {
        "liquidez": 20.0,
        "usa": 40.0,
        "argentina": 30.0,
        "emerging": 10.0,
    }
    assert round(sum(allocation.values()), 2) == 100.0
    assert allocation["SPY"] > allocation["EEM"]


def test_build_state_based_allocation_returns_base_only_when_no_gaps(planner, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.PortfolioParameters.get_active_parameters",
        lambda: None,
    )
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.get_concentracion_pais",
        lambda: {"USA": 50.0, "Argentina": 35.0, "EM": 20.0},
    )
    base = {"SPY": 40, "EEM": 20, "BONOS": 20, "LIQUIDEZ": 20}

    allocation, rationale = planner._build_state_based_allocation(
        base_allocation=base,
        current_portfolio={"total_iol": 1000, "liquidez_operativa": 150, "fci_cash_management": 100},
        risk_profile="moderado",
    )

    assert allocation == base
    assert rationale["mode"] == "base_only"


def test_build_state_based_allocation_uses_explicit_liquidity_layers_when_available(planner, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.PortfolioParameters.get_active_parameters",
        lambda: None,
    )
    monkeypatch.setattr(
        "apps.core.services.monthly_investment_planner.get_concentracion_pais",
        lambda: {"USA": 10.0, "Argentina": 20.0, "EM": 5.0},
    )

    allocation, rationale = planner._build_state_based_allocation(
        base_allocation={"SPY": 40, "EEM": 20, "BONOS": 20, "LIQUIDEZ": 20},
        current_portfolio={
            "total_patrimonio_modelado": 3000,
            "cash_disponible_broker": 200,
            "caucion_colocada": 1000,
            "liquidez_estrategica": 500,
        },
        risk_profile="moderado",
    )

    assert rationale["mode"] == "state_based"
    assert allocation["LIQUIDEZ"] == 0.0


def test_normalize_allocation_closes_rounding_drift(planner):
    result = planner._normalize_allocation({"A": 1, "B": 1, "C": 1})

    assert result == {"A": 33.34, "B": 33.33, "C": 33.33}


def test_estimate_quantity_returns_none_for_special_assets(planner):
    assert planner._estimate_quantity("LIQUIDEZ", Decimal("1000")) is None
    assert planner._estimate_quantity("BONOS", Decimal("1000")) is None


@pytest.mark.django_db
def test_estimate_quantity_uses_operational_price(planner, activo_snapshot):
    result = planner._estimate_quantity("SPY", Decimal("1000"))

    assert result == 5.0


@pytest.mark.django_db
def test_estimate_quantity_returns_none_without_reference_price(planner, activo_snapshot):
    activo_snapshot.ultimo_precio = 0
    activo_snapshot.ppc = 0
    activo_snapshot.save(update_fields=["ultimo_precio", "ppc"])

    result = planner._estimate_quantity("SPY", Decimal("1000"))

    assert result is None


def test_calculate_portfolio_impact_classifies_global_balance(planner):
    distribution = {
        "SPY": {"porcentaje": 35},
        "EEM": {"porcentaje": 15},
        "LIQUIDEZ": {"porcentaje": 10},
        "BONOS": {"porcentaje": 40},
    }

    result = planner._calculate_portfolio_impact(distribution, {}, Decimal("1000000"))

    assert result["cambio_acciones_usa"] == 35
    assert result["cambio_emergentes"] == 15
    assert result["cambio_liquidez"] == 10
    assert result["cambio_bonos"] == 40
    assert result["nueva_diversificacion"] == "equilibrada_global"


def test_generate_additional_recommendations_covers_small_large_and_spy_cases(planner):
    low_distribution = {"SPY": {"monto": 50000, "porcentaje": 70}}
    high_distribution = {
        "SPY": {"monto": 700000, "porcentaje": 70},
        "EEM": {"monto": 400000, "porcentaje": 30},
    }

    low_result = planner._generate_additional_recommendations(low_distribution, {})
    high_result = planner._generate_additional_recommendations(high_distribution, {})

    assert "Considera aumentar el aporte mensual para impacto significativo" in low_result
    assert "Alta concentración en SPY - considera diversificar en otros ETFs" in low_result
    assert low_result[-1] == "Considera promediar el aporte durante el mes para reducir volatilidad"
    assert "Monto elevado - considera diversificar en más activos" in high_result
