from __future__ import annotations

from django.db.models import Max

from apps.core.services.analytics_v2.helpers import (
    aggregate_numeric_items,
    build_data_quality_flags,
    normalize_country_label,
    rank_top_items,
    safe_percentage,
)
from apps.core.services.analytics_v2.scenario_catalog import ScenarioCatalogService
from apps.core.services.analytics_v2.scenario_sensitivity_service import ScenarioSensitivityService
from apps.core.services.analytics_v2.schemas import (
    AnalyticsMetadata,
    NormalizedPosition,
    ScenarioAnalysisResult,
    ScenarioAssetImpact,
    ScenarioGroupImpact,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class ScenarioAnalysisService:
    """Calcula impacto heuristico de escenarios MVP sobre posiciones actuales."""

    CASH_MANAGEMENT_SYMBOLS = {"ADBAICA", "IOLPORA", "PRPEDOB"}

    def __init__(
        self,
        sensitivity_service: ScenarioSensitivityService | None = None,
        catalog_service: ScenarioCatalogService | None = None,
    ):
        self.sensitivity_service = sensitivity_service or ScenarioSensitivityService()
        self.catalog_service = catalog_service or ScenarioCatalogService()

    def analyze(self, scenario_key: str) -> dict:
        scenario = self.catalog_service.require_scenario(scenario_key)
        positions = self._load_current_positions()
        if not positions:
            return ScenarioAnalysisResult(
                scenario_key=scenario_key,
                total_impact_pct=0.0,
                total_impact_money=0.0,
                by_asset=[],
                by_sector=[],
                by_country=[],
                top_negative_contributors=[],
                metadata=AnalyticsMetadata(
                    methodology="heuristic scenario analysis over current portfolio positions",
                    data_basis="current_positions_market_value",
                    limitations="No current positions were found",
                    confidence="low",
                    warnings=["empty_portfolio"],
                ),
            ).to_dict()

        total_basis = sum(position.market_value for position in positions)
        has_missing_metadata = any(
            position.sector == "unknown" or position.country == "unknown"
            for position in positions
        )

        impacts: list[ScenarioAssetImpact] = []
        warnings: list[str] = []
        for position in positions:
            sensitivity = self.sensitivity_service.resolve_asset_sensitivity(scenario_key, position)
            shock_multiplier = float(sensitivity["shock_multiplier"])
            impact_money = position.market_value * shock_multiplier
            impacts.append(
                ScenarioAssetImpact(
                    symbol=position.symbol,
                    market_value=round(position.market_value, 2),
                    estimated_impact_pct=round(shock_multiplier * 100.0, 2),
                    estimated_impact_money=round(impact_money, 2),
                    transmission_channel=sensitivity["transmission_channel"],
                )
            )
            if position.sector == "unknown" or position.country == "unknown":
                warnings.append(f"missing_metadata:{position.symbol}")

        total_impact_money = sum(item.estimated_impact_money for item in impacts)
        total_impact_pct = safe_percentage(total_impact_money, total_basis)

        quality = build_data_quality_flags(
            has_missing_metadata=has_missing_metadata,
            has_insufficient_history=False,
            used_fallback=False,
            warnings=warnings,
        )

        result = ScenarioAnalysisResult(
            scenario_key=scenario_key,
            total_impact_pct=round(total_impact_pct, 2),
            total_impact_money=round(total_impact_money, 2),
            by_asset=impacts,
            by_sector=self._aggregate_impacts(positions, impacts, "sector"),
            by_country=self._aggregate_impacts(positions, impacts, "country", normalizer=normalize_country_label),
            top_negative_contributors=rank_top_items(
                [impact for impact in impacts if impact.estimated_impact_money < 0],
                value_getter=lambda item: abs(item.estimated_impact_money),
                limit=5,
            ),
            metadata=AnalyticsMetadata(
                methodology="heuristic scenario sensitivity by asset, then aggregated by sector and country",
                data_basis="current_positions_market_value",
                limitations=(
                    "Impact model is heuristic and uses current positions only. "
                    "Account cash outside portfolio positions is excluded from the basis."
                ),
                confidence=quality.confidence,
                warnings=quality.warnings,
            ),
        )
        payload = result.to_dict()
        payload["scenario"] = scenario
        return payload

    def _load_current_positions(self) -> list[NormalizedPosition]:
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]
        if not latest_date:
            return []

        rows = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date).order_by("-valorizado", "simbolo")
        )
        total_market_value = sum(float(row.valorizado) for row in rows)
        params = {
            row.simbolo: row
            for row in ParametroActivo.objects.filter(simbolo__in=[position.simbolo for position in rows])
        }

        positions: list[NormalizedPosition] = []
        for row in rows:
            param = params.get(row.simbolo)
            market_value = float(row.valorizado)
            positions.append(
                NormalizedPosition(
                    symbol=row.simbolo,
                    description=row.descripcion,
                    market_value=market_value,
                    weight_pct=round(safe_percentage(market_value, total_market_value), 2),
                    sector=param.sector if param else "unknown",
                    country=param.pais_exposicion if param else "unknown",
                    asset_type=self._resolve_asset_type(row, param),
                    strategic_bucket=param.bloque_estrategico if param else "unknown",
                    patrimonial_type=param.tipo_patrimonial if param else "unknown",
                    currency=self._normalize_currency(row.moneda),
                    gain_pct=float(row.ganancia_porcentaje),
                    gain_money=float(row.ganancia_dinero),
                )
            )
        return positions

    @staticmethod
    def _normalize_currency(raw_currency: str | None) -> str | None:
        if not raw_currency:
            return None
        lowered = str(raw_currency).strip().lower()
        if lowered in {"peso_argentino", "ars"}:
            return "ARS"
        if lowered in {"dolar_estadounidense", "usd"}:
            return "USD"
        return str(raw_currency).upper()

    def _resolve_asset_type(self, row: ActivoPortafolioSnapshot, param: ParametroActivo | None) -> str:
        patrimonial = (param.tipo_patrimonial if param else "").strip().lower()
        raw_type = (row.tipo or "").strip().lower()
        symbol = (row.simbolo or "").strip().upper()

        if raw_type == "caucionespesos":
            return "cash"
        if symbol in self.CASH_MANAGEMENT_SYMBOLS:
            return "fci"
        if patrimonial == "bond" or raw_type == "titulospublicos":
            return "bond"
        if patrimonial == "fci" or raw_type == "fondocomundeinversion":
            return "fci"
        if raw_type in {"cedears", "acciones"}:
            return "equity"
        if patrimonial in {"equity", "growth", "defensive", "value", "dividend"}:
            return "equity"
        if patrimonial == "cash":
            return "cash"
        return "unknown"

    @staticmethod
    def _aggregate_impacts(
        positions: list[NormalizedPosition],
        impacts: list[ScenarioAssetImpact],
        field_name: str,
        *,
        normalizer=None,
    ) -> list[ScenarioGroupImpact]:
        impact_map = {impact.symbol: impact for impact in impacts}
        grouped_money = aggregate_numeric_items(
            positions,
            key_getter=lambda item: getattr(item, field_name, None),
            value_getter=lambda item: impact_map[item.symbol].estimated_impact_money,
            normalizer=normalizer,
        )
        total_basis = sum(position.market_value for position in positions)
        groups = []
        for key, impact_money in sorted(grouped_money.items(), key=lambda item: item[1]):
            groups.append(
                ScenarioGroupImpact(
                    key=key,
                    impact_pct=round(safe_percentage(impact_money, total_basis), 2),
                    impact_money=round(float(impact_money), 2),
                )
            )
        return groups
