from datetime import date
from types import SimpleNamespace

import pytest

from apps.core.models import MacroSeriesSnapshot
from apps.core.services.local_macro_context import (
    annualize_change_pct,
    build_fx_context_summary,
    calculate_gap_pct,
)


def test_calculate_gap_pct_returns_none_when_official_is_invalid():
    assert calculate_gap_pct(1200.0, 0.0) is None


def test_annualize_change_pct_returns_none_for_non_positive_growth_factor():
    assert annualize_change_pct(-100.0, lookback_days=30) is None


@pytest.mark.django_db
def test_build_fx_context_summary_blends_mep_and_ccl():
    service = SimpleNamespace(
        _get_latest_snapshot=lambda series_key: MacroSeriesSnapshot.objects.filter(series_key=series_key).order_by("-fecha").first(),
    )
    for series_key, current_date, value in [
        ("usdars_oficial", date(2026, 2, 10), 1000.0),
        ("usdars_oficial", date(2026, 3, 13), 1000.0),
        ("usdars_mep", date(2026, 2, 10), 1180.0),
        ("usdars_mep", date(2026, 3, 13), 1200.0),
        ("usdars_ccl", date(2026, 2, 10), 1200.0),
        ("usdars_ccl", date(2026, 3, 13), 1240.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key=series_key,
            source="manual",
            external_id=series_key,
            frequency="daily",
            fecha=current_date,
            value=value,
        )

    summary = build_fx_context_summary(
        service,
        official_snapshot=SimpleNamespace(value=1000.0),
        mep_snapshot=SimpleNamespace(value=1180.0),
        ccl_snapshot=SimpleNamespace(value=1220.0),
        lookback_days=30,
    )

    assert summary["financial_source"] == "blend_mep_ccl"
    assert summary["financial_value"] == 1200.0
    assert summary["fx_gap_change_30d"] is not None
