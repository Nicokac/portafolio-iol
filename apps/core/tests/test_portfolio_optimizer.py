import numpy as np
import pandas as pd
import pytest

from apps.core.services.portfolio_optimizer import PortfolioOptimizer


@pytest.fixture
def optimizer():
    return PortfolioOptimizer()


def test_optimize_risk_parity_returns_error_without_assets(optimizer, monkeypatch):
    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": pd.DataFrame(),
            "covariance_matrix": np.array([]),
            "expected_returns": np.array([]),
        },
    )

    result = optimizer.optimize_risk_parity([])

    assert result == {"error": "No hay activos válidos"}


def test_optimize_risk_parity_uses_equal_weights_when_returns_are_empty(optimizer, monkeypatch):
    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": pd.DataFrame(),
            "covariance_matrix": np.array([]),
            "expected_returns": np.array([]),
        },
    )

    result = optimizer.optimize_risk_parity(["SPY", "EEM", "QQQ"])

    assert result["metodo"] == "risk_parity"
    assert result["pesos_optimos"] == {"SPY": 33.33, "EEM": 33.33, "QQQ": 33.33}
    assert result["warning"] == "Datos históricos insuficientes: se usaron pesos equitativos"


def test_optimize_risk_parity_returns_quantitative_metrics(optimizer, monkeypatch):
    returns = pd.DataFrame(
        [[0.01, 0.02], [0.03, 0.01]],
        columns=["SPY", "EEM"],
    )
    covariance = np.array([[0.04, 0.01], [0.01, 0.09]])
    expected_returns = np.array([0.12, 0.18])

    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": returns,
            "covariance_matrix": covariance,
            "expected_returns": expected_returns,
        },
    )
    monkeypatch.setattr(
        optimizer.risk_parity,
        "optimize",
        lambda cov: np.array([0.6, 0.4]),
    )

    result = optimizer.optimize_risk_parity(["SPY", "EEM"])

    assert result["activos"] == ["SPY", "EEM"]
    assert result["pesos_optimos"] == {"SPY": 60.0, "EEM": 40.0}
    assert result["riesgo_portafolio"] == 0.1833
    assert result["retorno_esperado"] == 0.144
    assert result["sharpe_ratio"] == 0.7856


def test_optimize_markowitz_returns_error_without_assets(optimizer, monkeypatch):
    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": pd.DataFrame(),
            "covariance_matrix": np.array([]),
            "expected_returns": np.array([]),
        },
    )

    result = optimizer.optimize_markowitz([], target_return=0.1)

    assert result == {"error": "No hay activos válidos"}


def test_optimize_markowitz_uses_equal_weights_when_returns_are_empty(optimizer, monkeypatch):
    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": pd.DataFrame(),
            "covariance_matrix": np.array([]),
            "expected_returns": np.array([]),
        },
    )

    result = optimizer.optimize_markowitz(["SPY", "EEM"], target_return=0.08)

    assert result["metodo"] == "markowitz"
    assert result["retorno_objetivo"] == 0.08
    assert result["pesos_optimos"] == {"SPY": 50.0, "EEM": 50.0}
    assert result["warning"] == "Datos históricos insuficientes: se usaron pesos equitativos"


def test_optimize_markowitz_returns_expected_inputs(optimizer, monkeypatch):
    returns = pd.DataFrame(
        [[0.01, 0.02], [0.03, 0.01]],
        columns=["SPY", "EEM"],
    )
    covariance = np.array([[0.04, 0.01], [0.01, 0.09]])
    expected_returns = np.array([0.12, 0.18])

    monkeypatch.setattr(
        optimizer.cov_service,
        "build_model_inputs",
        lambda activos: {
            "returns": returns,
            "covariance_matrix": covariance,
            "expected_returns": expected_returns,
        },
    )
    monkeypatch.setattr(
        optimizer.markowitz,
        "optimize",
        lambda exp_returns, cov, target_return: np.array([0.25, 0.75]),
    )

    result = optimizer.optimize_markowitz(["SPY", "EEM"], target_return=0.15)

    assert result["activos"] == ["SPY", "EEM"]
    assert result["pesos_optimos"] == {"SPY": 25.0, "EEM": 75.0}
    assert result["retorno_objetivo"] == 0.15
    assert result["input_expected_returns"] == {"SPY": 0.12, "EEM": 0.18}
    assert result["riesgo_portafolio"] == 0.2385
    assert result["retorno_esperado"] == 0.165
    assert result["sharpe_ratio"] == 0.6919


def test_optimize_target_allocation_rejects_invalid_total(optimizer):
    result = optimizer.optimize_target_allocation(
        {"liquidez": 20, "usa": 40, "argentina": 20}
    )

    assert result == {"error": "Los pesos objetivo deben sumar 100%. Suma actual: 80"}


def test_optimize_target_allocation_generates_recommendations(optimizer):
    result = optimizer.optimize_target_allocation(
        {"liquidez": 35, "usa": 15, "argentina": 50}
    )

    assert result["metodo"] == "target_allocation"
    assert result["validacion"] == "pesos_suman_100"
    assert result["recomendaciones"] == [
        "Alta asignación a liquidez - considerar reducir para mejorar retorno",
        "Baja exposición USA - considerar aumentar para mayor estabilidad",
    ]


def test_optimize_target_allocation_handles_low_liquidity_and_high_argentina(optimizer):
    result = optimizer.optimize_target_allocation(
        {"liquidez": 4, "usa": 20, "argentina": 56, "emerging": 20}
    )

    assert result["recomendaciones"] == [
        "Baja liquidez - considerar aumentar para mayor seguridad",
        "Alta exposición Argentina - considerar diversificar internacionalmente",
    ]
