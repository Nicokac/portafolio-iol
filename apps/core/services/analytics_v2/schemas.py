from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal


ConfidenceLevel = Literal["high", "medium", "low"]


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {
            key: _serialize(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class SerializableSchema:
    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(frozen=True)
class DataQualityFlags(SerializableSchema):
    has_missing_metadata: bool = False
    has_insufficient_history: bool = False
    used_fallback: bool = False
    confidence: ConfidenceLevel = "medium"
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True)
class AnalyticsMetadata(SerializableSchema):
    methodology: str
    data_basis: str
    limitations: str
    confidence: ConfidenceLevel = "medium"
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.methodology.strip():
            raise ValueError("methodology cannot be empty")
        if not self.data_basis.strip():
            raise ValueError("data_basis cannot be empty")
        if not self.limitations.strip():
            raise ValueError("limitations cannot be empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True)
class NormalizedPosition(SerializableSchema):
    symbol: str
    description: str
    market_value: float
    weight_pct: float
    sector: str | None = None
    country: str | None = None
    asset_type: str | None = None
    strategic_bucket: str | None = None
    patrimonial_type: str | None = None
    currency: str | None = None
    gain_pct: float | None = None
    gain_money: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")


@dataclass(frozen=True)
class NormalizedPortfolioSnapshot(SerializableSchema):
    date: str
    total_iol: float
    liquidity_operativa: float
    cash_management: float
    invested_portfolio: float
    usa_exposure_pct: float | None = None
    argentina_exposure_pct: float | None = None

    def __post_init__(self) -> None:
        if not self.date.strip():
            raise ValueError("date cannot be empty")


@dataclass(frozen=True)
class BenchmarkAvailability(SerializableSchema):
    benchmark_key: str
    symbol: str
    source: str
    interval: str
    observations: int
    latest_date: str | None = None

    def __post_init__(self) -> None:
        if not self.benchmark_key.strip():
            raise ValueError("benchmark_key cannot be empty")
        if self.observations < 0:
            raise ValueError("observations cannot be negative")


@dataclass(frozen=True)
class ContributionGroupItem(SerializableSchema):
    key: str
    contribution_pct: float
    weight_pct: float | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("key cannot be empty")


@dataclass(frozen=True)
class RiskContributionItem(SerializableSchema):
    symbol: str
    weight_pct: float
    volatility_proxy: float | None
    risk_score: float
    contribution_pct: float
    sector: str | None = None
    country: str | None = None
    asset_type: str | None = None
    used_volatility_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")


@dataclass(frozen=True)
class RiskContributionResult(SerializableSchema):
    items: list[RiskContributionItem]
    by_sector: list[ContributionGroupItem]
    by_country: list[ContributionGroupItem]
    by_asset_type: list[ContributionGroupItem]
    top_contributors: list[RiskContributionItem]
    metadata: AnalyticsMetadata


@dataclass(frozen=True)
class ScenarioDefinition(SerializableSchema):
    scenario_key: str
    label: str
    description: str

    def __post_init__(self) -> None:
        if not self.scenario_key.strip():
            raise ValueError("scenario_key cannot be empty")
        if not self.label.strip():
            raise ValueError("label cannot be empty")


@dataclass(frozen=True)
class ScenarioAssetImpact(SerializableSchema):
    symbol: str
    market_value: float
    estimated_impact_pct: float
    estimated_impact_money: float
    transmission_channel: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not self.transmission_channel.strip():
            raise ValueError("transmission_channel cannot be empty")


@dataclass(frozen=True)
class ScenarioGroupImpact(SerializableSchema):
    key: str
    impact_pct: float
    impact_money: float

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("key cannot be empty")


@dataclass(frozen=True)
class ScenarioAnalysisResult(SerializableSchema):
    scenario_key: str
    total_impact_pct: float
    total_impact_money: float
    by_asset: list[ScenarioAssetImpact]
    by_sector: list[ScenarioGroupImpact]
    by_country: list[ScenarioGroupImpact]
    top_negative_contributors: list[ScenarioAssetImpact]
    metadata: AnalyticsMetadata

    def __post_init__(self) -> None:
        if not self.scenario_key.strip():
            raise ValueError("scenario_key cannot be empty")


@dataclass(frozen=True)
class FactorExposureItem(SerializableSchema):
    factor: str
    exposure_pct: float
    confidence: ConfidenceLevel = "medium"

    def __post_init__(self) -> None:
        if not self.factor.strip():
            raise ValueError("factor cannot be empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True)
class FactorClassification(SerializableSchema):
    symbol: str
    factor: str | None
    source: str
    confidence: ConfidenceLevel
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not self.source.strip():
            raise ValueError("source cannot be empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True)
class FactorDefinition(SerializableSchema):
    factor_key: str
    label: str
    description: str
    classification_notes: str = ""

    def __post_init__(self) -> None:
        if not self.factor_key.strip():
            raise ValueError("factor_key cannot be empty")
        if not self.label.strip():
            raise ValueError("label cannot be empty")
        if not self.description.strip():
            raise ValueError("description cannot be empty")


@dataclass(frozen=True)
class FactorExposureResult(SerializableSchema):
    factors: list[FactorExposureItem]
    dominant_factor: str | None
    underrepresented_factors: list[str]
    unknown_assets: list[str]
    metadata: AnalyticsMetadata


@dataclass(frozen=True)
class StressFragilityResult(SerializableSchema):
    scenario_key: str
    fragility_score: float
    total_loss_pct: float
    total_loss_money: float
    vulnerable_assets: list[ScenarioAssetImpact]
    vulnerable_sectors: list[ScenarioGroupImpact]
    vulnerable_countries: list[ScenarioGroupImpact]
    metadata: AnalyticsMetadata

    def __post_init__(self) -> None:
        if not self.scenario_key.strip():
            raise ValueError("scenario_key cannot be empty")


@dataclass(frozen=True)
class StressDefinition(SerializableSchema):
    stress_key: str
    label: str
    description: str

    def __post_init__(self) -> None:
        if not self.stress_key.strip():
            raise ValueError("stress_key cannot be empty")
        if not self.label.strip():
            raise ValueError("label cannot be empty")
        if not self.description.strip():
            raise ValueError("description cannot be empty")


@dataclass(frozen=True)
class RecommendationSignal(SerializableSchema):
    signal_key: str
    severity: ConfidenceLevel
    title: str
    description: str
    affected_scope: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.signal_key.strip():
            raise ValueError("signal_key cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.affected_scope.strip():
            raise ValueError("affected_scope cannot be empty")
        _validate_confidence(self.severity)


@dataclass(frozen=True)
class ExpectedReturnBucketItem(SerializableSchema):
    bucket_key: str
    label: str
    weight_pct: float
    expected_return_pct: float | None
    basis_reference: str

    def __post_init__(self) -> None:
        if not self.bucket_key.strip():
            raise ValueError("bucket_key cannot be empty")
        if not self.label.strip():
            raise ValueError("label cannot be empty")
        if not self.basis_reference.strip():
            raise ValueError("basis_reference cannot be empty")


@dataclass(frozen=True)
class ExpectedReturnResult(SerializableSchema):
    expected_return_pct: float | None
    real_expected_return_pct: float | None
    basis_reference: str
    by_bucket: list[ExpectedReturnBucketItem]
    metadata: AnalyticsMetadata

    def __post_init__(self) -> None:
        if not self.basis_reference.strip():
            raise ValueError("basis_reference cannot be empty")


def _validate_confidence(confidence: str) -> None:
    if confidence not in {"high", "medium", "low"}:
        raise ValueError("confidence must be one of: high, medium, low")
