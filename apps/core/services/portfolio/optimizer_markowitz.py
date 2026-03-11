from typing import Optional

import numpy as np


class MarkowitzOptimizer:
    """
    Optimizador Markowitz.
    - Min var para retorno objetivo (si se pasa target_return)
    - Max Sharpe aproximado (rf=0) cuando no hay target_return
    """

    def optimize(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        target_return: Optional[float] = None,
    ) -> np.ndarray:
        n = len(expected_returns)
        if n == 0:
            return np.array([])
        if n == 1:
            return np.array([1.0])

        inv_cov = np.linalg.pinv(covariance_matrix)
        ones = np.ones(n)
        mu = expected_returns

        if target_return is None:
            # Max Sharpe aproximado: w ∝ inv(C) * mu
            raw = inv_cov @ mu
            return self._normalize_long_only(raw)

        a = ones @ inv_cov @ ones
        b = ones @ inv_cov @ mu
        c = mu @ inv_cov @ mu
        det = a * c - b * b

        if abs(det) < 1e-12:
            # Degenerado: fallback a max sharpe aproximado
            raw = inv_cov @ mu
            return self._normalize_long_only(raw)

        lam = (c - b * target_return) / det
        gam = (a * target_return - b) / det
        raw = inv_cov @ (lam * ones + gam * mu)
        return self._normalize_long_only(raw)

    @staticmethod
    def _normalize_long_only(weights: np.ndarray) -> np.ndarray:
        clipped = np.clip(weights, 0, None)
        total = clipped.sum()
        if total <= 0:
            return np.ones(len(clipped)) / len(clipped)
        return clipped / total
