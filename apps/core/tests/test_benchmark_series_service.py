from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from apps.core.models import BenchmarkSnapshot
from apps.core.services.benchmark_series_service import BenchmarkSeriesService


@pytest.mark.django_db
def test_benchmark_series_service_syncs_and_upserts_rows_for_multiple_intervals():
    client = Mock()
    client.fetch_daily_adjusted.return_value = [
        {"fecha": date(2026, 3, 11), "close": 500.0, "adjusted_close": 499.5, "volume": 1000},
        {"fecha": date(2026, 3, 12), "close": 502.0, "adjusted_close": 501.5, "volume": 1100},
    ]
    client.fetch_weekly_adjusted.return_value = [
        {"fecha": date(2026, 3, 6), "close": 495.0, "adjusted_close": 494.5, "volume": 2000},
        {"fecha": date(2026, 3, 13), "close": 505.0, "adjusted_close": 504.5, "volume": 2100},
    ]

    service = BenchmarkSeriesService(client=client)
    first = service.sync_benchmark("cedear_usa")
    second = service.sync_benchmark("cedear_usa")

    assert first["created"] == 4
    assert second["updated"] == 4
    assert first["intervals"]["daily"]["rows_received"] == 2
    assert first["intervals"]["weekly_adjusted"]["rows_received"] == 2
    assert BenchmarkSnapshot.objects.count() == 4


@pytest.mark.django_db
def test_benchmark_series_service_sync_all_captures_partial_failures(monkeypatch):
    service = BenchmarkSeriesService(client=Mock())

    def fake_sync_benchmark(benchmark_key, outputsize="compact"):
        if benchmark_key == "bonos_ar":
            raise ValueError("rate limit")
        return {
            "success": True,
            "benchmark_key": benchmark_key,
            "symbol": "X",
            "provider": "alpha_vantage",
            "rows_received": 10,
            "created": 10,
            "updated": 0,
        }

    monkeypatch.setattr(service, "sync_benchmark", fake_sync_benchmark)
    monkeypatch.setattr("apps.core.services.benchmark_series_service.time.sleep", lambda _seconds: None)

    result = service.sync_all()

    assert result["cedear_usa"]["success"] is True
    assert result["bonos_ar"]["success"] is False
    assert "rate limit" in result["bonos_ar"]["error"]


@pytest.mark.django_db
def test_benchmark_series_service_builds_returns_from_daily_snapshots():
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="daily",
        fecha=date(2026, 3, 10),
        close=500,
        adjusted_close=500,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="daily",
        fecha=date(2026, 3, 11),
        close=510,
        adjusted_close=510,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="daily",
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


@pytest.mark.django_db
def test_benchmark_series_service_builds_returns_from_weekly_snapshots():
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="weekly_adjusted",
        fecha=date(2026, 3, 6),
        close=500,
        adjusted_close=500,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="weekly_adjusted",
        fecha=date(2026, 3, 13),
        close=510,
        adjusted_close=510,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="weekly_adjusted",
        fecha=date(2026, 3, 20),
        close=515,
        adjusted_close=515,
        volume=1000,
    )

    returns = BenchmarkSeriesService(client=Mock()).build_weekly_returns(
        "cedear_usa",
        pd.to_datetime(["2026-03-13", "2026-03-20"]),
    )

    assert len(returns) == 2
    assert returns.iloc[0] > 0
    assert returns.iloc[1] > 0


@pytest.mark.django_db
def test_benchmark_series_service_status_summary_includes_interval_breakdown():
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="daily",
        fecha=date(2026, 3, 12),
        close=515,
        adjusted_close=515,
        volume=1000,
    )
    BenchmarkSnapshot.objects.create(
        benchmark_key="cedear_usa",
        symbol="SPY",
        source="alpha_vantage",
        interval="weekly_adjusted",
        fecha=date(2026, 3, 13),
        close=520,
        adjusted_close=520,
        volume=1200,
    )

    summary = BenchmarkSeriesService(client=Mock()).get_status_summary()

    assert {row["benchmark_key"] for row in summary} == {"cedear_usa", "bonos_ar", "liquidez"}
    cedear = next(row for row in summary if row["benchmark_key"] == "cedear_usa")
    assert cedear["rows_count"] == 2
    assert cedear["daily_rows_count"] == 1
    assert cedear["weekly_rows_count"] == 1
    assert cedear["latest_date"].isoformat() == "2026-03-13"
    assert cedear["is_ready"] is False
