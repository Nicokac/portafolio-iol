from datetime import timedelta

import numpy as np
import pytest
from django.utils import timezone

from apps.core.services.portfolio.covariance_service import CovarianceService
from apps.core.services.portfolio.optimizer_markowitz import MarkowitzOptimizer
from apps.core.services.portfolio.risk_parity_service import RiskParityService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_snapshot(fecha, simbolo, valorizado):
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo=simbolo,
        descripcion=simbolo,
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo="USA",
        mercado="BCBA",
        tipo="CEDEARS",
        moneda="ARS",
    )


@pytest.mark.django_db
def test_covariance_service_builds_returns_and_covariance():
    now = timezone.now()
    for i, (aapl, spy) in enumerate([(1000, 1000), (1020, 1010), (1010, 1030), (1050, 1040)]):
        fecha = now - timedelta(days=3 - i)
        _make_snapshot(fecha, "AAPL", aapl)
        _make_snapshot(fecha, "SPY", spy)

    service = CovarianceService()
    returns = service.build_returns_matrix(["AAPL", "SPY"], lookback_days=30)
    exp = service.expected_returns_annualized(returns)
    cov = service.covariance_matrix_annualized(returns)

    assert not returns.empty
    assert exp.shape[0] == 2
    assert cov.shape == (2, 2)


@pytest.mark.django_db
def test_covariance_service_collapses_intraday_snapshots_to_daily_observations():
    now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    fixtures = [
        (1000, 1000),
        (1020, 1010),
        (1010, 1030),
    ]
    for i, (aapl, spy) in enumerate(fixtures):
        fecha = now - timedelta(days=2 - i)
        _make_snapshot(fecha, "AAPL", aapl)
        _make_snapshot(fecha + timedelta(hours=2), "AAPL", aapl)
        _make_snapshot(fecha, "SPY", spy)
        _make_snapshot(fecha + timedelta(hours=2), "SPY", spy)

    service = CovarianceService()
    returns = service.build_returns_matrix(["AAPL", "SPY"], lookback_days=30)

    assert len(returns.index) == 2
    assert list(returns.columns) == ["AAPL", "SPY"]


@pytest.mark.django_db
def test_covariance_service_uses_last_snapshot_of_day_for_each_asset():
    now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    day_one = now - timedelta(days=1)
    day_two = now

    _make_snapshot(day_one, "AAPL", 1000)
    _make_snapshot(day_one + timedelta(hours=4), "AAPL", 1050)
    _make_snapshot(day_one, "SPY", 2000)
    _make_snapshot(day_one + timedelta(hours=4), "SPY", 2100)

    _make_snapshot(day_two, "AAPL", 1100)
    _make_snapshot(day_two + timedelta(hours=4), "AAPL", 1200)
    _make_snapshot(day_two, "SPY", 2200)
    _make_snapshot(day_two + timedelta(hours=4), "SPY", 2310)

    service = CovarianceService()
    returns = service.build_returns_matrix(["AAPL", "SPY"], lookback_days=30)

    assert len(returns.index) == 1
    assert np.isclose(returns.iloc[0]["AAPL"], (1200 - 1050) / 1050)
    assert np.isclose(returns.iloc[0]["SPY"], (2310 - 2100) / 2100)


@pytest.mark.django_db
def test_covariance_service_returns_insufficient_history_for_single_return_observation():
    now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    day_one = now - timedelta(days=1)
    day_two = now

    _make_snapshot(day_one, "AAPL", 1000)
    _make_snapshot(day_one, "SPY", 2000)
    _make_snapshot(day_two, "AAPL", 1100)
    _make_snapshot(day_two, "SPY", 2200)

    service = CovarianceService()
    model_inputs = service.build_model_inputs(["AAPL", "SPY"], lookback_days=30)

    assert model_inputs["warning"] == "insufficient_history"
    assert model_inputs["observations"] == 1
    assert model_inputs["covariance_matrix"].size == 0


def test_markowitz_optimizer_returns_normalized_weights():
    expected_returns = np.array([0.10, 0.07, 0.05])
    covariance = np.array(
        [
            [0.04, 0.01, 0.00],
            [0.01, 0.03, 0.00],
            [0.00, 0.00, 0.01],
        ]
    )

    weights = MarkowitzOptimizer().optimize(expected_returns, covariance, target_return=0.08)

    assert len(weights) == 3
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_markowitz_optimizer_handles_empty_and_single_asset_inputs():
    optimizer = MarkowitzOptimizer()

    assert optimizer.optimize(np.array([]), np.array([])).size == 0
    assert np.array_equal(optimizer.optimize(np.array([0.1]), np.array([[0.04]])), np.array([1.0]))


def test_markowitz_optimizer_uses_max_sharpe_when_target_is_missing():
    expected_returns = np.array([0.10, 0.07])
    covariance = np.array([[0.04, 0.01], [0.01, 0.03]])

    weights = MarkowitzOptimizer().optimize(expected_returns, covariance)

    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_markowitz_optimizer_falls_back_when_system_is_degenerate():
    expected_returns = np.array([0.10, 0.10])
    covariance = np.array([[0.04, 0.00], [0.00, 0.04]])

    weights = MarkowitzOptimizer().optimize(expected_returns, covariance, target_return=0.10)

    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_markowitz_normalize_long_only_defaults_to_equal_weights_for_non_positive_total():
    weights = MarkowitzOptimizer._normalize_long_only(np.array([-2.0, -1.0, 0.0]))

    assert np.allclose(weights, np.array([1 / 3, 1 / 3, 1 / 3]))


def test_risk_parity_service_returns_inverse_vol_weights():
    covariance = np.array(
        [
            [0.09, 0.00, 0.00],
            [0.00, 0.04, 0.00],
            [0.00, 0.00, 0.01],
        ]
    )

    weights = RiskParityService().optimize(covariance)

    assert len(weights) == 3
    assert np.isclose(weights.sum(), 1.0)
    assert weights[2] > weights[1] > weights[0]


def test_risk_parity_service_handles_empty_and_single_asset_inputs():
    service = RiskParityService()

    assert service.optimize(np.array([])).size == 0
    assert np.array_equal(service.optimize(np.array([[0.09]])), np.array([1.0]))
