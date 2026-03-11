import numpy as np


class RiskParityService:
    """Asignación por riesgo usando volatilidad marginal (diag de covarianza)."""

    def optimize(self, covariance_matrix: np.ndarray) -> np.ndarray:
        n = covariance_matrix.shape[0]
        if n == 0:
            return np.array([])
        if n == 1:
            return np.array([1.0])

        vol = np.sqrt(np.clip(np.diag(covariance_matrix), 1e-12, None))
        inv_vol = 1.0 / vol
        weights = inv_vol / inv_vol.sum()
        return weights
