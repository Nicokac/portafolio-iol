from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
from django.db.models import Max
from django.utils import timezone

from apps.core.services.analytics_v2.helpers import (
    aggregate_numeric_items,
    build_data_quality_flags,
    build_group_items,
    normalize_country_label,
    rank_top_items,
)
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    RecommendationSignal,
    RiskContributionItem,
    RiskContributionResult,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@dataclass(frozen=True)
class _VolatilityResolution:
    value: float
    used_fallback: bool
    warning: str | None = None


class RiskContributionService:
    """Risk contribution MVP por activo usando peso y volatilidad proxy."""

    MIN_ASSET_OBSERVATIONS = 5
    TRADING_DAYS_PER_YEAR = 252
    CASH_MANAGEMENT_SYMBOLS = {"ADBAICA", "IOLPORA", "PRPEDOB"}
    TOP_CONTRIBUTOR_THRESHOLD = 25.0
    TOP3_CONTRIBUTOR_THRESHOLD = 60.0
    TECH_CONTRIBUTION_THRESHOLD = 35.0
    ARGENTINA_CONTRIBUTION_THRESHOLD = 45.0
    WEIGHT_RISK_DIVERGENCE_THRESHOLD = 15.0
    SECTOR_RISK_OVERCONCENTRATION_THRESHOLD = 5.0
    COUNTRY_RISK_OVERCONCENTRATION_THRESHOLD = 7.0
    COUNTRY_RISK_UNDERCONCENTRATION_THRESHOLD = -7.0
    FALLBACK_VOLATILITY = {
        "equity": 0.35,
        "growth": 0.35,
        "etf": 0.25,
        "bond": 0.18,
        "fci": 0.05,
        "cash": 0.0,
        "unknown": 0.12,
    }

    def __init__(self, historical_price_service: IOLHistoricalPriceService | None = None):
        self.historical_price_service = historical_price_service or IOLHistoricalPriceService()

    def calculate(self, lookback_days: int = 90, top_n: int = 5) -> dict:
        positions = self._load_current_invested_positions()
        if not positions:
            return RiskContributionResult(
                items=[],
                by_sector=[],
                by_country=[],
                by_asset_type=[],
                top_contributors=[],
                metadata=AnalyticsMetadata(
                    methodology="weight * volatility_proxy over invested portfolio positions",
                    data_basis="invested_portfolio_market_value",
                    limitations="No eligible invested positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ),
            ).to_dict()

        total_invested = sum(float(position.valorizado) for position in positions)
        params = self._load_parameters(positions)

        items: list[RiskContributionItem] = []
        warnings: list[str] = []
        has_missing_metadata = False
        used_fallback = False
        has_insufficient_history = False

        provisional_items: list[tuple[RiskContributionItem, float]] = []
        for position in positions:
            market_value = float(position.valorizado)
            weight = (market_value / total_invested) if total_invested > 0 else 0.0
            param = params.get(position.simbolo)
            if param is None:
                has_missing_metadata = True
                warnings.append(f"missing_metadata:{position.simbolo}")

            volatility = self._resolve_volatility_proxy(position, param, lookback_days=lookback_days)
            used_fallback = used_fallback or volatility.used_fallback
            if volatility.used_fallback and volatility.warning:
                warnings.append(volatility.warning)
            if volatility.warning and "insufficient_history" in volatility.warning:
                has_insufficient_history = True

            item = RiskContributionItem(
                symbol=position.simbolo,
                weight_pct=round(weight * 100, 2),
                volatility_proxy=round(volatility.value * 100, 2),
                risk_score=0.0,
                contribution_pct=0.0,
                sector=param.sector if param else "unknown",
                country=param.pais_exposicion if param else "unknown",
                asset_type=self._resolve_asset_type(position, param),
                used_volatility_fallback=volatility.used_fallback,
            )
            provisional_items.append((item, weight * volatility.value))

        total_risk_score = sum(score for _, score in provisional_items)
        if total_risk_score <= 0:
            warnings.append("non_positive_risk_score_total")
            total_risk_score = 0.0

        for item, risk_score in provisional_items:
            contribution = ((risk_score / total_risk_score) * 100.0) if total_risk_score > 0 else 0.0
            items.append(
                RiskContributionItem(
                    symbol=item.symbol,
                    weight_pct=item.weight_pct,
                    volatility_proxy=item.volatility_proxy,
                    risk_score=round(risk_score, 6),
                    contribution_pct=round(contribution, 2),
                    sector=item.sector,
                    country=item.country,
                    asset_type=item.asset_type,
                    used_volatility_fallback=item.used_volatility_fallback,
                )
            )

        quality = build_data_quality_flags(
            has_missing_metadata=has_missing_metadata,
            has_insufficient_history=has_insufficient_history,
            used_fallback=used_fallback,
            warnings=warnings,
        )

        result = RiskContributionResult(
            items=items,
            by_sector=self._aggregate_items(items, "sector"),
            by_country=self._aggregate_items(items, "country", normalizer=normalize_country_label),
            by_asset_type=self._aggregate_items(items, "asset_type"),
            top_contributors=rank_top_items(items, lambda item: item.contribution_pct, limit=top_n),
            metadata=AnalyticsMetadata(
                methodology="risk_score = weight * volatility_proxy; contribution_pct = risk_score / total_risk_score",
                data_basis="invested_portfolio_market_value",
                limitations=(
                    "MVP proxy model without covariance matrix. "
                    "Aggregations are built from item-level contribution_pct and weight_pct."
                ),
                confidence=quality.confidence,
                warnings=quality.warnings,
            ),
        )
        return result.to_dict()

    def build_recommendation_signals(self, lookback_days: int = 90, top_n: int = 5) -> list[dict]:
        result = self.calculate(lookback_days=lookback_days, top_n=top_n)
        return self._build_recommendation_signals_from_result(result)

    def _build_recommendation_signals_from_result(self, result: dict) -> list[dict]:
        items = result.get("items", [])
        if not items:
            return []

        signals: list[RecommendationSignal] = []

        top_contributors = result.get("top_contributors", [])
        if top_contributors:
            top_1 = float(top_contributors[0]["contribution_pct"])
            top_3 = sum(float(item["contribution_pct"]) for item in top_contributors[:3])
            if top_1 >= self.TOP_CONTRIBUTOR_THRESHOLD or top_3 >= self.TOP3_CONTRIBUTOR_THRESHOLD:
                symbols = [item["symbol"] for item in top_contributors[:3]]
                signals.append(
                    RecommendationSignal(
                        signal_key="risk_concentration_top_assets",
                        severity="high" if top_1 >= self.TOP_CONTRIBUTOR_THRESHOLD else "medium",
                        title="Riesgo concentrado en pocos activos",
                        description="La contribucion al riesgo esta concentrada en uno o pocos activos dominantes.",
                        affected_scope="portfolio",
                        evidence={
                            "top_1_contribution_pct": round(top_1, 2),
                            "top_3_contribution_pct": round(top_3, 2),
                            "symbols": symbols,
                        },
                    )
                )

        tech_contribution = sum(
            float(group["contribution_pct"])
            for group in result.get("by_sector", [])
            if self._is_technology_sector(group["key"])
        )
        if tech_contribution >= self.TECH_CONTRIBUTION_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="risk_concentration_tech",
                    severity="medium",
                    title="Riesgo concentrado en tecnologia",
                    description="La exposicion al riesgo tecnologico supera el umbral del MVP.",
                    affected_scope="sector",
                    evidence={
                        "sector": "technology",
                        "contribution_pct": round(tech_contribution, 2),
                    },
                )
            )

        argentina_group = next(
            (group for group in result.get("by_country", []) if normalize_country_label(group["key"]) == "Argentina"),
            None,
        )
        if argentina_group and float(argentina_group["contribution_pct"]) >= self.ARGENTINA_CONTRIBUTION_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="risk_concentration_argentina",
                    severity="high",
                    title="Riesgo concentrado en Argentina",
                    description="La contribucion al riesgo argentino supera el umbral del MVP.",
                    affected_scope="country",
                    evidence={
                        "country": "Argentina",
                        "contribution_pct": round(float(argentina_group["contribution_pct"]), 2),
                        "weight_pct": round(float(argentina_group.get("weight_pct") or 0.0), 2),
                    },
                )
            )

        max_divergence_item = None
        max_divergence = 0.0
        for item in items:
            divergence = float(item["contribution_pct"]) - float(item["weight_pct"])
            if divergence > max_divergence:
                max_divergence = divergence
                max_divergence_item = item

        if max_divergence_item and max_divergence >= self.WEIGHT_RISK_DIVERGENCE_THRESHOLD:
            signals.append(
                RecommendationSignal(
                    signal_key="risk_vs_weight_divergence",
                    severity="medium",
                    title="Divergencia entre peso patrimonial y riesgo",
                    description="Un activo explica mucho mas riesgo que su peso patrimonial relativo.",
                    affected_scope="asset",
                    evidence={
                        "symbol": max_divergence_item["symbol"],
                        "contribution_pct": round(float(max_divergence_item["contribution_pct"]), 2),
                        "weight_pct": round(float(max_divergence_item["weight_pct"]), 2),
                        "divergence_pct": round(max_divergence, 2),
                    },
                )
            )

        sector_overconcentration = self._find_max_group_delta(
            result.get("by_sector", []),
            minimum_delta=self.SECTOR_RISK_OVERCONCENTRATION_THRESHOLD,
        )
        if sector_overconcentration:
            signals.append(
                RecommendationSignal(
                    signal_key="sector_risk_overconcentration",
                    severity="medium",
                    title="Sector con sobre-contribucion de riesgo",
                    description=(
                        f"El sector {sector_overconcentration['key']} explica "
                        f"{sector_overconcentration['contribution_pct']:.2f}% del riesgo con solo "
                        f"{sector_overconcentration['weight_pct']:.2f}% del peso patrimonial."
                    ),
                    affected_scope="sector",
                    evidence={
                        "sector": sector_overconcentration["key"],
                        "weight_pct": round(sector_overconcentration["weight_pct"], 2),
                        "contribution_pct": round(sector_overconcentration["contribution_pct"], 2),
                        "risk_vs_weight_delta": round(sector_overconcentration["risk_vs_weight_delta"], 2),
                    },
                )
            )

        country_overconcentration = self._find_max_group_delta(
            result.get("by_country", []),
            minimum_delta=self.COUNTRY_RISK_OVERCONCENTRATION_THRESHOLD,
            normalizer=normalize_country_label,
        )
        if country_overconcentration:
            signals.append(
                RecommendationSignal(
                    signal_key="country_risk_overconcentration",
                    severity="high",
                    title="Pais con sobre-contribucion de riesgo",
                    description=(
                        f"El bloque {country_overconcentration['key']} concentra mas riesgo "
                        "del que su peso patrimonial sugiere."
                    ),
                    affected_scope="country",
                    evidence={
                        "country": country_overconcentration["key"],
                        "weight_pct": round(country_overconcentration["weight_pct"], 2),
                        "contribution_pct": round(country_overconcentration["contribution_pct"], 2),
                        "risk_vs_weight_delta": round(country_overconcentration["risk_vs_weight_delta"], 2),
                    },
                )
            )

        country_underconcentration = self._find_min_group_delta(
            result.get("by_country", []),
            maximum_delta=self.COUNTRY_RISK_UNDERCONCENTRATION_THRESHOLD,
            normalizer=normalize_country_label,
        )
        if country_underconcentration:
            signals.append(
                RecommendationSignal(
                    signal_key="country_risk_underconcentration",
                    severity="low",
                    title="Pais con infra-contribucion de riesgo",
                    description=(
                        f"El bloque {country_underconcentration['key']} pesa significativamente "
                        "mas en patrimonio que en contribucion al riesgo."
                    ),
                    affected_scope="country",
                    evidence={
                        "country": country_underconcentration["key"],
                        "weight_pct": round(country_underconcentration["weight_pct"], 2),
                        "contribution_pct": round(country_underconcentration["contribution_pct"], 2),
                        "risk_vs_weight_delta": round(country_underconcentration["risk_vs_weight_delta"], 2),
                    },
                )
            )

        return [signal.to_dict() for signal in signals]

    @staticmethod
    def _find_max_group_delta(groups: list[dict], *, minimum_delta: float, normalizer=None) -> dict | None:
        winner = None
        for group in groups:
            key = group.get("key")
            if normalizer:
                key = normalizer(key)
            weight_pct = float(group.get("weight_pct") or 0.0)
            contribution_pct = float(group.get("contribution_pct") or 0.0)
            delta = contribution_pct - weight_pct
            if delta <= minimum_delta:
                continue
            if winner is None or delta > winner["risk_vs_weight_delta"]:
                winner = {
                    "key": key,
                    "weight_pct": weight_pct,
                    "contribution_pct": contribution_pct,
                    "risk_vs_weight_delta": delta,
                }
        return winner

    @staticmethod
    def _find_min_group_delta(groups: list[dict], *, maximum_delta: float, normalizer=None) -> dict | None:
        winner = None
        for group in groups:
            key = group.get("key")
            if normalizer:
                key = normalizer(key)
            weight_pct = float(group.get("weight_pct") or 0.0)
            contribution_pct = float(group.get("contribution_pct") or 0.0)
            delta = contribution_pct - weight_pct
            if delta >= maximum_delta:
                continue
            if winner is None or delta < winner["risk_vs_weight_delta"]:
                winner = {
                    "key": key,
                    "weight_pct": weight_pct,
                    "contribution_pct": contribution_pct,
                    "risk_vs_weight_delta": delta,
                }
        return winner

    def _load_current_invested_positions(self) -> list[ActivoPortafolioSnapshot]:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]
        if not latest_date:
            return []

        positions = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date).order_by("-valorizado", "simbolo")
        )
        return [
            position
            for position in positions
            if self._is_invested_position(position)
        ]

    @staticmethod
    def _load_parameters(positions: list[ActivoPortafolioSnapshot]) -> dict[str, ParametroActivo]:
        symbols = [position.simbolo for position in positions]
        return {row.simbolo: row for row in ParametroActivo.objects.filter(simbolo__in=symbols)}

    def _is_invested_position(self, position: ActivoPortafolioSnapshot) -> bool:
        if position.tipo == "CAUCIONESPESOS":
            return False
        if position.simbolo.upper() in self.CASH_MANAGEMENT_SYMBOLS:
            return False
        return True

    def _resolve_volatility_proxy(
        self,
        position: ActivoPortafolioSnapshot,
        param: ParametroActivo | None,
        *,
        lookback_days: int,
    ) -> _VolatilityResolution:
        historical = self._get_asset_historical_volatility(
            position.simbolo,
            mercado=getattr(position, "mercado", None),
            lookback_days=lookback_days,
        )
        if historical is not None:
            return _VolatilityResolution(value=historical, used_fallback=False)

        asset_type = self._resolve_asset_type(position, param)
        fallback_key = asset_type.lower()
        fallback_value = self.FALLBACK_VOLATILITY.get(fallback_key, self.FALLBACK_VOLATILITY["unknown"])
        return _VolatilityResolution(
            value=fallback_value,
            used_fallback=True,
            warning=f"used_fallback:{position.simbolo}:insufficient_history",
        )

    def _get_asset_historical_volatility(self, symbol: str, *, mercado: str | None, lookback_days: int) -> float | None:
        iol_historical = self._get_iol_historical_volatility(symbol, mercado=mercado, lookback_days=lookback_days)
        if iol_historical is not None:
            return iol_historical

        end_date = timezone.now()
        start_date = end_date - timedelta(days=lookback_days)
        queryset = ActivoPortafolioSnapshot.objects.filter(
            simbolo=symbol,
            fecha_extraccion__range=(start_date, end_date),
        ).values("fecha_extraccion", "valorizado")
        df = pd.DataFrame(list(queryset))
        if df.empty:
            return None

        df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"])
        df["valorizado"] = pd.to_numeric(df["valorizado"], errors="coerce")
        df["fecha"] = df["fecha_extraccion"].dt.date
        series = (
            df.sort_values("fecha_extraccion")
            .dropna(subset=["valorizado"])
            .drop_duplicates(subset=["fecha"], keep="last")
            .set_index("fecha")["valorizado"]
        )
        if len(series.index) < self.MIN_ASSET_OBSERVATIONS:
            return None

        returns = series.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
        if len(returns.index) < max(2, self.MIN_ASSET_OBSERVATIONS - 1):
            return None

        daily_vol = float(returns.std())
        if daily_vol <= 0:
            return None
        return daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)

    def _get_iol_historical_volatility(self, symbol: str, *, mercado: str | None, lookback_days: int) -> float | None:
        if not mercado:
            return None

        end_date = timezone.now()
        start_date = end_date - timedelta(days=lookback_days)
        dates = pd.date_range(start=start_date.date(), end=end_date.date(), freq="D")
        series = self.historical_price_service.build_close_series(symbol, mercado, dates)
        if series.empty or len(series.index) < self.MIN_ASSET_OBSERVATIONS:
            return None

        returns = pd.to_numeric(series, errors="coerce").pct_change().replace(
            [float("inf"), float("-inf")], pd.NA
        ).dropna()
        if len(returns.index) < max(2, self.MIN_ASSET_OBSERVATIONS - 1):
            return None

        daily_vol = float(returns.std())
        if daily_vol <= 0:
            return None
        return daily_vol * (self.TRADING_DAYS_PER_YEAR ** 0.5)

    @staticmethod
    def _resolve_asset_type(position: ActivoPortafolioSnapshot, param: ParametroActivo | None) -> str:
        patrimonial = (param.tipo_patrimonial if param else "").strip().lower()
        raw_type = (position.tipo or "").strip().lower()

        if patrimonial == "bond" or raw_type == "titulospublicos":
            return "bond"
        if patrimonial == "fci" or raw_type == "fondocomundeinversion":
            return "fci"
        if raw_type == "cedears":
            return "equity"
        if raw_type == "acciones":
            if "etf" in (position.simbolo or "").lower():
                return "etf"
            return "equity"
        if patrimonial in {"equity", "growth", "defensive", "value", "dividend"}:
            return "equity"
        if patrimonial == "cash":
            return "cash"
        return "unknown"

    @staticmethod
    def _aggregate_items(
        items: list[RiskContributionItem],
        field_name: str,
        *,
        normalizer=None,
    ):
        contribution_grouped = aggregate_numeric_items(
            items,
            key_getter=lambda item: getattr(item, field_name, None),
            value_getter=lambda item: item.contribution_pct,
            normalizer=normalizer,
        )
        weight_grouped = aggregate_numeric_items(
            items,
            key_getter=lambda item: getattr(item, field_name, None),
            value_getter=lambda item: item.weight_pct,
            normalizer=normalizer,
        )
        return build_group_items(
            contribution_grouped,
            basis_total=None,
        ) if not weight_grouped else [
            group.__class__(
                key=group.key,
                contribution_pct=group.contribution_pct,
                weight_pct=round(weight_grouped.get(group.key, 0.0), 2),
            )
            for group in build_group_items(contribution_grouped, basis_total=None)
        ]

    @staticmethod
    def _is_technology_sector(label: str | None) -> bool:
        if not label:
            return False
        lowered = str(label).strip().lower()
        return "tecnolog" in lowered or "tech" in lowered
