import pytest

from apps.core.models import Alert
from apps.dashboard.historical_rebalance import (
    build_active_alerts,
    build_senales_rebalanceo,
    build_snapshot_coverage_summary,
    get_objetivos_rebalanceo,
    mapear_sector_a_categoria,
)
from apps.portafolio_iol.models import PortfolioSnapshot


def test_mapear_sector_a_categoria_reuses_expected_bucket_names():
    assert mapear_sector_a_categoria("Utilities") == "Defensivos"
    assert mapear_sector_a_categoria("Indice") == "ETF core"
    assert mapear_sector_a_categoria("Argentina") == "Argentina"


def test_get_objetivos_rebalanceo_exposes_expected_targets():
    objetivos = get_objetivos_rebalanceo()

    assert objetivos["patrimonial"]["Liquidez"] == 25.0
    assert objetivos["patrimonial"]["Invertido"] == 67.5
    assert objetivos["sectorial"]["Defensivos"] == 12.5


def test_build_senales_rebalanceo_detects_overweights_underweights_and_large_positions():
    result = build_senales_rebalanceo(
        concentracion_patrimonial={"Liquidez": 40.0, "Invertido": 55.0},
        concentracion_sectorial={"Utilities": 20.0, "Tecnologia": 8.0, "Salud": 1.0},
        latest_portafolio_data=[],
    )

    assert result["patrimonial_sobreponderado"][0]["categoria"] == "Liquidez"
    assert result["patrimonial_subponderado"][0]["categoria"] == "Invertido"
    assert result["sectorial_sobreponderado"][0]["sector"] == "Defensivos"
    assert any(item["sector"] == "Salud" for item in result["sectorial_subponderado"])
    assert result["posiciones_mayor_peso"] == []


@pytest.mark.django_db
def test_build_snapshot_coverage_summary_reports_sufficient_history():
    for fecha, total in (
        ("2026-03-10", 1000),
        ("2026-03-14", 1100),
        ("2026-03-17", 1200),
        ("2026-03-20", 1300),
        ("2026-03-24", 1400),
    ):
        PortfolioSnapshot.objects.create(
            fecha=fecha,
            total_iol=total,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )

    summary = build_snapshot_coverage_summary(days=30)

    assert summary["snapshots_count"] == 5
    assert summary["history_span_days"] == 14
    assert summary["is_sufficient_for_volatility"] is True
    assert summary["status"] == "ok"


@pytest.mark.django_db
def test_build_active_alerts_orders_by_severity_and_recency():
    info = Alert.objects.create(tipo="info", mensaje="info", severidad="info", is_active=True)
    warning = Alert.objects.create(tipo="warning", mensaje="warning", severidad="warning", is_active=True)
    critical = Alert.objects.create(tipo="critical", mensaje="critical", severidad="critical", is_active=True)

    rows = build_active_alerts()

    assert [row["id"] for row in rows[:3]] == [critical.id, warning.id, info.id]
