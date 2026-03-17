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
    monkeypatch.setattr(engine, "_analyze_analytics_v2", lambda: [])

    result = engine.generate_recommendations()

    assert result == [{"tipo": "liq"}]


def test_generate_recommendations_returns_combined_output(engine, monkeypatch):
    monkeypatch.setattr(engine, "_analyze_liquidity", lambda portfolio: {"tipo": "liq", "prioridad": "media"})
    monkeypatch.setattr(
        engine,
        "_analyze_geographic_concentration",
        lambda portfolio: [{"tipo": "geo_1", "prioridad": "alta"}, {"tipo": "geo_2", "prioridad": "media"}],
    )
    monkeypatch.setattr(
        engine,
        "_analyze_sector_concentration",
        lambda portfolio: [{"tipo": "sector", "prioridad": "media"}],
    )
    monkeypatch.setattr(engine, "_analyze_risk_profile", lambda portfolio: {"tipo": "risk", "prioridad": "alta"})
    monkeypatch.setattr(engine, "_analyze_performance", lambda portfolio: {"tipo": "perf", "prioridad": "baja"})
    monkeypatch.setattr(engine, "_analyze_analytics_v2", lambda: [{"tipo": "v2", "prioridad": "alta", "origen": "analytics_v2"}])

    result = engine.generate_recommendations({"total_iol": 100})

    assert [item["tipo"] for item in result] == [
        "v2",
        "geo_1",
        "risk",
        "liq",
        "geo_2",
        "sector",
        "perf",
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
    engine, portfolio, expected_type, expected_priority, monkeypatch
):
    monkeypatch.setattr(
        engine,
        "_build_diversification_categories",
        lambda: ["Healthcare", "Industrials", "Small Caps", "Utilities"],
    )
    result = engine._analyze_liquidity(portfolio)

    assert result["tipo"] == expected_type
    assert result["prioridad"] == expected_priority

    if expected_type == "liquidez_excesiva":
        assert "Liquidez total = liquidez operativa + cash management" in result["descripcion"]


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


def test_analyze_sector_concentration_detects_diversification_and_financial_cases(engine, monkeypatch):
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
        "diversificacion_sectorial",
        "financiero_sobreponderado",
    ]
    diversification = result[1]
    assert "Healthcare" in diversification["activos_sugeridos"]
    assert "Industrials" in diversification["activos_sugeridos"]
    assert "Small Caps" in diversification["activos_sugeridos"]


def test_analyze_risk_profile_detects_high_concentration(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_patrimonial",
        lambda: {"Cash": 80.0, "ETF": 20.0},
    )

    result = engine._analyze_risk_profile({})

    assert result["tipo"] == "riesgo_concentracion_alto"
    assert result["prioridad"] == "alta"


def test_analyze_risk_profile_detects_medium_concentration(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.get_concentracion_patrimonial",
        lambda: {"Cash": 50.0, "ETF": 30.0, "Bond": 20.0},
    )

    result = engine._analyze_risk_profile({})

    assert result["tipo"] == "riesgo_concentracion_media"
    assert result["prioridad"] == "media"


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


