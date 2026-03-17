from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable

from apps.core.services.analytics_v2 import (
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    RiskContributionService,
    ScenarioAnalysisService,
    StressFragilityService,
)
from apps.core.services.analytics_v2.schemas import NormalizedPosition
from apps.core.services.analytics_v2.scenario_catalog import ScenarioCatalogService
from apps.core.services.analytics_v2.stress_catalog import StressCatalogService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@dataclass(frozen=True)
class _SyntheticSnapshotPosition:
    simbolo: str
    valorizado: float
    tipo: str


@dataclass(frozen=True)
class _SyntheticParametro:
    simbolo: str
    sector: str
    pais_exposicion: str
    tipo_patrimonial: str
    bloque_estrategico: str


class _InMemoryScenarioAnalysisService(ScenarioAnalysisService):
    def __init__(self, positions: list[NormalizedPosition]):
        super().__init__()
        self._positions = positions

    def _load_current_positions(self) -> list[NormalizedPosition]:
        return list(self._positions)


class _InMemoryRiskContributionService(RiskContributionService):
    def __init__(self, positions: list[NormalizedPosition]):
        super().__init__()
        self._positions = positions
        self._params = {
            position.symbol: _SyntheticParametro(
                simbolo=position.symbol,
                sector=position.sector or "unknown",
                pais_exposicion=position.country or "unknown",
                tipo_patrimonial=position.patrimonial_type or "unknown",
                bloque_estrategico=position.strategic_bucket or "unknown",
            )
            for position in positions
        }

    def _load_current_invested_positions(self) -> list[_SyntheticSnapshotPosition]:
        rows: list[_SyntheticSnapshotPosition] = []
        for position in self._positions:
            if (position.asset_type or "").lower() in {"cash", "fci"}:
                continue
            rows.append(
                _SyntheticSnapshotPosition(
                    simbolo=position.symbol,
                    valorizado=float(position.market_value),
                    tipo=self._normalize_raw_type(position),
                )
            )
        return rows

    @staticmethod
    def _normalize_raw_type(position: NormalizedPosition) -> str:
        asset_type = (position.asset_type or "").lower()
        if asset_type == "bond":
            return "TitulosPublicos"
        if asset_type == "fci":
            return "FondoComundeInversion"
        if asset_type == "cash":
            return "CAUCIONESPESOS"
        return "ACCIONES"

    def _load_parameters(self, positions: list[_SyntheticSnapshotPosition]) -> dict[str, _SyntheticParametro]:
        return {
            position.simbolo: self._params[position.simbolo]
            for position in positions
            if position.simbolo in self._params
        }


