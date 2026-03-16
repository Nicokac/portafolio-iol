from __future__ import annotations

from apps.core.services.analytics_v2.scenario_analysis_service import ScenarioAnalysisService
from apps.core.services.analytics_v2.schemas import AnalyticsMetadata, RecommendationSignal
from apps.core.services.local_macro_series_service import LocalMacroSeriesService


class LocalMacroSignalsService:
    """Señales locales simples de macro y carry para carteras con exposición argentina."""

    HIGH_ARGENTINA_EXPOSURE_THRESHOLD = 25.0
    HIGH_ARS_LIQUIDITY_THRESHOLD = 15.0
    VERY_HIGH_ARS_LIQUIDITY_THRESHOLD = 30.0
    NEGATIVE_REAL_CARRY_GAP_THRESHOLD = 1.0
    LARGE_NEGATIVE_REAL_CARRY_GAP_THRESHOLD = 5.0
    LOW_CER_HEDGE_THRESHOLD = 8.0
    HIGH_SOVEREIGN_RISK_THRESHOLD = 10.0
    VERY_HIGH_SOVEREIGN_RISK_THRESHOLD = 15.0

    def __init__(
        self,
        positions_loader: ScenarioAnalysisService | None = None,
        macro_service: LocalMacroSeriesService | None = None,
    ):
        self.positions_loader = positions_loader or ScenarioAnalysisService()
        self.macro_service = macro_service or LocalMacroSeriesService()

    def calculate(self) -> dict:
        positions = self._load_current_positions()
        if not positions:
            return {
                "summary": {},
                "metadata": AnalyticsMetadata(
                    methodology="local macro signals over current normalized positions and persisted macro references",
                    data_basis="current_positions_market_value + MacroSeriesSnapshot",
                    limitations="No current positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ).to_dict(),
            }

        context = self.macro_service.get_context_summary()
        total_market_value = sum(float(position.market_value) for position in positions)
        argentina_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: (position.country or "").strip().lower() == "argentina",
        )
        ars_liquidity_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: self._is_ars_cash_like(position),
        )
        cer_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: (position.sector or "").strip().lower() == "cer",
        )
        argentina_bond_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: (
                (position.country or "").strip().lower() == "argentina"
                and (position.asset_type or "").strip().lower() == "bond"
            ),
        )
        sovereign_bond_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: (position.sector or "").strip().lower() == "soberano",
        )

        badlar_pct = self._as_float(context.get("badlar_privada"))
        ipc_yoy_pct = self._as_float(context.get("ipc_nacional_variation_yoy"))
        ipc_ytd_pct = self._as_float(context.get("ipc_nacional_variation_ytd"))
        usdars_oficial = self._as_float(context.get("usdars_oficial"))
        badlar_real_carry_pct = None
        if badlar_pct is not None and ipc_yoy_pct is not None:
            badlar_real_carry_pct = round(badlar_pct - ipc_yoy_pct, 2)

        warnings: list[str] = []
        if badlar_pct is None:
            warnings.append("missing_macro_reference:badlar_privada")
        if ipc_yoy_pct is None:
            warnings.append("missing_macro_reference:ipc_nacional_variation_yoy")
        if usdars_oficial is None:
            warnings.append("missing_macro_reference:usdars_oficial")

        return {
            "summary": {
                "argentina_weight_pct": round(argentina_weight_pct, 2),
                "ars_liquidity_weight_pct": round(ars_liquidity_weight_pct, 2),
                "cer_weight_pct": round(cer_weight_pct, 2),
                "argentina_bond_weight_pct": round(argentina_bond_weight_pct, 2),
                "sovereign_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                "badlar_pct": round(badlar_pct, 2) if badlar_pct is not None else None,
                "ipc_yoy_pct": round(ipc_yoy_pct, 2) if ipc_yoy_pct is not None else None,
                "ipc_ytd_pct": round(ipc_ytd_pct, 2) if ipc_ytd_pct is not None else None,
                "badlar_real_carry_pct": badlar_real_carry_pct,
                "usdars_oficial": round(usdars_oficial, 2) if usdars_oficial is not None else None,
            },
            "metadata": AnalyticsMetadata(
                methodology=(
                    "signals are derived from current normalized positions plus persisted local references "
                    "for BADLAR, IPC and USDARS oficial"
                ),
                data_basis="current_positions_market_value + MacroSeriesSnapshot",
                limitations=(
                    "The module does not use breakeven inflation, sovereign spreads, MEP or risk-country series yet. "
                    "It is a heuristic local reading focused on carry, CER coverage and sovereign concentration."
                ),
                confidence=self._derive_confidence(warnings),
                warnings=warnings,
            ).to_dict(),
        }

    def build_recommendation_signals(self) -> list[dict]:
        result = self.calculate()
        summary = result.get("summary", {})
        if not summary:
            return []

        signals: list[RecommendationSignal] = []

        argentina_weight_pct = float(summary.get("argentina_weight_pct") or 0.0)
        ars_liquidity_weight_pct = float(summary.get("ars_liquidity_weight_pct") or 0.0)
        cer_weight_pct = float(summary.get("cer_weight_pct") or 0.0)
        argentina_bond_weight_pct = float(summary.get("argentina_bond_weight_pct") or 0.0)
        sovereign_bond_weight_pct = float(summary.get("sovereign_bond_weight_pct") or 0.0)
        badlar_real_carry_pct = summary.get("badlar_real_carry_pct")
        ipc_yoy_pct = summary.get("ipc_yoy_pct")

        if (
            badlar_real_carry_pct is not None
            and ars_liquidity_weight_pct >= self.HIGH_ARS_LIQUIDITY_THRESHOLD
            and float(badlar_real_carry_pct) <= -self.NEGATIVE_REAL_CARRY_GAP_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_liquidity_real_carry_negative",
                    severity=(
                        "high"
                        if ars_liquidity_weight_pct >= self.VERY_HIGH_ARS_LIQUIDITY_THRESHOLD
                        and float(badlar_real_carry_pct) <= -self.LARGE_NEGATIVE_REAL_CARRY_GAP_THRESHOLD
                        else "medium"
                    ),
                    title="Liquidez en pesos con carry real débil",
                    description="La liquidez en ARS pesa demasiado mientras BADLAR no compensa el ritmo inflacionario observado.",
                    affected_scope="portfolio",
                    evidence={
                        "ars_liquidity_weight_pct": round(ars_liquidity_weight_pct, 2),
                        "badlar_real_carry_pct": round(float(badlar_real_carry_pct), 2),
                        "ipc_yoy_pct": round(float(ipc_yoy_pct or 0.0), 2),
                    },
                )
            )

        if (
            argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and cer_weight_pct < self.LOW_CER_HEDGE_THRESHOLD
            and ipc_yoy_pct is not None
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_inflation_hedge_gap",
                    severity="medium",
                    title="Cobertura inflacionaria local acotada",
                    description="La exposición argentina es material y la cobertura CER luce baja para el contexto inflacionario actual.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "cer_weight_pct": round(cer_weight_pct, 2),
                        "ipc_yoy_pct": round(float(ipc_yoy_pct), 2),
                    },
                )
            )

        if sovereign_bond_weight_pct >= self.HIGH_SOVEREIGN_RISK_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="local_sovereign_risk_excess",
                    severity="high" if sovereign_bond_weight_pct >= self.VERY_HIGH_SOVEREIGN_RISK_THRESHOLD else "medium",
                    title="Riesgo soberano local concentrado",
                    description="La cartera acumula una porción relevante de bonos soberanos argentinos dentro del bloque local.",
                    affected_scope="portfolio",
                    evidence={
                        "sovereign_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                        "argentina_bond_weight_pct": round(argentina_bond_weight_pct, 2),
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                    },
                )
            )

        return [signal.to_dict() for signal in signals]

    def _load_current_positions(self):
        return self.positions_loader._load_current_positions()  # noqa: SLF001

    def _is_ars_cash_like(self, position) -> bool:
        return self.positions_loader._is_cash_like_position(position) and (position.currency or "").upper() == "ARS"  # noqa: SLF001

    @staticmethod
    def _weight_pct(positions, total_market_value: float, *, predicate) -> float:
        if total_market_value <= 0:
            return 0.0
        market_value = sum(float(position.market_value) for position in positions if predicate(position))
        return (market_value / total_market_value) * 100.0

    @staticmethod
    def _as_float(value):
        return float(value) if value is not None else None

    @staticmethod
    def _derive_confidence(warnings: list[str]) -> str:
        if not warnings:
            return "high"
        if len(warnings) == 1:
            return "medium"
        return "low"
