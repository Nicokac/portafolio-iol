import logging
from typing import Dict, List, Optional

import numpy as np

from apps.core.services.portfolio.covariance_service import CovarianceService
from apps.core.services.portfolio.optimizer_markowitz import MarkowitzOptimizer
from apps.core.services.portfolio.risk_parity_service import RiskParityService

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """Optimizador de portafolio con motores cuantitativos."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cov_service = CovarianceService()
        self.markowitz = MarkowitzOptimizer()
        self.risk_parity = RiskParityService()

    def optimize_risk_parity(self, activos: List[str], target_return: Optional[float] = None) -> Dict:
        logger.info("Optimizing portfolio with Risk Parity for assets: %s", activos)

        returns = self.cov_service.build_returns_matrix(activos)
        if returns.empty:
            if not activos:
                return {"error": "No hay activos válidos"}
            equal_weight = round(100 / len(activos), 2)
            return {
                "metodo": "risk_parity",
                "activos": activos,
                "pesos_optimos": {a: equal_weight for a in activos},
                "riesgo_portafolio": 0.0,
                "retorno_esperado": 0.0,
                "sharpe_ratio": 0.0,
                "warning": "Datos históricos insuficientes: se usaron pesos equitativos",
            }

        cov = self.cov_service.covariance_matrix_annualized(returns)
        exp_returns = self.cov_service.expected_returns_annualized(returns)

        weights = self.risk_parity.optimize(cov)
        weight_dict = {symbol: round(weight * 100, 2) for symbol, weight in zip(returns.columns, weights)}

        risk = float(np.sqrt(weights @ cov @ weights))
        expected = float(weights @ exp_returns)
        sharpe = (expected / risk) if risk > 0 else 0.0

        return {
            "metodo": "risk_parity",
            "activos": list(returns.columns),
            "pesos_optimos": weight_dict,
            "riesgo_portafolio": round(risk, 4),
            "retorno_esperado": round(expected, 4),
            "sharpe_ratio": round(sharpe, 4),
        }

    def optimize_markowitz(self, activos: List[str], target_return: float) -> Dict:
        logger.info("Optimizing portfolio with Markowitz for target return %s", target_return)

        returns = self.cov_service.build_returns_matrix(activos)
        if returns.empty:
            if not activos:
                return {"error": "No hay activos válidos"}
            equal_weight = round(100 / len(activos), 2)
            return {
                "metodo": "markowitz",
                "activos": activos,
                "retorno_objetivo": target_return,
                "pesos_optimos": {a: equal_weight for a in activos},
                "riesgo_portafolio": 0.0,
                "retorno_esperado": 0.0,
                "sharpe_ratio": 0.0,
                "warning": "Datos históricos insuficientes: se usaron pesos equitativos",
            }

        cov = self.cov_service.covariance_matrix_annualized(returns)
        exp_returns = self.cov_service.expected_returns_annualized(returns)
        weights = self.markowitz.optimize(exp_returns, cov, target_return=target_return)

        weight_dict = {symbol: round(weight * 100, 2) for symbol, weight in zip(returns.columns, weights)}
        risk = float(np.sqrt(weights @ cov @ weights))
        expected = float(weights @ exp_returns)
        sharpe = (expected / risk) if risk > 0 else 0.0

        return {
            "metodo": "markowitz",
            "activos": list(returns.columns),
            "retorno_objetivo": target_return,
            "pesos_optimos": weight_dict,
            "riesgo_portafolio": round(risk, 4),
            "retorno_esperado": round(expected, 4),
            "sharpe_ratio": round(sharpe, 4),
            "input_expected_returns": {
                symbol: round(float(mu), 4) for symbol, mu in zip(returns.columns, exp_returns)
            },
        }

    def optimize_target_allocation(self, target_allocations: Dict[str, float]) -> Dict:
        logger.info("Optimizing portfolio with target allocations: %s", target_allocations)
        total_weight = sum(target_allocations.values())
        if abs(total_weight - 100) > 0.1:
            return {"error": f"Los pesos objetivo deben sumar 100%. Suma actual: {total_weight}"}

        recommendations = []
        if "liquidez" in target_allocations and target_allocations["liquidez"] > 30:
            recommendations.append("Alta asignación a liquidez - considerar reducir para mejorar retorno")
        elif "liquidez" in target_allocations and target_allocations["liquidez"] < 5:
            recommendations.append("Baja liquidez - considerar aumentar para mayor seguridad")

        if "argentina" in target_allocations and target_allocations["argentina"] > 50:
            recommendations.append("Alta exposición Argentina - considerar diversificar internacionalmente")

        if "usa" in target_allocations and target_allocations["usa"] < 20:
            recommendations.append("Baja exposición USA - considerar aumentar para mayor estabilidad")

        return {
            "metodo": "target_allocation",
            "asignacion_objetivo": target_allocations,
            "validacion": "pesos_suman_100",
            "recomendaciones": recommendations,
        }
