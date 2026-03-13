from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from apps.core.models import BenchmarkSnapshot
from apps.core.services.benchmark_series_service import BenchmarkSeriesService


@pytest.mark.django_db
def test_benchmark_series_service_syncs_and_upserts_rows():
    client = Mock()
    client.fetch_daily_adjusted.return_value = [
        {"fecha": date(2026, 3, 11), "close": 500.0, "adjusted_close": 499.5, "volume": 1000},
        {"fecha": date(2026, 3, 12), "close": 502.0, "adjusted_close": 501.5, "volume": 1100},
    ]

    service = BenchmarkSeriesService(client=client)
    first = service.sync_benchmark("cedear_usa")
    second = service.sync_benchmark("cedear_usa")

    assert first["created"] == 2
    assert second["updated"] == 2
    assert BenchmarkSnapshot.objects.count() == 2


@pytest.mark.django_db
def test_benchmark_series_service_builds_returns_from_snapshots():
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        fecha=date(2026, 3, 10),
        close=500,
        adjusted_close=500,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        fecha=date(2026, 3, 11),
        close=510,
        adjusted_close=510,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        fecha=date(2026, 3, 12),
        close=515,
        adjusted_close=515,
        volume=1000,
    )

    returns = BenchmarkSeriesService(client=Mock()).build_daily_returns(
        "cedear_usa",
        pd.to_datetime(["2026-03-11", "2026-03-12"]),
    )

    assert len(returns) == 2
    assert returns.iloc[0] > 0
    assert returns.iloc[1] > 0
