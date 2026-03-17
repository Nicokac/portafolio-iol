"""Shared contracts for Portfolio Analytics v2."""

from .analytics_explanation_service import AnalyticsExplanationService
from .helpers import (
    aggregate_aliases,
    aggregate_numeric_items,
    aggregate_positions_by_field,
    build_data_quality_flags,
    build_group_items,
    derive_confidence,
    normalize_country_label,
    normalize_percentage_allocation,
    rank_top_items,
    safe_percentage,
)
from .covariance_risk_contribution_service import CovarianceAwareRiskContributionService
from .factor_catalog import FACTOR_CATALOG, FactorCatalogService
from .factor_classifier_service import FactorClassifierService
from .factor_exposure_service import FactorExposureService
from .local_macro_signals_service import LocalMacroSignalsService
from .expected_return_service import ExpectedReturnService
from .risk_contribution_service import RiskContributionService
from .scenario_analysis_service import ScenarioAnalysisService
from .scenario_sensitivity_service import ScenarioSensitivityService
from .scenario_catalog import SCENARIO_CATALOG, ScenarioCatalogService
from .stress_catalog import STRESS_CATALOG, StressCatalogService
from .stress_fragility_service import StressFragilityService
from .schemas import (
    AnalyticsMetadata,
    BenchmarkAvailability,
    ContributionGroupItem,
    DataQualityFlags,
    ExpectedReturnBucketItem,
    ExpectedReturnResult,
    FactorClassification,
    FactorDefinition,
    FactorExposureItem,
    FactorExposureResult,
    NormalizedPortfolioSnapshot,
    NormalizedPosition,
    RiskContributionItem,
    RiskContributionResult,
    RecommendationSignal,
    ScenarioAnalysisResult,
    ScenarioAssetImpact,
    ScenarioDefinition,
    ScenarioGroupImpact,
    StressDefinition,
    StressFragilityResult,
)

__all__ = [
    "AnalyticsExplanationService",
    "aggregate_aliases",
    "aggregate_numeric_items",
    "aggregate_positions_by_field",
    "AnalyticsMetadata",
    "BenchmarkAvailability",
    "build_data_quality_flags",
    "build_group_items",
    "ContributionGroupItem",
    "CovarianceAwareRiskContributionService",
    "DataQualityFlags",
    "derive_confidence",
    "ExpectedReturnBucketItem",
    "ExpectedReturnResult",
    "ExpectedReturnService",
    "FACTOR_CATALOG",
    "FactorClassification",
    "FactorCatalogService",
    "FactorClassifierService",
    "FactorDefinition",
    "FactorExposureService",
    "LocalMacroSignalsService",
    "FactorExposureItem",
    "FactorExposureResult",
    "normalize_country_label",
    "normalize_percentage_allocation",
    "NormalizedPortfolioSnapshot",
    "NormalizedPosition",
    "rank_top_items",
    "RiskContributionService",
    "RiskContributionItem",
    "RiskContributionResult",
    "RecommendationSignal",
    "SCENARIO_CATALOG",
    "safe_percentage",
    "ScenarioAnalysisService",
    "ScenarioAnalysisResult",
    "ScenarioAssetImpact",
    "ScenarioCatalogService",
    "ScenarioDefinition",
    "ScenarioGroupImpact",
    "ScenarioSensitivityService",
    "STRESS_CATALOG",
    "StressCatalogService",
    "StressDefinition",
    "StressFragilityService",
    "StressFragilityResult",
]
