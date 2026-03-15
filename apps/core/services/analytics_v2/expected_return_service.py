from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from apps.core.config.parametros_benchmark import ParametrosBenchmark
from apps.core.services.analytics_v2.helpers import safe_percentage
from apps.core.services.analytics_v2.scenario_analysis_service import ScenarioAnalysisService
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    ExpectedReturnBucketItem,
    ExpectedReturnResult,
    NormalizedPosition,
    RecommendationSignal,
)
from apps.core.services.benchmark_series_service import BenchmarkSeriesService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService


@dataclass(frozen=True)
class _BucketConfig:
    label: str
    benchmark_key: str | None
    static_fallback_pct: float
    uses_badlar_macro: bool = False


class ExpectedReturnService:
    """Modelo simple de retorno esperado estructural por buckets."""

    DAILY_LOOKBACK_PERIODS = 252
    WEEKLY_LOOKBACK_PERIODS = 52
    MIN_DAILY_OBSERVATIONS = 30
    MIN_WEEKLY_OBSERVATIONS = 8
    LOW_REAL_EXPECTED_RETURN_THRESHOLD = 0.0
    LOW_NOMINAL_EXPECTED_RETURN_THRESHOLD = 12.0
    HIGH_LIQUIDITY_WEIGHT_THRESHOLD = 30.0
    LIQUIDITY_GAP_THRESHOLD = 5.0

    BUCKETS = {
        "equity_beta": _BucketConfig(
            label="Equity beta / CEDEAR",
            benchmark_key="cedear_usa",
            static_fallback_pct=ParametrosBenchmark.ANNUAL_RETURNS["sp500"] * 100.0,
        ),
        "fixed_income_ar": _BucketConfig(
            label="Renta fija AR",
            benchmark_key="bonos_ar",
            static_fallback_pct=ParametrosBenchmark.ANNUAL_RETURNS["cer_embi_proxy"] * 100.0,
        ),
        "liquidity_ars": _BucketConfig(
            label="Liquidez y cash management",
            benchmark_key=None,
            static_fallback_pct=ParametrosBenchmark.ANNUAL_RETURNS["caucion_rate"] * 100.0,
            uses_badlar_macro=True,
        ),
    }

    def __init__(
        self,
        positions_loader: ScenarioAnalysisService | None = None,
        benchmark_service: BenchmarkSeriesService | None = None,
        macro_service: LocalMacroSeriesService | None = None,
    ):
        self.positions_loader = positions_loader or ScenarioAnalysisService()
        self.benchmark_service = benchmark_service or BenchmarkSeriesService()
        self.macro_service = macro_service or LocalMacroSeriesService()

    def calculate(self) -> dict:
        positions = self._load_current_positions()
        if not positions:
            return ExpectedReturnResult(
                expected_return_pct=None,
                real_expected_return_pct=None,
                basis_reference="weighted_bucket_baseline_current_positions",
                by_bucket=[],
                metadata=AnalyticsMetadata(
                    methodology="weighted bucket baseline using institutional benchmark and macro references",
                    data_basis="current_positions_market_value",
                    limitations="No current positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ),
            ).to_dict()

        grouped_market_value = {bucket_key: 0.0 for bucket_key in self.BUCKETS}
        total_market_value = sum(float(position.market_value) for position in positions)
        for position in positions:
            grouped_market_value[self._resolve_bucket_key(position)] += float(position.market_value)

        context = self.macro_service.get_context_summary()
        inflation_reference = context.get("ipc_nacional_variation_yoy")

        warnings: list[str] = []
        used_fallback = False
        bucket_items: list[ExpectedReturnBucketItem] = []
        weighted_nominal_return = 0.0
        has_nominal_reference = False

        for bucket_key, config in self.BUCKETS.items():
            market_value = grouped_market_value[bucket_key]
            if market_value <= 0:
                continue

            expected_return_pct, basis_reference, bucket_used_fallback, bucket_warnings = self._resolve_bucket_reference(
                bucket_key,
                config,
                context,
            )
            weight_pct = round(safe_percentage(market_value, total_market_value), 2)
            bucket_items.append(
                ExpectedReturnBucketItem(
                    bucket_key=bucket_key,
                    label=config.label,
                    weight_pct=weight_pct,
                    expected_return_pct=round(expected_return_pct, 2) if expected_return_pct is not None else None,
                    basis_reference=basis_reference,
                )
            )
            warnings.extend(bucket_warnings)
            used_fallback = used_fallback or bucket_used_fallback
            if expected_return_pct is not None:
                weighted_nominal_return += (weight_pct / 100.0) * expected_return_pct
                has_nominal_reference = True

        expected_return_pct = round(weighted_nominal_return, 2) if has_nominal_reference else None
        real_expected_return_pct = None
        if expected_return_pct is not None and inflation_reference is not None:
            real_expected_return_pct = round(
                (((1 + (expected_return_pct / 100.0)) / (1 + (float(inflation_reference) / 100.0))) - 1) * 100.0,
                2,
            )
        elif expected_return_pct is not None:
            warnings.append("missing_inflation_reference")

        return ExpectedReturnResult(
            expected_return_pct=expected_return_pct,
            real_expected_return_pct=real_expected_return_pct,
            basis_reference="weighted_bucket_baseline_current_positions",
            by_bucket=bucket_items,
            metadata=AnalyticsMetadata(
                methodology=(
                    "current positions are grouped into equity, fixed income and liquidity buckets; "
                    "each bucket uses a simple structural reference based on SPY, EMB or BADLAR, "
                    "with explicit static fallbacks when live references are unavailable"
                ),
                data_basis="current_positions_market_value",
                limitations=(
                    "This is a structural baseline, not a precise forecast. "
                    "Local equities share the global equity proxy in the MVP and real return depends on current inflation reference."
                ),
                confidence=self._derive_confidence(used_fallback=used_fallback, has_inflation=inflation_reference is not None),
                warnings=list(dict.fromkeys(warnings)),
            ),
        ).to_dict()

    def build_recommendation_signals(self) -> list[dict]:
        result = self.calculate()
        if not result.get("by_bucket"):
            return []

        signals: list[RecommendationSignal] = []
        buckets = {item["bucket_key"]: item for item in result.get("by_bucket", [])}
        expected_return_pct = result.get("expected_return_pct")
        real_expected_return_pct = result.get("real_expected_return_pct")

        liquidity_bucket = buckets.get("liquidity_ars", {})
        liquidity_weight = float(liquidity_bucket.get("weight_pct", 0.0) or 0.0)
        liquidity_expected = liquidity_bucket.get("expected_return_pct")
        equity_bucket = buckets.get("equity_beta", {})
        equity_expected = equity_bucket.get("expected_return_pct")

        if real_expected_return_pct is not None and float(real_expected_return_pct) <= self.LOW_REAL_EXPECTED_RETURN_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="expected_return_real_weak",
                    severity="high" if float(real_expected_return_pct) < -2.0 else "medium",
                    title="Retorno real esperado débil",
                    description="La referencia real esperada del portafolio queda en zona baja o negativa frente a inflación.",
                    affected_scope="portfolio",
                    evidence={
                        "real_expected_return_pct": round(float(real_expected_return_pct), 2),
                        "expected_return_pct": round(float(expected_return_pct or 0.0), 2),
                    },
                )
            )
        elif expected_return_pct is not None and float(expected_return_pct) <= self.LOW_NOMINAL_EXPECTED_RETURN_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="expected_return_nominal_weak",
                    severity="medium",
                    title="Retorno esperado nominal moderado",
                    description="La referencia nominal del portafolio luce acotada para la composición actual.",
                    affected_scope="portfolio",
                    evidence={
                        "expected_return_pct": round(float(expected_return_pct), 2),
                        "threshold_pct": self.LOW_NOMINAL_EXPECTED_RETURN_THRESHOLD,
                    },
                )
            )

        if (
            liquidity_weight >= self.HIGH_LIQUIDITY_WEIGHT_THRESHOLD
            and liquidity_expected is not None
            and equity_expected is not None
            and (float(equity_expected) - float(liquidity_expected)) >= self.LIQUIDITY_GAP_THRESHOLD
        ):
            signals.append(
                RecommendationSignal(
                    signal_key="expected_return_liquidity_drag",
                    severity="medium",
                    title="Liquidez excedente con retorno esperado menor",
                    description="La liquidez y el cash management pesan demasiado frente a buckets con mejor referencia estructural de retorno.",
                    affected_scope="portfolio",
                    evidence={
                        "liquidity_weight_pct": round(liquidity_weight, 2),
                        "liquidity_expected_return_pct": round(float(liquidity_expected), 2),
                        "equity_expected_return_pct": round(float(equity_expected), 2),
                    },
                )
            )

        return [signal.to_dict() for signal in signals]

    def _load_current_positions(self) -> list[NormalizedPosition]:
        return self.positions_loader._load_current_positions()

    def _resolve_bucket_key(self, position: NormalizedPosition) -> str:
        asset_type = (position.asset_type or "").strip().lower()
        sector = (position.sector or "").strip().lower()
        strategic_bucket = (position.strategic_bucket or "").strip().lower()
        patrimonial_type = (position.patrimonial_type or "").strip().lower()

        if (
            asset_type in {"cash", "fci"}
            or sector in {"liquidez", "cash mgmt"}
            or strategic_bucket == "liquidez"
            or patrimonial_type in {"cash", "fci"}
        ):
            return "liquidity_ars"
        if asset_type == "bond" or patrimonial_type == "bond":
            return "fixed_income_ar"
        return "equity_beta"

    def _resolve_bucket_reference(
        self,
        bucket_key: str,
        config: _BucketConfig,
        context: dict,
    ) -> tuple[float | None, str, bool, list[str]]:
        if config.uses_badlar_macro:
            badlar = context.get("badlar_privada")
            if badlar is not None:
                return float(badlar), "macro:badlar_privada_latest_annual_rate", False, []
            return (
                config.static_fallback_pct,
                "static:caucion_rate_fallback",
                True,
                [f"expected_return_fallback:{bucket_key}:missing_badlar"],
            )

        benchmark_pct, basis_reference = self._build_benchmark_reference(config.benchmark_key)
        if benchmark_pct is not None:
            return benchmark_pct, basis_reference, False, []

        mapping_key = ParametrosBenchmark.BENCHMARK_MAPPINGS.get(config.benchmark_key or "", "static")
        return (
            config.static_fallback_pct,
            f"static:{mapping_key}",
            True,
            [f"expected_return_fallback:{bucket_key}:insufficient_benchmark_history"],
        )

    def _build_benchmark_reference(self, benchmark_key: str | None) -> tuple[float | None, str]:
        if not benchmark_key:
            return None, "unavailable"

        daily_dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=self.DAILY_LOOKBACK_PERIODS)
        daily_returns = self.benchmark_service.build_daily_returns(benchmark_key, daily_dates).dropna()
        if len(daily_returns) >= self.MIN_DAILY_OBSERVATIONS:
            annualized = self._annualize_returns(daily_returns, periods_per_year=252)
            return annualized, f"benchmark:{benchmark_key}:daily_trailing_{len(daily_returns)}"

        weekly_dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=self.WEEKLY_LOOKBACK_PERIODS, freq="W-FRI")
        weekly_returns = self.benchmark_service.build_weekly_returns(benchmark_key, weekly_dates).dropna()
        if len(weekly_returns) >= self.MIN_WEEKLY_OBSERVATIONS:
            annualized = self._annualize_returns(weekly_returns, periods_per_year=52)
            return annualized, f"benchmark:{benchmark_key}:weekly_trailing_{len(weekly_returns)}"

        return None, f"benchmark:{benchmark_key}:unavailable"

    @staticmethod
    def _annualize_returns(returns: pd.Series, periods_per_year: int) -> float:
        cumulative_return = (1 + returns.astype(float)).prod()
        if cumulative_return <= 0 or len(returns.index) == 0:
            return 0.0
        annualized = (cumulative_return ** (periods_per_year / len(returns.index))) - 1.0
        return annualized * 100.0

    @staticmethod
    def _derive_confidence(*, used_fallback: bool, has_inflation: bool) -> str:
        if used_fallback and not has_inflation:
            return "low"
        if used_fallback or not has_inflation:
            return "medium"
        return "high"
