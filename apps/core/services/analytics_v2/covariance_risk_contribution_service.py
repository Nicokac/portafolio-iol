from __future__ import annotations

from copy import deepcopy

import numpy as np

from apps.core.services.analytics_v2.risk_contribution_service import RiskContributionService
from apps.core.services.analytics_v2.schemas import AnalyticsMetadata, RiskContributionItem, RiskContributionResult
from apps.core.services.observability import record_state
from apps.core.services.portfolio.covariance_service import CovarianceService


class CovarianceAwareRiskContributionService:
    """Risk contribution avanzado usando covarianza cuando la historia lo permite."""

    MIN_RETURN_OBSERVATIONS = 20
    MIN_ELIGIBLE_ASSETS = 3
    MIN_COVERAGE_PCT = 80.0
    MAJOR_UNCOVERED_WEIGHT_PCT = 10.0

    def __init__(
        self,
        base_service: RiskContributionService | None = None,
        covariance_service: CovarianceService | None = None,
    ):
        self.base_service = base_service or RiskContributionService()
        self.covariance_service = covariance_service or CovarianceService()

    def calculate(self, lookback_days: int = 252, top_n: int = 5) -> dict:
        positions = self.base_service._load_current_invested_positions()  # noqa: SLF001
        if not positions:
            return self._fallback_result(
                reason="empty_portfolio",
                lookback_days=lookback_days,
                top_n=top_n,
            )

        total_invested = sum(float(position.valorizado) for position in positions)
        symbols = [position.simbolo for position in positions]
        positions_by_symbol = {position.simbolo: position for position in positions}
        params = self.base_service._load_parameters(positions)  # noqa: SLF001

        model_inputs = self.covariance_service.build_model_inputs(symbols, lookback_days=lookback_days)
        returns = model_inputs.get("returns")
        observations = int(model_inputs.get("observations", 0) or 0)
        if model_inputs.get("warning") or returns is None or returns.empty:
            return self._fallback_result(
                reason="insufficient_covariance_history",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
            )

        covered_symbols = [symbol for symbol in returns.columns if symbol in positions_by_symbol]
        covered_positions = [positions_by_symbol[symbol] for symbol in covered_symbols]
        covered_total = sum(float(position.valorizado) for position in covered_positions)
        coverage_pct = (covered_total / total_invested * 100.0) if total_invested > 0 else 0.0
        uncovered_positions = [position for position in positions if position.simbolo not in covered_symbols]
        max_uncovered_weight = max(
            ((float(position.valorizado) / total_invested) * 100.0 for position in uncovered_positions),
            default=0.0,
        )

        if observations < self.MIN_RETURN_OBSERVATIONS or len(covered_symbols) < self.MIN_ELIGIBLE_ASSETS:
            return self._fallback_result(
                reason="insufficient_covariance_history",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
                coverage_pct=coverage_pct,
                covered_symbols=covered_symbols,
                excluded_symbols=[position.simbolo for position in uncovered_positions],
            )

        if coverage_pct < self.MIN_COVERAGE_PCT or max_uncovered_weight > self.MAJOR_UNCOVERED_WEIGHT_PCT:
            return self._fallback_result(
                reason="insufficient_covariance_coverage",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
                coverage_pct=coverage_pct,
                covered_symbols=covered_symbols,
                excluded_symbols=[position.simbolo for position in uncovered_positions],
            )

        covariance_matrix = model_inputs.get("covariance_matrix")
        if covariance_matrix is None or getattr(covariance_matrix, "size", 0) == 0:
            return self._fallback_result(
                reason="degenerate_covariance_matrix",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
                coverage_pct=coverage_pct,
                covered_symbols=covered_symbols,
            )

        weights = np.array([float(position.valorizado) for position in covered_positions], dtype=float)
        weights = weights / weights.sum()

        portfolio_variance = float(weights @ covariance_matrix @ weights)
        if not np.isfinite(portfolio_variance) or portfolio_variance <= 0:
            return self._fallback_result(
                reason="non_positive_portfolio_volatility",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
                coverage_pct=coverage_pct,
                covered_symbols=covered_symbols,
            )

        portfolio_volatility = float(np.sqrt(portfolio_variance))
        marginal_risk = covariance_matrix @ weights / portfolio_volatility
        total_risk = weights * marginal_risk
        total_risk_sum = float(total_risk.sum())

        if not np.isfinite(total_risk_sum) or total_risk_sum <= 0:
            return self._fallback_result(
                reason="non_positive_total_risk_contribution",
                lookback_days=lookback_days,
                top_n=top_n,
                observations=observations,
                coverage_pct=coverage_pct,
                covered_symbols=covered_symbols,
            )

        items = []
        for idx, position in enumerate(covered_positions):
            param = params.get(position.simbolo)
            contribution_pct = float(total_risk[idx] / total_risk_sum * 100.0)
            standalone_vol = float(np.sqrt(max(float(covariance_matrix[idx, idx]), 0.0)) * 100.0)
            items.append(
                RiskContributionItem(
                    symbol=position.simbolo,
                    weight_pct=round((float(position.valorizado) / total_invested) * 100.0, 2),
                    volatility_proxy=round(standalone_vol, 2),
                    risk_score=round(float(total_risk[idx]), 6),
                    contribution_pct=round(contribution_pct, 2),
                    sector=param.sector if param else "unknown",
                    country=param.pais_exposicion if param else "unknown",
                    asset_type=self.base_service._resolve_asset_type(position, param),  # noqa: SLF001
                    used_volatility_fallback=False,
                )
            )

        result = RiskContributionResult(
            items=items,
            by_sector=self.base_service._aggregate_items(items, "sector"),  # noqa: SLF001
            by_country=self.base_service._aggregate_items(items, "country", normalizer=self.base_service._aggregate_items.__globals__["normalize_country_label"]),  # noqa: SLF001
            by_asset_type=self.base_service._aggregate_items(items, "asset_type"),  # noqa: SLF001
            top_contributors=self.base_service._aggregate_items.__globals__["rank_top_items"](items, lambda item: item.contribution_pct, limit=top_n),  # noqa: SLF001
            metadata=AnalyticsMetadata(
                methodology=(
                    "portfolio_vol = sqrt(w'Sw); marginal_risk = (Sw)/portfolio_vol; "
                    "total_risk = w * marginal_risk; contribution_pct = total_risk / sum(total_risk)"
                ),
                data_basis="covered_invested_portfolio_market_value",
                limitations=(
                    "Uses covariance only when daily history and invested coverage are sufficient. "
                    "Falls back to MVP proxy model otherwise."
                ),
                confidence="high" if coverage_pct >= 99.9 and observations >= 60 else "medium",
                warnings=[],
            ),
        ).to_dict()
        result.update(
            {
                "model_variant": "covariance_aware",
                "covariance_observations": observations,
                "portfolio_volatility_proxy": round(portfolio_volatility * 100.0, 2),
                "coverage_pct": round(coverage_pct, 2),
                "covered_symbols": covered_symbols,
                "excluded_symbols": [position.simbolo for position in uncovered_positions],
            }
        )
        self._record_model_variant(
            model_variant="covariance_aware",
            observations=observations,
            coverage_pct=coverage_pct,
        )
        return result

    def build_recommendation_signals(self, lookback_days: int = 252, top_n: int = 5) -> list[dict]:
        result = self.calculate(lookback_days=lookback_days, top_n=top_n)
        return self.base_service._build_recommendation_signals_from_result(result)  # noqa: SLF001

    def _fallback_result(
        self,
        *,
        reason: str,
        lookback_days: int,
        top_n: int,
        observations: int = 0,
        coverage_pct: float = 0.0,
        covered_symbols: list[str] | None = None,
        excluded_symbols: list[str] | None = None,
    ) -> dict:
        result = deepcopy(self.base_service.calculate(lookback_days=min(lookback_days, 90), top_n=top_n))
        metadata = result.setdefault("metadata", {})
        warnings = list(metadata.get("warnings", []))
        if reason not in warnings:
            warnings.append(reason)
        metadata["warnings"] = warnings
        if metadata.get("confidence") == "high":
            metadata["confidence"] = "medium"
        result.update(
            {
                "model_variant": "mvp_proxy",
                "covariance_observations": int(observations),
                "portfolio_volatility_proxy": None,
                "coverage_pct": round(coverage_pct, 2),
                "covered_symbols": covered_symbols or [],
                "excluded_symbols": excluded_symbols or [],
            }
        )
        self._record_model_variant(
            model_variant="mvp_proxy",
            observations=observations,
            coverage_pct=coverage_pct,
            reason=reason,
        )
        return result

    @staticmethod
    def _record_model_variant(
        *,
        model_variant: str,
        observations: int,
        coverage_pct: float,
        reason: str | None = None,
    ) -> None:
        record_state(
            "analytics_v2.risk_contribution.model_variant",
            model_variant,
            extra={
                "observations": int(observations),
                "coverage_pct": round(float(coverage_pct), 2),
                "reason": reason,
            },
        )