def test_analyze_analytics_v2_maps_signals_to_recommendations(engine, monkeypatch):
    monkeypatch.setattr(
        engine,
        "_build_risk_contribution_signals",
        lambda: [
            {
                "signal_key": "risk_concentration_top_assets",
                "severity": "high",
                "title": "Riesgo concentrado en pocos activos",
                "description": "Tres activos dominan el riesgo proxy.",
                "affected_scope": "portfolio",
                "evidence": {"top_symbols": ["AAPL", "MSFT", "NVDA"]},
                "risk_model_variant": "covariance_aware",
            }
        ],
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.ScenarioAnalysisService",
        lambda: type("DummyScenario", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.FactorExposureService",
        lambda: type("DummyFactor", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.StressFragilityService",
        lambda: type("DummyStress", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.ExpectedReturnService",
        lambda: type("DummyExpected", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.LocalMacroSignalsService",
        lambda: type("DummyLocalMacro", (), {"build_recommendation_signals": lambda self: []})(),
    )

    result = engine._analyze_analytics_v2()

    assert len(result) == 1
    assert result[0]["tipo"] == "analytics_v2_risk_concentration_top_assets"
    assert result[0]["prioridad"] == "alta"
    assert result[0]["origen"] == "analytics_v2"
    assert result[0]["activos_sugeridos"] == ["AAPL", "MSFT", "NVDA"]
    assert result[0]["modelo_riesgo"] == "covariance_aware"


def test_analyze_analytics_v2_returns_empty_on_exception(engine, monkeypatch):
    monkeypatch.setattr(
        engine,
        "_build_risk_contribution_signals",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert engine._analyze_analytics_v2() == []


def test_build_signal_actions_returns_country_risk_actions(engine):
    actions = engine._build_signal_actions(
        {
            "signal_key": "local_country_risk_high",
            "affected_scope": "portfolio",
        }
    )

    assert actions == [
        "Revisar si el peso de soberanos locales sigue siendo consistente con el nivel actual de riesgo país",
        "Reducir dependencia de crédito soberano argentino si el bloque local ya es material",
    ]


def test_build_signal_actions_returns_single_name_sovereign_actions(engine):
    actions = engine._build_signal_actions(
        {
            "signal_key": "local_sovereign_single_name_concentration",
            "affected_scope": "portfolio",
        }
    )

    assert actions == [
        "Reducir dependencia de un solo bono soberano dentro del bloque argentino",
        "Distribuir el riesgo local entre instrumentos con drivers distintos si la convicción sigue siendo local",
    ]


def test_build_signal_actions_returns_hard_dollar_sovereign_actions(engine):
    actions = engine._build_signal_actions(
        {
            "signal_key": "local_sovereign_hard_dollar_dependence",
            "affected_scope": "portfolio",
        }
    )

    assert actions == [
        "Revisar si el bloque de renta fija local depende demasiado de soberanos hard dollar",
        "Balancear el bloque local con CER u otras exposiciones argentinas menos correlacionadas",
    ]


def test_analyze_analytics_v2_includes_local_macro_signals(engine, monkeypatch):
    monkeypatch.setattr(engine, "_build_risk_contribution_signals", lambda: [])
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.ScenarioAnalysisService",
        lambda: type("DummyScenario", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.FactorExposureService",
        lambda: type("DummyFactor", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.StressFragilityService",
        lambda: type("DummyStress", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.ExpectedReturnService",
        lambda: type("DummyExpected", (), {"build_recommendation_signals": lambda self: []})(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.LocalMacroSignalsService",
        lambda: type(
            "DummyLocalMacro",
            (),
            {
                "build_recommendation_signals": lambda self: [
                    {
                        "signal_key": "local_sovereign_risk_excess",
                        "severity": "medium",
                        "title": "Riesgo soberano local concentrado",
                        "description": "Los soberanos locales pesan demasiado.",
                        "affected_scope": "portfolio",
                        "evidence": {"argentina_weight_pct": 30.0},
                    }
                ]
            },
        )(),
    )

    result = engine._analyze_analytics_v2()

    assert len(result) == 1
    assert result[0]["tipo"] == "analytics_v2_local_sovereign_risk_excess"
    assert result[0]["prioridad"] == "media"
    assert result[0]["origen"] == "analytics_v2"
    assert "soberanos locales" in result[0]["titulo"].lower() or "soberano" in result[0]["titulo"].lower()


def test_build_signal_actions_returns_specific_actions_for_fx_gap(engine):
    actions = engine._build_signal_actions({"signal_key": "local_fx_gap_high"})

    assert any("brecha" in action.lower() for action in actions)
    assert any("argentina" in action.lower() or "local" in action.lower() for action in actions)


def test_build_risk_contribution_signals_prefers_covariance_when_active(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.CovarianceAwareRiskContributionService",
        lambda: type(
            "DummyCovarianceRisk",
            (),
            {
                "calculate": lambda self, top_n=5: {"model_variant": "covariance_aware"},
                "build_recommendation_signals": lambda self, top_n=5: [
                    {
                        "signal_key": "risk_concentration_top_assets",
                        "severity": "high",
                        "title": "Riesgo concentrado en pocos activos",
                        "description": "Cluster correlacionado dominante.",
                        "affected_scope": "portfolio",
                        "evidence": {"top_symbols": ["AAPL", "MSFT"]},
                    }
                ],
            },
        )(),
    )

    result = engine._build_risk_contribution_signals()

    assert len(result) == 1
    assert result[0]["risk_model_variant"] == "covariance_aware"


def test_build_risk_contribution_signals_falls_back_to_mvp_when_covariance_is_not_active(engine, monkeypatch):
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.CovarianceAwareRiskContributionService",
        lambda: type(
            "DummyCovarianceRisk",
            (),
            {
                "calculate": lambda self, top_n=5: {"model_variant": "mvp_proxy"},
                "build_recommendation_signals": lambda self, top_n=5: [],
            },
        )(),
    )
    monkeypatch.setattr(
        "apps.core.services.recommendation_engine.RiskContributionService",
        lambda: type(
            "DummyRisk",
            (),
            {
                "build_recommendation_signals": lambda self, top_n=5: [
                    {
                        "signal_key": "risk_concentration_argentina",
                        "severity": "high",
                        "title": "Riesgo concentrado en Argentina",
                        "description": "El riesgo local domina el portafolio.",
                        "affected_scope": "country",
                        "evidence": {"country": "Argentina"},
                    }
                ]
            },
        )(),
    )

    result = engine._build_risk_contribution_signals()

    assert len(result) == 1
    assert result[0]["signal_key"] == "risk_concentration_argentina"
    assert result[0]["risk_model_variant"] == "mvp_proxy"


def test_prioritize_recommendations_prefers_analytics_v2_for_overlapping_topics(engine):
    recommendations = [
        {
            "tipo": "liquidez_excesiva",
            "prioridad": "media",
            "titulo": "Liquidez Excesiva",
        },
        {
            "tipo": "analytics_v2_expected_return_liquidity_drag",
            "prioridad": "media",
            "titulo": "Costo de oportunidad por liquidez",
            "origen": "analytics_v2",
            "activos_sugeridos": ["SPY"],
        },
        {
            "tipo": "concentracion_argentina_alta",
            "prioridad": "alta",
            "titulo": "Alta Concentracion Argentina",
        },
        {
            "tipo": "analytics_v2_risk_concentration_argentina",
            "prioridad": "alta",
            "titulo": "Riesgo concentrado en Argentina",
            "origen": "analytics_v2",
            "activos_sugeridos": ["GGAL", "AL30"],
        },
    ]

    result = engine._prioritize_recommendations(recommendations)

    assert [item["tipo"] for item in result] == [
        "analytics_v2_risk_concentration_argentina",
        "analytics_v2_expected_return_liquidity_drag",
    ]


def test_prioritize_recommendations_keeps_distinct_topics(engine):
    recommendations = [
        {"tipo": "diversificacion_sectorial", "prioridad": "media"},
        {
            "tipo": "analytics_v2_factor_defensive_gap",
            "prioridad": "media",
            "origen": "analytics_v2",
        },
        {"tipo": "revision_rendimiento", "prioridad": "baja"},
    ]

    result = engine._prioritize_recommendations(recommendations)

    assert [item["tipo"] for item in result] == [
        "analytics_v2_factor_defensive_gap",
        "diversificacion_sectorial",
        "revision_rendimiento",
    ]


def test_prioritize_recommendations_prefers_local_liquidity_signal_for_overlapping_liquidity_topics(engine):
    recommendations = [
        {
            "tipo": "liquidez_excesiva",
            "prioridad": "media",
            "titulo": "Liquidez Excesiva",
        },
        {
            "tipo": "analytics_v2_expected_return_liquidity_drag",
            "prioridad": "media",
            "titulo": "Costo de oportunidad por liquidez",
            "origen": "analytics_v2",
        },
        {
            "tipo": "analytics_v2_local_liquidity_real_carry_negative",
            "prioridad": "media",
            "titulo": "Liquidez en pesos con carry real debil",
            "origen": "analytics_v2",
        },
    ]

    result = engine._prioritize_recommendations(recommendations)

    assert [item["tipo"] for item in result] == [
        "analytics_v2_local_liquidity_real_carry_negative",
    ]


def test_prioritize_recommendations_prefers_local_sovereign_signal_for_overlapping_argentina_topics(engine):
    recommendations = [
        {
            "tipo": "concentracion_argentina_alta",
            "prioridad": "alta",
            "titulo": "Alta Concentracion Argentina",
        },
        {
            "tipo": "analytics_v2_risk_concentration_argentina",
            "prioridad": "alta",
            "titulo": "Riesgo concentrado en Argentina",
            "origen": "analytics_v2",
        },
        {
            "tipo": "analytics_v2_local_sovereign_risk_excess",
            "prioridad": "alta",
            "titulo": "Riesgo soberano local concentrado",
            "origen": "analytics_v2",
        },
        {
            "tipo": "analytics_v2_local_inflation_hedge_gap",
            "prioridad": "media",
            "titulo": "Cobertura inflacionaria local acotada",
            "origen": "analytics_v2",
        },
    ]

    result = engine._prioritize_recommendations(recommendations)

    assert [item["tipo"] for item in result] == [
        "analytics_v2_local_sovereign_risk_excess",
        "analytics_v2_local_inflation_hedge_gap",
    ]

