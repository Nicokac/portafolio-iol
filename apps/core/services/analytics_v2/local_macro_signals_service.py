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
    HIGH_FX_GAP_THRESHOLD = 15.0
    VERY_HIGH_FX_GAP_THRESHOLD = 30.0
    FX_GAP_DETERIORATION_POINTS_THRESHOLD = 5.0
    VERY_HIGH_FX_GAP_DETERIORATION_POINTS_THRESHOLD = 10.0
    FX_GAP_DETERIORATION_PCT_THRESHOLD = 25.0
    VERY_HIGH_FX_GAP_DETERIORATION_PCT_THRESHOLD = 50.0
    FX_MEP_CCL_DIVERGENCE_THRESHOLD = 3.0
    UVA_ACCELERATING_30D_THRESHOLD = 3.0
    HIGH_UVA_ANNUALIZED_THRESHOLD = 35.0
    NEGATIVE_REAL_RATE_THRESHOLD = -1.0
    VERY_NEGATIVE_REAL_RATE_THRESHOLD = -5.0
    HIGH_COUNTRY_RISK_THRESHOLD = 900.0
    VERY_HIGH_COUNTRY_RISK_THRESHOLD = 1400.0
    COUNTRY_RISK_DETERIORATION_POINTS_THRESHOLD = 150.0
    VERY_HIGH_COUNTRY_RISK_DETERIORATION_POINTS_THRESHOLD = 300.0
    COUNTRY_RISK_DETERIORATION_PCT_THRESHOLD = 15.0
    VERY_HIGH_COUNTRY_RISK_DETERIORATION_PCT_THRESHOLD = 25.0
    HIGH_SINGLE_SOVEREIGN_SHARE_THRESHOLD = 45.0
    VERY_HIGH_SINGLE_SOVEREIGN_SHARE_THRESHOLD = 60.0
    HIGH_HARD_DOLLAR_SHARE_THRESHOLD = 70.0

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
        cer_local_bond_weight_pct = self._weight_pct(
            positions,
            total_market_value,
            predicate=lambda position: self._is_local_cer_bond(position),
        )
        sovereign_positions = self._build_local_sovereign_breakdown(positions, total_market_value)
        top_local_sovereign = sovereign_positions[0] if sovereign_positions else None
        sovereign_block_hhi = self._calculate_concentration_hhi(sovereign_positions, key="share_pct")
        local_duration_split = self._build_local_duration_split(positions, total_market_value)

        badlar_pct = self._as_float(context.get("badlar_privada"))
        ipc_yoy_pct = self._as_float(context.get("ipc_nacional_variation_yoy"))
        ipc_ytd_pct = self._as_float(context.get("ipc_nacional_variation_ytd"))
        usdars_oficial = self._as_float(context.get("usdars_oficial"))
        usdars_mep = self._as_float(context.get("usdars_mep"))
        usdars_ccl = self._as_float(context.get("usdars_ccl"))
        usdars_financial = self._as_float(context.get("usdars_financial"))
        fx_gap_pct = self._as_float(context.get("fx_gap_pct"))
        fx_gap_mep_pct = self._as_float(context.get("fx_gap_mep_pct"))
        fx_gap_ccl_pct = self._as_float(context.get("fx_gap_ccl_pct"))
        fx_gap_change_30d = self._as_float(context.get("fx_gap_change_30d"))
        fx_gap_change_pct_30d = self._as_float(context.get("fx_gap_change_pct_30d"))
        fx_mep_ccl_spread_pct = self._as_float(context.get("fx_mep_ccl_spread_pct"))
        fx_signal_state = context.get("fx_signal_state")
        riesgo_pais_arg = self._as_float(context.get("riesgo_pais_arg"))
        riesgo_pais_arg_change_30d = self._as_float(context.get("riesgo_pais_arg_change_30d"))
        riesgo_pais_arg_change_pct_30d = self._as_float(context.get("riesgo_pais_arg_change_pct_30d"))
        uva = self._as_float(context.get("uva"))
        uva_change_30d = self._as_float(context.get("uva_change_30d"))
        uva_change_pct_30d = self._as_float(context.get("uva_change_pct_30d"))
        uva_annualized_pct_30d = self._as_float(context.get("uva_annualized_pct_30d"))
        real_rate_badlar_vs_uva_30d = self._as_float(context.get("real_rate_badlar_vs_uva_30d"))
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
                "local_hard_dollar_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                "local_cer_bond_weight_pct": round(cer_local_bond_weight_pct, 2),
                "local_hard_dollar_share_pct": local_duration_split["hard_dollar_share_pct"],
                "local_cer_share_pct": local_duration_split["cer_share_pct"],
                "top_local_sovereign_symbol": top_local_sovereign["symbol"] if top_local_sovereign else None,
                "top_local_sovereign_weight_pct": top_local_sovereign["weight_pct"] if top_local_sovereign else None,
                "top_local_sovereign_share_pct": top_local_sovereign["share_pct"] if top_local_sovereign else None,
                "local_sovereign_symbols_count": len(sovereign_positions),
                "local_sovereign_concentration_hhi": sovereign_block_hhi,
                "local_sovereign_breakdown": sovereign_positions[:3],
                "badlar_pct": round(badlar_pct, 2) if badlar_pct is not None else None,
                "ipc_yoy_pct": round(ipc_yoy_pct, 2) if ipc_yoy_pct is not None else None,
                "ipc_ytd_pct": round(ipc_ytd_pct, 2) if ipc_ytd_pct is not None else None,
                "badlar_real_carry_pct": badlar_real_carry_pct,
                "usdars_oficial": round(usdars_oficial, 2) if usdars_oficial is not None else None,
                "usdars_mep": round(usdars_mep, 2) if usdars_mep is not None else None,
                "usdars_ccl": round(usdars_ccl, 2) if usdars_ccl is not None else None,
                "usdars_financial": round(usdars_financial, 2) if usdars_financial is not None else None,
                "fx_gap_pct": round(fx_gap_pct, 2) if fx_gap_pct is not None else None,
                "fx_gap_mep_pct": round(fx_gap_mep_pct, 2) if fx_gap_mep_pct is not None else None,
                "fx_gap_ccl_pct": round(fx_gap_ccl_pct, 2) if fx_gap_ccl_pct is not None else None,
                "fx_gap_change_30d": round(fx_gap_change_30d, 2) if fx_gap_change_30d is not None else None,
                "fx_gap_change_pct_30d": (
                    round(fx_gap_change_pct_30d, 2) if fx_gap_change_pct_30d is not None else None
                ),
                "fx_mep_ccl_spread_pct": (
                    round(fx_mep_ccl_spread_pct, 2) if fx_mep_ccl_spread_pct is not None else None
                ),
                "fx_signal_state": fx_signal_state,
                "riesgo_pais_arg": round(riesgo_pais_arg, 2) if riesgo_pais_arg is not None else None,
                "riesgo_pais_arg_change_30d": (
                    round(riesgo_pais_arg_change_30d, 2) if riesgo_pais_arg_change_30d is not None else None
                ),
                "riesgo_pais_arg_change_pct_30d": (
                    round(riesgo_pais_arg_change_pct_30d, 2) if riesgo_pais_arg_change_pct_30d is not None else None
                ),
                "uva": round(uva, 2) if uva is not None else None,
                "uva_change_30d": round(uva_change_30d, 2) if uva_change_30d is not None else None,
                "uva_change_pct_30d": round(uva_change_pct_30d, 2) if uva_change_pct_30d is not None else None,
                "uva_annualized_pct_30d": (
                    round(uva_annualized_pct_30d, 2) if uva_annualized_pct_30d is not None else None
                ),
                "real_rate_badlar_vs_uva_30d": (
                    round(real_rate_badlar_vs_uva_30d, 2) if real_rate_badlar_vs_uva_30d is not None else None
                ),
            },
            "metadata": AnalyticsMetadata(
                methodology=(
                    "signals are derived from current normalized positions plus persisted local references "
                    "for BADLAR, IPC, USDARS oficial and optional local external references such as USDARS MEP or riesgo pais"
                ),
                data_basis="current_positions_market_value + MacroSeriesSnapshot",
                limitations=(
                    "The module does not use breakeven inflation or sovereign spreads yet. "
                    "MEP, FX gap and riesgo pais are only used when those series already exist in MacroSeriesSnapshot."
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
        local_hard_dollar_bond_weight_pct = float(summary.get("local_hard_dollar_bond_weight_pct") or 0.0)
        local_cer_bond_weight_pct = float(summary.get("local_cer_bond_weight_pct") or 0.0)
        local_hard_dollar_share_pct = summary.get("local_hard_dollar_share_pct")
        top_local_sovereign_symbol = summary.get("top_local_sovereign_symbol")
        top_local_sovereign_weight_pct = summary.get("top_local_sovereign_weight_pct")
        top_local_sovereign_share_pct = summary.get("top_local_sovereign_share_pct")
        badlar_real_carry_pct = summary.get("badlar_real_carry_pct")
        ipc_yoy_pct = summary.get("ipc_yoy_pct")
        fx_gap_pct = summary.get("fx_gap_pct")
        fx_gap_change_30d = summary.get("fx_gap_change_30d")
        fx_gap_change_pct_30d = summary.get("fx_gap_change_pct_30d")
        fx_mep_ccl_spread_pct = summary.get("fx_mep_ccl_spread_pct")
        fx_signal_state = summary.get("fx_signal_state")
        riesgo_pais_arg = summary.get("riesgo_pais_arg")
        riesgo_pais_arg_change_30d = summary.get("riesgo_pais_arg_change_30d")
        riesgo_pais_arg_change_pct_30d = summary.get("riesgo_pais_arg_change_pct_30d")
        uva_change_pct_30d = summary.get("uva_change_pct_30d")
        uva_annualized_pct_30d = summary.get("uva_annualized_pct_30d")
        real_rate_badlar_vs_uva_30d = summary.get("real_rate_badlar_vs_uva_30d")

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

        if (
            fx_gap_pct is not None
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and float(fx_gap_pct) >= self.HIGH_FX_GAP_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_fx_gap_high",
                    severity="high" if float(fx_gap_pct) >= self.VERY_HIGH_FX_GAP_THRESHOLD else "medium",
                    title="Brecha cambiaria local elevada",
                    description="La exposicion argentina es material y la brecha entre dolar oficial y MEP agrega sensibilidad local.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "fx_gap_pct": round(float(fx_gap_pct), 2),
                        "usdars_oficial": round(float(summary.get("usdars_oficial") or 0.0), 2),
                        "usdars_mep": round(float(summary.get("usdars_mep") or 0.0), 2),
                    },
                )
            )

        if (
            fx_signal_state == "tensioned"
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_fx_regime_tensioned",
                    severity="high" if float(fx_gap_pct or 0.0) >= self.VERY_HIGH_FX_GAP_THRESHOLD else "medium",
                    title="Regimen FX local tensionado",
                    description="El dolar financiero y la brecha cambiaria muestran una tension relevante para carteras con exposicion local.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "fx_gap_pct": round(float(fx_gap_pct or 0.0), 2),
                        "fx_gap_change_30d": round(float(fx_gap_change_30d or 0.0), 2),
                    },
                )
            )

        if (
            fx_signal_state == "divergent"
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and fx_mep_ccl_spread_pct is not None
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_fx_regime_divergent",
                    severity="high" if float(fx_mep_ccl_spread_pct) >= self.FX_MEP_CCL_DIVERGENCE_THRESHOLD * 2 else "medium",
                    title="Regimen FX local divergente",
                    description="MEP y CCL se abrieron entre si, senal de ruido cambiario adicional sobre la referencia financiera local.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "fx_gap_pct": round(float(fx_gap_pct or 0.0), 2),
                        "fx_mep_ccl_spread_pct": round(float(fx_mep_ccl_spread_pct), 2),
                    },
                )
            )

        if (
            fx_gap_change_30d is not None
            and fx_gap_change_pct_30d is not None
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and (
                float(fx_gap_change_30d) >= self.FX_GAP_DETERIORATION_POINTS_THRESHOLD
                or float(fx_gap_change_pct_30d) >= self.FX_GAP_DETERIORATION_PCT_THRESHOLD
            )
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_fx_gap_deteriorating",
                    severity=(
                        "high"
                        if (
                            float(fx_gap_change_30d) >= self.VERY_HIGH_FX_GAP_DETERIORATION_POINTS_THRESHOLD
                            or float(fx_gap_change_pct_30d) >= self.VERY_HIGH_FX_GAP_DETERIORATION_PCT_THRESHOLD
                        )
                        else "medium"
                    ),
                    title="Brecha cambiaria en deterioro reciente",
                    description="La brecha entre dólar oficial y MEP viene ampliándose con fuerza mientras la cartera mantiene exposición local material.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "fx_gap_pct": round(float(fx_gap_pct or 0.0), 2),
                        "fx_gap_change_30d": round(float(fx_gap_change_30d), 2),
                        "fx_gap_change_pct_30d": round(float(fx_gap_change_pct_30d), 2),
                        "usdars_oficial": round(float(summary.get("usdars_oficial") or 0.0), 2),
                        "usdars_mep": round(float(summary.get("usdars_mep") or 0.0), 2),
                    },
                )
            )

        if (
            uva_change_pct_30d is not None
            and uva_annualized_pct_30d is not None
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and (
                float(uva_change_pct_30d) >= self.UVA_ACCELERATING_30D_THRESHOLD
                or float(uva_annualized_pct_30d) >= self.HIGH_UVA_ANNUALIZED_THRESHOLD
            )
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="inflation_accelerating",
                    severity="high" if float(uva_annualized_pct_30d) >= self.HIGH_UVA_ANNUALIZED_THRESHOLD + 15.0 else "medium",
                    title="Inflacion indexada en aceleracion",
                    description="La trayectoria reciente de UVA sugiere una nominalidad mas alta para la referencia local indexada.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "uva_change_pct_30d": round(float(uva_change_pct_30d), 2),
                        "uva_annualized_pct_30d": round(float(uva_annualized_pct_30d), 2),
                    },
                )
            )

        if (
            real_rate_badlar_vs_uva_30d is not None
            and ars_liquidity_weight_pct >= self.HIGH_ARS_LIQUIDITY_THRESHOLD
            and float(real_rate_badlar_vs_uva_30d) <= self.NEGATIVE_REAL_RATE_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="real_rate_negative",
                    severity="high" if float(real_rate_badlar_vs_uva_30d) <= self.VERY_NEGATIVE_REAL_RATE_THRESHOLD else "medium",
                    title="Tasa real local negativa",
                    description="BADLAR queda por debajo del ritmo indexado reciente de UVA mientras la cartera mantiene liquidez relevante en ARS.",
                    affected_scope="portfolio",
                    evidence={
                        "ars_liquidity_weight_pct": round(ars_liquidity_weight_pct, 2),
                        "real_rate_badlar_vs_uva_30d": round(float(real_rate_badlar_vs_uva_30d), 2),
                        "uva_annualized_pct_30d": round(float(uva_annualized_pct_30d or 0.0), 2),
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

        if (
            top_local_sovereign_symbol
            and top_local_sovereign_share_pct is not None
            and sovereign_bond_weight_pct >= self.HIGH_SOVEREIGN_RISK_THRESHOLD
            and float(top_local_sovereign_share_pct) >= self.HIGH_SINGLE_SOVEREIGN_SHARE_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_sovereign_single_name_concentration",
                    severity=(
                        "high"
                        if float(top_local_sovereign_share_pct) >= self.VERY_HIGH_SINGLE_SOVEREIGN_SHARE_THRESHOLD
                        else "medium"
                    ),
                    title="Bloque soberano local concentrado en un solo bono",
                    description=(
                        "La exposicion a soberanos locales depende demasiado de un instrumento puntual dentro del bloque argentino."
                    ),
                    affected_scope="portfolio",
                    evidence={
                        "top_local_sovereign_symbol": top_local_sovereign_symbol,
                        "top_local_sovereign_weight_pct": round(float(top_local_sovereign_weight_pct or 0.0), 2),
                        "top_local_sovereign_share_pct": round(float(top_local_sovereign_share_pct), 2),
                        "sovereign_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                    },
                )
            )

        if (
            local_hard_dollar_share_pct is not None
            and sovereign_bond_weight_pct >= self.HIGH_SOVEREIGN_RISK_THRESHOLD
            and float(local_hard_dollar_share_pct) >= self.HIGH_HARD_DOLLAR_SHARE_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_sovereign_hard_dollar_dependence",
                    severity="medium",
                    title="Bloque soberano local sesgado a hard dollar",
                    description=(
                        "Dentro de la renta fija local predomina la exposicion a soberanos hard dollar frente a CER."
                    ),
                    affected_scope="portfolio",
                    evidence={
                        "local_hard_dollar_bond_weight_pct": round(local_hard_dollar_bond_weight_pct, 2),
                        "local_cer_bond_weight_pct": round(local_cer_bond_weight_pct, 2),
                        "local_hard_dollar_share_pct": round(float(local_hard_dollar_share_pct), 2),
                    },
                )
            )

        if (
            riesgo_pais_arg is not None
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and sovereign_bond_weight_pct >= self.HIGH_SOVEREIGN_RISK_THRESHOLD
            and float(riesgo_pais_arg) >= self.HIGH_COUNTRY_RISK_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_country_risk_high",
                    severity="high" if float(riesgo_pais_arg) >= self.VERY_HIGH_COUNTRY_RISK_THRESHOLD else "medium",
                    title="Riesgo país alto con soberano local relevante",
                    description="La cartera combina exposición argentina material, soberanos locales y un nivel elevado de riesgo país.",
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "sovereign_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                        "riesgo_pais_arg": round(float(riesgo_pais_arg), 2),
                    },
                )
            )

        if (
            riesgo_pais_arg_change_30d is not None
            and riesgo_pais_arg_change_pct_30d is not None
            and argentina_weight_pct >= self.HIGH_ARGENTINA_EXPOSURE_THRESHOLD
            and sovereign_bond_weight_pct >= self.HIGH_SOVEREIGN_RISK_THRESHOLD
            and (
                float(riesgo_pais_arg_change_30d) >= self.COUNTRY_RISK_DETERIORATION_POINTS_THRESHOLD
                or float(riesgo_pais_arg_change_pct_30d) >= self.COUNTRY_RISK_DETERIORATION_PCT_THRESHOLD
            )
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="local_country_risk_deteriorating",
                    severity=(
                        "high"
                        if (
                            float(riesgo_pais_arg_change_30d) >= self.VERY_HIGH_COUNTRY_RISK_DETERIORATION_POINTS_THRESHOLD
                            or float(riesgo_pais_arg_change_pct_30d) >= self.VERY_HIGH_COUNTRY_RISK_DETERIORATION_PCT_THRESHOLD
                        )
                        else "medium"
                    ),
                    title="Riesgo país en deterioro reciente",
                    description=(
                        "El riesgo país argentino viene subiendo con fuerza frente a la referencia reciente mientras la cartera mantiene exposición local material."
                    ),
                    affected_scope="portfolio",
                    evidence={
                        "argentina_weight_pct": round(argentina_weight_pct, 2),
                        "sovereign_bond_weight_pct": round(sovereign_bond_weight_pct, 2),
                        "riesgo_pais_arg": round(float(riesgo_pais_arg or 0.0), 2),
                        "riesgo_pais_arg_change_30d": round(float(riesgo_pais_arg_change_30d), 2),
                        "riesgo_pais_arg_change_pct_30d": round(float(riesgo_pais_arg_change_pct_30d), 2),
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
    def _build_local_sovereign_breakdown(positions, total_market_value: float) -> list[dict]:
        sovereign_positions = [
            position
            for position in positions
            if (position.sector or "").strip().lower() == "soberano"
            and (position.country or "").strip().lower() == "argentina"
            and (position.asset_type or "").strip().lower() == "bond"
        ]
        sovereign_total = sum(float(position.market_value) for position in sovereign_positions)
        if total_market_value <= 0 or sovereign_total <= 0:
            return []

        rows = []
        for position in sovereign_positions:
            market_value = float(position.market_value)
            rows.append(
                {
                    "symbol": position.symbol,
                    "weight_pct": round((market_value / total_market_value) * 100.0, 2),
                    "share_pct": round((market_value / sovereign_total) * 100.0, 2),
                }
            )
        return sorted(rows, key=lambda item: item["weight_pct"], reverse=True)

    @staticmethod
    def _build_local_duration_split(positions, total_market_value: float) -> dict:
        if total_market_value <= 0:
            return {"hard_dollar_share_pct": None, "cer_share_pct": None}

        hard_dollar_value = sum(
            float(position.market_value)
            for position in positions
            if (position.sector or "").strip().lower() == "soberano"
            and (position.country or "").strip().lower() == "argentina"
            and (position.asset_type or "").strip().lower() == "bond"
        )
        cer_value = sum(
            float(position.market_value)
            for position in positions
            if LocalMacroSignalsService._is_local_cer_bond(position)
        )
        total_local_duration = hard_dollar_value + cer_value
        if total_local_duration <= 0:
            return {"hard_dollar_share_pct": None, "cer_share_pct": None}

        return {
            "hard_dollar_share_pct": round((hard_dollar_value / total_local_duration) * 100.0, 2),
            "cer_share_pct": round((cer_value / total_local_duration) * 100.0, 2),
        }

    @staticmethod
    def _calculate_concentration_hhi(items: list[dict], *, key: str) -> float | None:
        if not items:
            return None
        shares = [float(item.get(key) or 0.0) / 100.0 for item in items]
        if not any(shares):
            return None
        return round(sum((share ** 2) for share in shares) * 10000, 2)

    @staticmethod
    def _is_local_cer_bond(position) -> bool:
        return (
            (position.sector or "").strip().lower() == "cer"
            and (position.country or "").strip().lower() == "argentina"
            and (position.asset_type or "").strip().lower() == "bond"
        )

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
