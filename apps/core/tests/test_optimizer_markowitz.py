import numpy as np

from apps.core.services.portfolio.optimizer_markowitz import MarkowitzOptimizer


def test_markowitz_returns_empty_for_no_assets():
    result = MarkowitzOptimizer().optimize(np.array([]), np.array([]))
    assert result.size == 0


def test_markowitz_returns_full_weight_for_single_asset():
    result = MarkowitzOptimizer().optimize(np.array([0.12]), np.array([[0.04]]))
    assert np.array_equal(result, np.array([1.0]))


def test_markowitz_uses_max_sharpe_when_target_return_is_none():
    expected_returns = np.array([0.10, 0.20])
    covariance = np.array([[0.04, 0.0], [0.0, 0.09]])

    result = MarkowitzOptimizer().optimize(expected_returns, covariance, target_return=None)

    assert np.isclose(result.sum(), 1.0)
    assert result[0] > result[1]


def test_markowitz_falls_back_when_determinant_is_degenerate():
    expected_returns = np.array([0.10, 0.20])
    covariance = np.array([[1.0, 2.0], [2.0, 4.0]])

    result = MarkowitzOptimizer().optimize(expected_returns, covariance, target_return=0.15)

    assert np.isclose(result.sum(), 1.0)
    assert np.all(result >= 0)


def test_normalize_long_only_returns_equal_weights_when_total_is_non_positive():
    weights = np.array([-1.0, -2.0, -3.0])
    result = MarkowitzOptimizer._normalize_long_only(weights)
    assert np.allclose(result, np.array([1 / 3, 1 / 3, 1 / 3]))
