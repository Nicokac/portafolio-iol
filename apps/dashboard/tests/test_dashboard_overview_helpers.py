from types import SimpleNamespace

from apps.dashboard.dashboard_overview import (
    build_current_enriched_portfolio,
    build_dashboard_kpis_payload,
    build_riesgo_portafolio_payload,
    build_riesgo_portafolio_detallado_payload,
)


def test_build_dashboard_kpis_payload_passes_portfolio_resumen_and_classified_data():
    result = build_dashboard_kpis_payload(
        get_latest_portafolio_data_fn=lambda: ["portfolio"],
        get_latest_resumen_data_fn=lambda: ["resumen"],
        get_portafolio_enriquecido_actual_fn=lambda: {"inversion": []},
        build_dashboard_kpis_fn=lambda portafolio, clasificado, resumen: {
            "portafolio": portafolio,
            "clasificado": clasificado,
            "resumen": resumen,
        },
    )

    assert result["portafolio"] == ["portfolio"]
    assert result["clasificado"] == {"inversion": []}
    assert result["resumen"] == ["resumen"]


def test_build_current_enriched_portfolio_passes_fci_profiles_when_available(db):
    result = build_current_enriched_portfolio(
        get_latest_portafolio_data_fn=lambda: [
            SimpleNamespace(simbolo="IOLCAMA", tipo="FondoComundeInversion"),
            SimpleNamespace(simbolo="AAPL", tipo="CEDEARS"),
        ],
        build_portafolio_enriquecido_fn=lambda portafolio, parametros, fci_profiles=None: {
            "portafolio": portafolio,
            "parametros": parametros,
            "fci_profiles": fci_profiles,
        },
        get_fci_profiles_by_symbols_fn=lambda simbolos: {"IOLCAMA": {"strategy_profile": {"classification": "cash_management"}}},
    )

    assert "IOLCAMA" in result["fci_profiles"]


def test_build_current_enriched_portfolio_passes_mep_profiles_for_cedears(db):
    result = build_current_enriched_portfolio(
        get_latest_portafolio_data_fn=lambda: [
            SimpleNamespace(simbolo="AAPL", tipo="CEDEARS"),
            SimpleNamespace(simbolo="AL30", tipo="TitulosPublicos"),
        ],
        build_portafolio_enriquecido_fn=lambda portafolio, parametros, fci_profiles=None, mep_profiles=None: {
            "portafolio": portafolio,
            "parametros": parametros,
            "fci_profiles": fci_profiles,
            "mep_profiles": mep_profiles,
        },
        get_mep_quotes_by_symbols_fn=lambda simbolos: {"AAPL": {"mep_price_ars": 1392.26}},
    )

    assert result["mep_profiles"] == {"AAPL": {"mep_price_ars": 1392.26}}


def test_build_riesgo_portafolio_payload_uses_kpis_liquidity_and_total():
    captured = {}

    build_riesgo_portafolio_payload(
        get_activos_invertidos_fn=lambda: [{"activo": SimpleNamespace(valorizado=100)}, {"activo": SimpleNamespace(valorizado=50)}],
        get_dashboard_kpis_fn=lambda: {"liquidez_operativa": 20, "total_iol": 170},
        build_riesgo_portafolio_fn=lambda **kwargs: captured.update(kwargs) or {"ok": True},
    )

    assert captured["total_portafolio"] == 150
    assert captured["liquidez_operativa"] == 20
    assert captured["total_iol"] == 170


def test_build_riesgo_portafolio_detallado_payload_uses_same_contract():
    captured = {}

    build_riesgo_portafolio_detallado_payload(
        get_activos_invertidos_fn=lambda: [{"activo": SimpleNamespace(valorizado=80)}],
        get_dashboard_kpis_fn=lambda: {"liquidez_operativa": 10, "total_iol": 90},
        build_riesgo_portafolio_detallado_fn=lambda **kwargs: captured.update(kwargs) or {"ok": True},
    )

    assert captured["total_portafolio"] == 80
    assert captured["liquidez_operativa"] == 10
    assert captured["total_iol"] == 90
