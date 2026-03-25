from decimal import Decimal
from types import SimpleNamespace

from apps.dashboard.market_signals import (
    build_market_snapshot_feature_context,
    build_market_snapshot_history_feature_context,
    build_portfolio_parking_feature_context,
)


def test_build_market_snapshot_feature_context_summarizes_missing_spread_and_fallback_alerts():
    result = build_market_snapshot_feature_context(
        payload={
            "summary": {"fallback_count": 1, "order_book_count": 0, "available_count": 1},
            "refreshed_at_label": "2026-03-24 10:00",
            "rows": [
                {
                    "simbolo": "GGAL",
                    "mercado": "BCBA",
                    "snapshot_status": "available",
                    "descripcion": "Grupo Galicia",
                    "spread_pct": Decimal("1.20"),
                    "puntas_count": 0,
                }
            ],
        },
        relevant_positions=[
            {"activo": SimpleNamespace(simbolo="GGAL", mercado="BCBA", descripcion="GGAL", valorizado=Decimal("1000")), "peso_porcentual": 60},
            {"activo": SimpleNamespace(simbolo="PAMP", mercado="BCBA", descripcion="PAMP", valorizado=Decimal("500")), "peso_porcentual": 40},
        ],
        top_limit=5,
    )

    assert result["has_cached_snapshot"] is True
    assert result["top_available_count"] == 1
    assert result["top_missing_count"] == 1
    assert result["wide_spread_count"] == 1
    assert [alert["title"] for alert in result["alerts"]] == [
        "Cobertura parcial en posiciones relevantes",
        "Spreads anchos en posiciones relevantes",
        "Parte de la cobertura viene por fallback",
    ]


def test_build_market_snapshot_history_feature_context_enriches_rows_and_aggregates_weak_blocks():
    current_portafolio = {
        "inversion": [
            {
                "activo": SimpleNamespace(simbolo="GGAL", mercado="BCBA", valorizado=Decimal("1500")),
                "peso_porcentual": 55,
                "bloque_estrategico": "Argentina",
            }
        ],
        "fci_cash_management": [
            {
                "activo": SimpleNamespace(simbolo="ADBAICA", mercado="FCI", valorizado=Decimal("800")),
                "peso_porcentual": 20,
                "bloque_estrategico": "FCI Cash Management",
            }
        ],
    }

    result = build_market_snapshot_history_feature_context(
        history_rows=[
            {"simbolo": "GGAL", "mercado": "BCBA", "quality_status": "weak"},
            {"simbolo": "ADBAICA", "mercado": "FCI", "quality_status": "insufficient"},
        ],
        summary={"weak_count": 1, "insufficient_count": 1},
        current_portafolio=current_portafolio,
        top_limit=5,
        lookback_days=7,
    )

    assert result["has_history"] is True
    assert result["top_rows"][0]["simbolo"] == "GGAL"
    assert result["top_rows"][0]["bloque_estrategico"] == "Argentina"
    assert result["weak_blocks"] == [{"label": "Argentina", "value_total": Decimal("1500")}]
    assert [alert["title"] for alert in result["alerts"]] == [
        "Liquidez reciente debil en posiciones actuales",
        "Historial puntual todavia corto",
    ]


def test_build_portfolio_parking_feature_context_summarizes_visible_positions():
    result = build_portfolio_parking_feature_context(
        portafolio={
            "inversion": [
                {
                    "activo": SimpleNamespace(
                        parking={"fecha": "2026-03-26"},
                        valorizado=Decimal("900"),
                        disponible_inmediato=Decimal("0"),
                    ),
                    "bloque_estrategico": "Argentina",
                },
                {
                    "activo": SimpleNamespace(
                        parking=None,
                        valorizado=Decimal("300"),
                        disponible_inmediato=Decimal("300"),
                    ),
                    "bloque_estrategico": "USA",
                },
            ],
            "fci_cash_management": [],
        },
        top_limit=5,
        safe_percentage=lambda numerator, denominator: Decimal("50.00"),
    )

    assert result["has_visible_parking"] is True
    assert result["summary"]["parking_count"] == 1
    assert result["summary"]["parking_pct"] == Decimal("50.00")
    assert result["parking_blocks"] == [{"label": "Argentina", "value_total": Decimal("900")}]
    assert result["top_rows"][0]["parking_label"] == "Con parking"
