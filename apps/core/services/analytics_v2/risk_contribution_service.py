from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
from django.db.models import Max
from django.utils import timezone

from apps.core.services.analytics_v2.helpers import (
    build_data_quality_flags,
    rank_top_items,
)
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
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
    FALLBACK_VOLATILITY = {
        "equity": 0.35,
        "growth": 0.35,
        "etf": 0.25,
        "bond": 0.18,
        "fci": 0.05,
        "cash": 0.0,
        "unknown": 0.12,
    }

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
            by_sector=[],
            by_country=[],
            by_asset_type=[],
            top_contributors=rank_top_items(items, lambda item: item.contribution_pct, limit=top_n),
            metadata=AnalyticsMetadata(
                methodology="risk_score = weight * volatility_proxy; contribution_pct = risk_score / total_risk_score",
                data_basis="invested_portfolio_market_value",
                limitations=(
                    "MVP proxy model without covariance matrix. "
                    "Sector/country/type aggregations are not populated yet in module 2.2."
                ),
                confidence=quality.confidence,
                warnings=quality.warnings,
            ),
        )
        return result.to_dict()

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
        historical = self._get_asset_historical_volatility(position.simbolo, lookback_days=lookback_days)
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

    def _get_asset_historical_volatility(self, symbol: str, *, lookback_days: int) -> float | None:
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
        series = (
            df.sort_values("fecha_extraccion")
            .dropna(subset=["valorizado"])
            .drop_duplicates(subset=["fecha_extraccion"], keep="last")
            .set_index("fecha_extraccion")["valorizado"]
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
