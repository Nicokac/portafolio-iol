from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from .schemas import ContributionGroupItem, DataQualityFlags


def safe_percentage(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (float(numerator) / float(denominator)) * 100.0


def normalize_percentage_allocation(allocation: dict[str, float]) -> dict[str, float]:
    cleaned = {
        key: float(value)
        for key, value in allocation.items()
        if float(value) > 0
    }
    total = sum(cleaned.values())
    if total <= 0:
        return {}

    normalized = {
        key: round((value / total) * 100.0, 2)
        for key, value in cleaned.items()
    }
    drift = round(100.0 - sum(normalized.values()), 2)
    if normalized and drift != 0:
        max_key = max(normalized, key=normalized.get)
        normalized[max_key] = round(normalized[max_key] + drift, 2)
    return normalized


def aggregate_numeric_items(
    items: Iterable[object],
    key_getter: Callable[[object], str | None],
    value_getter: Callable[[object], float],
    *,
    unknown_label: str = "unknown",
    normalizer: Callable[[str], str] | None = None,
) -> dict[str, float]:
    grouped: dict[str, float] = {}
    for item in items:
        raw_key = key_getter(item) or unknown_label
        key = normalizer(raw_key) if normalizer else raw_key
        grouped[key] = grouped.get(key, 0.0) + float(value_getter(item))
    return grouped


def aggregate_positions_by_field(
    positions: Sequence[object],
    field_name: str,
    value_getter: Callable[[object], float],
    *,
    unknown_label: str = "unknown",
    normalizer: Callable[[str], str] | None = None,
) -> dict[str, float]:
    return aggregate_numeric_items(
        positions,
        key_getter=lambda item: getattr(item, field_name, None),
        value_getter=value_getter,
        unknown_label=unknown_label,
        normalizer=normalizer,
    )


def normalize_country_label(value: str | None) -> str:
    if not value:
        return "unknown"
    normalized = str(value).strip()
    lowered = normalized.lower()
    if lowered in {"usa", "estados unidos", "united states", "eeuu"}:
        return "USA"
    if lowered == "argentina":
        return "Argentina"
    return normalized


def aggregate_aliases(
    distribution: dict[str, float],
    alias_resolver: Callable[[str], str],
) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for key, value in distribution.items():
        resolved = alias_resolver(key)
        aggregated[resolved] = aggregated.get(resolved, 0.0) + float(value)
    return aggregated


def build_group_items(
    grouped_values: dict[str, float],
    *,
    basis_total: float | None = None,
) -> list[ContributionGroupItem]:
    items: list[ContributionGroupItem] = []
    for key, value in sorted(grouped_values.items(), key=lambda item: item[1], reverse=True):
        weight_pct = safe_percentage(value, basis_total) if basis_total is not None else None
        items.append(
            ContributionGroupItem(
                key=key,
                contribution_pct=float(value),
                weight_pct=weight_pct,
            )
        )
    return items


def rank_top_items(
    items: Sequence[object],
    value_getter: Callable[[object], float],
    *,
    limit: int = 5,
) -> list[object]:
    if limit <= 0:
        return []
    return sorted(items, key=value_getter, reverse=True)[:limit]


def derive_confidence(
    *,
    has_missing_metadata: bool = False,
    has_insufficient_history: bool = False,
    used_fallback: bool = False,
) -> str:
    if has_insufficient_history:
        return "low"
    if has_missing_metadata and used_fallback:
        return "low"
    if has_missing_metadata or used_fallback:
        return "medium"
    return "high"


def build_data_quality_flags(
    *,
    has_missing_metadata: bool = False,
    has_insufficient_history: bool = False,
    used_fallback: bool = False,
    warnings: Iterable[str] | None = None,
) -> DataQualityFlags:
    warning_list = list(dict.fromkeys(warnings or []))
    return DataQualityFlags(
        has_missing_metadata=has_missing_metadata,
        has_insufficient_history=has_insufficient_history,
        used_fallback=used_fallback,
        confidence=derive_confidence(
            has_missing_metadata=has_missing_metadata,
            has_insufficient_history=has_insufficient_history,
            used_fallback=used_fallback,
        ),
        warnings=warning_list,
    )
