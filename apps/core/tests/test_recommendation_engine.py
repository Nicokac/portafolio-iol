import pytest

from apps.core.services.recommendation_engine import RecommendationEngine


@pytest.fixture
def engine():
    return RecommendationEngine()


def test_generate_recommendations_uses_dashboard_kpis_when_portfolio_missing(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_dashboard_kpis",
        lambda: {"total_iol": 1000, "liquidez_operativa": 100, "fci_cash_management": 0},
    )
    monkeypatch.setattr(engine, "_analyze_liquidity", lambda portfolio: {"tipo": "liq"})
    monkeypatch.setattr(engine, "_analyze_geographic_concentration", lambda portfolio: [])
    monkeypatch.setattr(engine, "_analyze_sector_concentration", lambda portfolio: [])
    monkeypatch.setattr(engine, "_analyze_risk_profile", lambda portfolio: None)
    monkeypatch.setattr(engine, "_analyze_performance", lambda portfolio: None)

    result = engine.generate_recommendations()

    assert result == [{"tipo": "liq"}]


def test_generate_recommendations_returns_combined_output(engine, monkeypatch):
    monkeypatch.setattr(engine, "_analyze_liquidity", lambda portfolio: {"tipo": "liq"})
    monkeypatch.setattr(
        engine,
        "_analyze_geographic_concentration",
        lambda portfolio: [{"tipo": "geo_1"}, {"tipo": "geo_2"}],
    )
    monkeypatch.setattr(
        engine,
        "_analyze_sector_concentration",
        lambda portfolio: [{"tipo": "sector"}],
    )
    monkeypatch.setattr(engine, "_analyze_risk_profile", lambda portfolio: {"tipo": "risk"})
    monkeypatch.setattr(engine, "_analyze_performance", lambda portfolio: {"tipo": "perf"})

    result = engine.generate_recommendations({"total_iol": 100})

    assert result == [
        {"tipo": "liq"},
        {"tipo": "geo_1"},
        {"tipo": "geo_2"},
        {"tipo": "sector"},
        {"tipo": "risk"},
        {"tipo": "perf"},
    ]


def test_generate_recommendations_returns_error_payload_on_exception(engine, monkeypatch):
    monkeypatch.setattr(engine, "_analyze_liquidity", lambda portfolio: 1 / 0)

    result = engine.generate_recommendations({"total_iol": 100})

    assert result == [
        {
            "tipo": "error",
            "mensaje": "Error generando recomendaciones: division by zero",
        }
    ]


@pytest.mark.parametrize(
    ("portfolio", "expected_type", "expected_priority"),
    [
        (
            {"total_iol": 1000, "liquidez_operativa": 250, "fci_cash_management": 100},
            "liquidez_excesiva",
            "media",
        ),
        (
            {"total_iol": 1000, "liquidez_operativa": 20, "fci_cash_management": 0},
            "liquidez_insuficiente",
            "alta",
        ),
    ],
)
def test_analyze_liquidity_returns_expected_recommendations(
    engine, portfolio, expected_type, expected_priority
):
    result = engine._analyze_liquidity(portfolio)

    assert result["tipo"] == expected_type
    assert result["prioridad"] == expected_priority


def test_analyze_liquidity_returns_none_on_safe_range(engine):
    result = engine._analyze_liquidity(
        {"total_iol": 1000, "liquidez_operativa": 100, "fci_cash_management": 50}
    )

    assert result is None


def test_analyze_geographic_concentration_returns_argentina_and_usa_recommendations(
    engine, monkeypatch
):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_pais",
        lambda: {"Argentina": 65.0, "USA": 10.0, "Europa": 25.0},
    )

    result = engine._analyze_geographic_concentration({})

    assert [item["tipo"] for item in result] == [
        "concentracion_argentina_alta",
        "exposicion_usa_baja",
    ]


def test_analyze_geographic_concentration_returns_empty_on_exception(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_pais",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = engine._analyze_geographic_concentration({})

    assert result == []


def test_analyze_sector_concentration_detects_tech_and_financial_cases(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_sector",
        lambda: {
            "Consumo": 20.0,
            "Finanzas / Holding": 25.0,
            "Banco Local": 20.0,
            "Utilities": 35.0,
        },
    )

    result = engine._analyze_sector_concentration({})

    assert [item["tipo"] for item in result] == [
        "tecnologia_subponderada",
        "financiero_sobreponderado",
    ]


def test_analyze_risk_profile_detects_high_concentration(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_patrimonial",
        lambda: {"Cash": 80.0, "ETF": 20.0},
    )

    result = engine._analyze_risk_profile({})

    assert result["tipo"] == "riesgo_concentracion_alto"
    assert result["prioridad"] == "alta"


def test_analyze_risk_profile_detects_excellent_diversification(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_patrimonial",
        lambda: {f"asset_{idx}": 5.0 for idx in range(20)},
    )

    result = engine._analyze_risk_profile({})

    assert result["tipo"] == "diversificacion_excelente"
    assert result["prioridad"] == "baja"


def test_analyze_performance_returns_static_recommendation(engine):
    result = engine._analyze_performance({})

    assert result["tipo"] == "revision_rendimiento"
    assert result["prioridad"] == "baja"