class IncrementalPortfolioSimulator:
    """Simula un plan incremental de compra y compara before/after con Analytics v2."""

    def __init__(
        self,
        *,
        current_positions_loader: Callable[[], list[NormalizedPosition]] | None = None,
        asset_metadata_loader: Callable[[str], NormalizedPosition | None] | None = None,
        analytics_runner: Callable[[list[NormalizedPosition]], dict] | None = None,
    ):
        self._scenario_service = ScenarioAnalysisService()
        self.current_positions_loader = current_positions_loader or self._scenario_service._load_current_positions  # noqa: SLF001
        self.asset_metadata_loader = asset_metadata_loader or self._load_asset_metadata
        self.analytics_runner = analytics_runner or self._run_analytics

    def simulate(self, proposal: dict) -> dict:
        capital_amount = self._coerce_amount(proposal.get("capital_amount"))
        purchase_plan = proposal.get("purchase_plan") or []

        if capital_amount <= 0:
            return self._empty_result(warnings=["invalid_capital"])
        if not isinstance(purchase_plan, list) or not purchase_plan:
            return self._empty_result(warnings=["empty_purchase_plan"])

        before_positions = list(self.current_positions_loader() or [])
        applied_plan, plan_total, warnings = self._normalize_purchase_plan(purchase_plan)
        if plan_total <= 0:
            warnings.append("empty_purchase_plan")
            return self._empty_result(warnings=warnings)
        if abs(plan_total - capital_amount) > Decimal("0.01"):
            warnings.append("capital_plan_mismatch")

        after_positions = self._apply_purchase_plan(before_positions, applied_plan, warnings)
        before_analytics = self.analytics_runner(before_positions)
        after_analytics = self.analytics_runner(after_positions)
        delta = self._build_delta(before_analytics, after_analytics)

        return {
            "capital_amount": float(capital_amount),
            "applied_capital_amount": float(plan_total),
            "purchase_plan": [
                {"symbol": symbol, "amount": float(amount)}
                for symbol, amount in applied_plan.items()
            ],
            "before": self._build_summary(before_analytics),
            "after": self._build_summary(after_analytics),
            "delta": delta,
            "interpretation": self._build_interpretation(before_analytics, after_analytics, delta),
            "warnings": warnings,
        }

    def _normalize_purchase_plan(self, purchase_plan: list[dict]) -> tuple[dict[str, Decimal], Decimal, list[str]]:
        normalized: dict[str, Decimal] = {}
        warnings: list[str] = []
        for item in purchase_plan:
            symbol = str(item.get("symbol") or "").strip().upper()
            amount = self._coerce_amount(item.get("amount"))
            if not symbol:
                warnings.append("missing_purchase_symbol")
                continue
            if amount <= 0:
                warnings.append(f"invalid_purchase_amount:{symbol}")
                continue
            normalized[symbol] = normalized.get(symbol, Decimal("0")) + amount
        total = sum(normalized.values(), Decimal("0"))
        return normalized, total, warnings

    def _apply_purchase_plan(
        self,
        positions: list[NormalizedPosition],
        purchase_plan: dict[str, Decimal],
        warnings: list[str],
    ) -> list[NormalizedPosition]:
        updated = {
            position.symbol: self._clone_position(position)
            for position in positions
        }

        for symbol, amount in purchase_plan.items():
            if symbol in updated:
                current = updated[symbol]
                updated[symbol] = self._clone_position(
                    current,
                    market_value=float(current.market_value) + float(amount),
                )
                continue

            template = self.asset_metadata_loader(symbol)
            if template is None:
                warnings.append(f"unknown_purchase_symbol:{symbol}")
                continue
            updated[symbol] = self._clone_position(template, market_value=float(amount))

        return self._reweight_positions(list(updated.values()))

    @staticmethod
    def _clone_position(position: NormalizedPosition, **overrides) -> NormalizedPosition:
        payload = position.to_dict()
        payload.update(overrides)
        return NormalizedPosition(**payload)

    @staticmethod
    def _reweight_positions(positions: list[NormalizedPosition]) -> list[NormalizedPosition]:
        total = sum(float(position.market_value) for position in positions)
        if total <= 0:
            return positions
        return [
            IncrementalPortfolioSimulator._clone_position(
                position,
                weight_pct=round((float(position.market_value) / total) * 100.0, 2),
            )
            for position in sorted(positions, key=lambda item: (-float(item.market_value), item.symbol))
        ]

    def _run_analytics(self, positions: list[NormalizedPosition]) -> dict:
        scenario_service = _InMemoryScenarioAnalysisService(positions)
        expected_return_service = ExpectedReturnService(positions_loader=scenario_service)
        factor_exposure_service = FactorExposureService(positions_loader=scenario_service)
        stress_fragility_service = StressFragilityService(scenario_analysis_service=scenario_service)
        risk_base_service = _InMemoryRiskContributionService(positions)
        covariance_service = CovarianceAwareRiskContributionService(base_service=risk_base_service)

        expected_return_result = expected_return_service.calculate()
        factor_result = factor_exposure_service.calculate()
        covariance_result = covariance_service.calculate(top_n=5)
        if covariance_result.get("model_variant") == "covariance_aware":
            risk_result = covariance_result
        else:
            risk_result = risk_base_service.calculate(top_n=5)
            risk_result.update(
                {
                    "model_variant": covariance_result.get("model_variant", "mvp_proxy"),
                    "covariance_observations": covariance_result.get("covariance_observations", 0),
                    "coverage_pct": covariance_result.get("coverage_pct", 0.0),
                }
            )

        scenario_catalog = ScenarioCatalogService()
        scenario_results = [scenario_service.analyze(item["scenario_key"]) for item in scenario_catalog.list_scenarios()]
        worst_scenario = min(
            scenario_results,
            key=lambda item: float(item.get("total_impact_pct") or 0.0),
            default=None,
        )

        stress_catalog = StressCatalogService()
        stress_results = [stress_fragility_service.calculate(item["stress_key"]) for item in stress_catalog.list_stresses()]
        worst_stress = max(
            stress_results,
            key=lambda item: float(item.get("fragility_score") or 0.0),
            default=None,
        )

        top_risk = (risk_result.get("top_contributors") or [{}])[0]
        return {
            "expected_return_pct": expected_return_result.get("expected_return_pct"),
            "real_expected_return_pct": expected_return_result.get("real_expected_return_pct"),
            "fragility_score": worst_stress.get("fragility_score") if worst_stress else None,
            "worst_stress_key": worst_stress.get("scenario_key") if worst_stress else None,
            "dominant_factor": factor_result.get("dominant_factor"),
            "worst_scenario_key": worst_scenario.get("scenario_key") if worst_scenario else None,
            "worst_scenario_loss_pct": worst_scenario.get("total_impact_pct") if worst_scenario else None,
            "top_risk_contributor": top_risk.get("symbol"),
            "top_risk_contribution_pct": top_risk.get("contribution_pct"),
            "risk_model_variant": risk_result.get("model_variant", "mvp_proxy"),
            "factor_result": factor_result,
            "risk_result": risk_result,
            "warnings": self._dedupe_warnings(
                expected_return_result.get("metadata", {}).get("warnings", [])
                + factor_result.get("metadata", {}).get("warnings", [])
                + risk_result.get("metadata", {}).get("warnings", [])
            ),
        }

    @staticmethod
    def _build_summary(analytics: dict) -> dict:
        return {
            "expected_return_pct": analytics.get("expected_return_pct"),
            "real_expected_return_pct": analytics.get("real_expected_return_pct"),
            "fragility_score": analytics.get("fragility_score"),
            "dominant_factor": analytics.get("dominant_factor"),
            "worst_scenario_key": analytics.get("worst_scenario_key"),
            "worst_scenario_loss_pct": analytics.get("worst_scenario_loss_pct"),
            "top_risk_contributor": analytics.get("top_risk_contributor"),
            "top_risk_contribution_pct": analytics.get("top_risk_contribution_pct"),
            "risk_model_variant": analytics.get("risk_model_variant"),
        }

    @staticmethod
    def _build_delta(before: dict, after: dict) -> dict:
        return {
            "expected_return_change": IncrementalPortfolioSimulator._delta(
                before.get("expected_return_pct"),
                after.get("expected_return_pct"),
            ),
            "real_expected_return_change": IncrementalPortfolioSimulator._delta(
                before.get("real_expected_return_pct"),
                after.get("real_expected_return_pct"),
            ),
            "fragility_change": IncrementalPortfolioSimulator._delta(
                before.get("fragility_score"),
                after.get("fragility_score"),
            ),
            "scenario_loss_change": IncrementalPortfolioSimulator._delta(
                before.get("worst_scenario_loss_pct"),
                after.get("worst_scenario_loss_pct"),
            ),
            "risk_concentration_change": IncrementalPortfolioSimulator._delta(
                before.get("top_risk_contribution_pct"),
                after.get("top_risk_contribution_pct"),
            ),
        }

    @staticmethod
    def _delta(before, after):
        if before is None or after is None:
            return None
        return round(float(after) - float(before), 2)

    def _build_interpretation(self, before: dict, after: dict, delta: dict) -> str:
        messages: list[str] = []

        fragility_change = delta.get("fragility_change")
        if fragility_change is not None and fragility_change < 0:
            messages.append("La compra reduce la fragilidad del portafolio.")
        elif fragility_change is not None and fragility_change > 0:
            messages.append("La compra aumenta la fragilidad del portafolio.")

        expected_change = delta.get("expected_return_change")
        if expected_change is not None and expected_change > 0:
            messages.append("La compra mejora el retorno esperado estructural.")

        scenario_change = delta.get("scenario_loss_change")
        if scenario_change is not None and scenario_change > 0:
            messages.append("La compra mejora la resiliencia frente al peor escenario actual.")
        elif scenario_change is not None and scenario_change < 0:
            messages.append("La compra empeora la pérdida estimada del peor escenario.")

        risk_change = delta.get("risk_concentration_change")
        if risk_change is not None and risk_change < 0:
            messages.append("La compra reduce la concentración del principal contribuidor al riesgo.")
        elif risk_change is not None and risk_change > 0:
            messages.append("La compra aumenta la concentración del principal contribuidor al riesgo.")

        before_factors = self._factor_map(before.get("factor_result", {}))
        after_factors = self._factor_map(after.get("factor_result", {}))
        if after_factors.get("defensive", 0.0) > before_factors.get("defensive", 0.0):
            messages.append("La compra aumenta la exposición defensiva.")
        if after_factors.get("dividend", 0.0) > before_factors.get("dividend", 0.0):
            messages.append("La compra refuerza el perfil de ingresos pasivos.")

        if not messages:
            return "La compra propuesta no altera materialmente las métricas principales del portafolio en el MVP."
        return " ".join(messages)

    @staticmethod
    def _factor_map(result: dict) -> dict[str, float]:
        return {
            str(item.get("factor")): float(item.get("exposure_pct") or 0.0)
            for item in result.get("factors", [])
        }

    def _load_asset_metadata(self, symbol: str) -> NormalizedPosition | None:
        row = ActivoPortafolioSnapshot.objects.filter(simbolo=symbol).order_by("-fecha_extraccion").first()
        param = ParametroActivo.objects.filter(simbolo=symbol).first()
        if row is None and param is None:
            return None

        if row is not None:
            asset_type = self._scenario_service._resolve_asset_type(row, param)  # noqa: SLF001
            description = row.descripcion or symbol
            currency = self._scenario_service._normalize_currency(row.moneda)  # noqa: SLF001
        else:
            asset_type = self._infer_asset_type_from_param(param)
            description = symbol
            currency = "ARS"

        return NormalizedPosition(
            symbol=symbol,
            description=description,
            market_value=0.0,
            weight_pct=0.0,
            sector=param.sector if param else "unknown",
            country=param.pais_exposicion if param else "unknown",
            asset_type=asset_type,
            strategic_bucket=param.bloque_estrategico if param else "unknown",
            patrimonial_type=param.tipo_patrimonial if param else "unknown",
            currency=currency,
            gain_pct=0.0,
            gain_money=0.0,
        )

    @staticmethod
    def _infer_asset_type_from_param(param: ParametroActivo | None) -> str:
        patrimonial = (param.tipo_patrimonial if param else "").strip().lower()
        if patrimonial == "bond":
            return "bond"
        if patrimonial in {"cash", "fci"}:
            return patrimonial
        if patrimonial in {"equity", "growth", "defensive", "value", "dividend"}:
            return "equity"
        return "unknown"

    @staticmethod
    def _coerce_amount(value) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _dedupe_warnings(warnings: list[str]) -> list[str]:
        seen: list[str] = []
        for warning in warnings:
            if warning not in seen:
                seen.append(warning)
        return seen

    @staticmethod
    def _empty_result(*, warnings: list[str]) -> dict:
        return {
            "capital_amount": 0.0,
            "applied_capital_amount": 0.0,
            "purchase_plan": [],
            "before": {},
            "after": {},
            "delta": {
                "expected_return_change": None,
                "real_expected_return_change": None,
                "fragility_change": None,
                "scenario_loss_change": None,
                "risk_concentration_change": None,
            },
            "interpretation": "No se pudo simular la compra incremental con los datos provistos.",
            "warnings": warnings,
        }
